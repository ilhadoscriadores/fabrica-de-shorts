"""A base do corte: junta os trechos, encurta as pausas, censura palavrão e gera a linha do tempo final.

Tudo é cortado na grade de quadros (1/30 s): imagem e som saem com o mesmo tamanho, sem a fala escorregar."""
from __future__ import annotations

import math
import re
from pathlib import Path

import numpy as np

from . import ambiente, config, legendas, transcricao, util

FPS = 30
SR = 48000
ANTES, DEPOIS = 0.06, 0.12

PALAVROES = {
    "pt": {"porra", "caralho", "caralhos", "cacete", "merda", "foda", "fodase", "foder", "fodeu", "fodido", "fodida",
           "puta", "puto", "putaria", "putamerda", "buceta", "boceta", "cu", "cuzao", "arrombado", "arrombada",
           "viado", "bosta", "piranha", "desgracado", "desgracada", "vagabundo", "vagabunda", "pqp", "vsf", "fdp",
           "corno", "otario", "babaca"},
    "en": {"fuck", "fucking", "fucked", "fucker", "motherfucker", "shit", "bullshit", "bitch", "asshole", "dick",
           "cunt", "bastard", "pussy", "whore", "slut"},
    "es": {"mierda", "puta", "puto", "joder", "jodido", "cono", "cabron", "pendejo", "verga", "chingar", "chingada",
           "culero", "gilipollas", "hostia"},
}
VOGAIS = "aeiouáéíóúâêôãõàAEIOUÁÉÍÓÚÂÊÔÃÕÀ"


def mascarar(w: str) -> str:
    """porra → p*rra (troca a primeira vogal depois da 1ª letra)."""
    m = re.match(r"^(\W*)(.*?)(\W*)$", w)
    pre, nucleo, pos = m.groups()
    for i, c in enumerate(nucleo):
        if i > 0 and c in VOGAIS:
            return pre + nucleo[:i] + "*" + nucleo[i + 1:] + pos
    return w


def aplicar_correcoes(ws: list[dict], correcoes: list[dict]) -> list[dict]:
    """Cada correção acha a palavra (ou sequência) mais perto de `t` (±1,5 s) e troca o texto."""
    ws = [dict(w) for w in ws]
    trocas = {}
    for c in correcoes:
        de = [util.normalizar(x) for x in str(c["de"]).split() if util.normalizar(x)]
        if not de:
            continue
        melhor, dist = None, 1.5
        for i in range(len(ws) - len(de) + 1):
            if [util.normalizar(ws[i + k]["w"]) for k in range(len(de))] == de:
                d = abs(ws[i]["s"] - float(c["t"]))
                if d <= dist:
                    melhor, dist = i, d
        if melhor is not None:
            trocas[melhor] = (len(de), str(c.get("para", "")))
    out, i = [], 0
    while i < len(ws):
        if i in trocas:
            n, para = trocas[i]
            s, e = ws[i]["s"], ws[i + n - 1]["e"]
            novas = para.split()
            for k, p in enumerate(novas):
                out.append({"w": p, "s": round(s + k * (e - s) / len(novas), 3), "e": round(s + (k + 1) * (e - s) / len(novas), 3)})
            i += n
        else:
            out.append(ws[i])
            i += 1
    return out


def achar_censuras(ws: list[dict], pedidos: list[dict], idioma: str = "pt", automatico: bool = True) -> list[int]:
    idx = set()
    if automatico:
        lista = PALAVROES.get(idioma, set())
        idx |= {i for i, w in enumerate(ws) if util.normalizar(w["w"]) in lista}
    for p in pedidos:
        alvo = util.normalizar(p.get("palavra", ""))
        perto = [(abs(w["s"] - float(p["t"])), i) for i, w in enumerate(ws)
                 if abs(w["s"] - float(p["t"])) <= 1.5 and (not alvo or util.normalizar(w["w"]).startswith(alvo))]
        if perto:
            idx.add(min(perto)[1])
    return sorted(idx)


def _grade(x: float, fps: int, para_cima: bool) -> float:
    k = math.ceil(x * fps - 1e-6) if para_cima else math.floor(x * fps + 1e-6)
    return k / fps


def calcular_keep(ws: list[dict], trechos, pausa_max: float, fps: int = FPS) -> list[list[float]]:
    keep = []  # [início, fim, começo da palavra seguinte]
    for a, b in trechos:
        dentro = [i for i, w in enumerate(ws) if w["s"] >= a - 0.25 and w["e"] <= b + 0.25 and w["e"] > a and w["s"] < b]
        if not dentro:
            raise util.ErroUsuario(f"o trecho {a}–{b} s não tem fala na transcrição: confira os tempos no transcricao.txt")
        i0, i1 = dentro[0], dentro[-1]
        ini = ws[i0]["s"] - ANTES
        if i0 > 0:
            ini = max(ini, min(ws[i0 - 1]["e"] + 0.01, ws[i0]["s"] - 0.02))
        fim = ws[i1]["e"] + DEPOIS
        if i1 + 1 < len(ws):
            fim = min(fim, max(ws[i1 + 1]["s"] - 0.01, ws[i1]["e"] + 0.02))
        cur, prev_e = ini, None
        for i in range(i0, i1 + 1):
            w = ws[i]
            if prev_e is not None and w["s"] - prev_e > pausa_max:
                keep.append([cur, min(prev_e + 0.14, w["s"] - ANTES), w["s"]])
                cur = w["s"] - ANTES
            prev_e = w["e"]
        keep.append([cur, fim, ws[i1 + 1]["s"] if i1 + 1 < len(ws) else math.inf])
    grade = []
    for s, e, prox in keep:
        fim = _grade(e, fps, True)
        if fim > prox - 0.005:  # para cima entraria no começo da palavra seguinte (legenda sem áudio)
            fim = _grade(e, fps, False)
        grade.append([_grade(max(0.0, s), fps, False), fim])
    juntos = []
    for s, e in grade:
        if juntos and s <= juntos[-1][1] + 1e-9:
            juntos[-1][1] = max(juntos[-1][1], e)
        elif e - s >= 2 / fps - 1e-9:
            juntos.append([s, e])
    return [[round(s * fps) / fps, round(e * fps) / fps] for s, e in juntos]


def refinar_keep(keep, env, pausa_max: float, fps: int = FPS, passo: float = 0.01, folga: float = 0.07):
    """O Whisper às vezes estica uma palavra por cima de um silêncio: a pausa não sai e a legenda fica sem voz.
    Todo silêncio do áudio com pausa_max + 0,15 s ou mais dentro de um pedaço sai, deixando 0,07 s de cada lado."""
    if env is None or not len(env):
        return keep
    _, off = legendas.limiar(env)
    mudo = np.asarray(env) < off
    minimo = pausa_max + 0.15
    out = []
    for s, e in keep:
        pedacos, cur = [], s
        k, k1 = math.ceil(s / passo - 1e-6), min(len(mudo), math.floor(e / passo + 1e-6))
        while k < k1 and cur is not None:
            if not mudo[k]:
                k += 1
                continue
            j = k
            while j < k1 and mudo[j]:
                j += 1
            a, b = k * passo, j * passo
            if b - a >= minimo - 1e-9:
                if a - cur > passo:  # tem voz antes: fecha o pedaço com folga
                    pedacos.append([cur, min(e, _grade(a + folga, fps, True))])
                cur = None if j >= k1 else max(cur, _grade(b - folga, fps, False))
            k = j
        if cur is not None:
            pedacos.append([cur, e])
        pedacos = [[x, y] for x, y in pedacos if y - x >= 2 / fps - 1e-9]
        out += pedacos or [[s, e]]  # pedaço todo "mudo" (limiar errado?): fica como estava
    return [[round(x * fps) / fps, round(y * fps) / fps] for x, y in out]


def palavras_no_corte(ws: list[dict], keep) -> list[dict]:
    """Palavras no tempo do corte final. Só entra a que começa dentro de um pedaço e tem pelo menos
    min(0,08 s, metade dela) lá dentro: a que só encosta no fim do pedaço não tem áudio."""
    out = []
    for w in ws:
        minimo = min(0.08, (w["e"] - w["s"]) / 2)
        dentro = next(((s, e) for s, e in keep
                       if s - 0.01 <= w["s"] <= e and min(w["e"], e) - max(w["s"], s) >= minimo - 1e-9), None)
        if dentro:
            out.append({"w": w["w"], "s": round(remap(keep, w["s"]), 3),
                        "e": round(remap(keep, min(w["e"], dentro[1])), 3), "orig": w["s"],
                        "censura": bool(w.get("censura"))})
    return out


def remap(keep, t: float) -> float:
    acc = 0.0
    for s, e in keep:
        if t < s:
            return acc
        if t <= e:
            return acc + (t - s)
        acc += e - s
    return acc


def linhas_texto(ws: list[dict]) -> list[str]:
    return transcricao.linhas_txt(ws)


def _filtro(keep, censuras_final, espelhar: bool) -> str:
    sel = "+".join(f"between(n\\,{round(s * FPS)}\\,{round(e * FPS) - 1})" for s, e in keep)
    escala = "scale='if(gte(iw,ih),-2,min(iw,1080))':'if(gte(iw,ih),min(ih,1080),-2)'"
    v = f"[0:v]setpts=PTS-STARTPTS,fps={FPS},select='{sel}',setpts=N/{FPS}/TB,{escala}{',hflip' if espelhar else ''},format=yuv420p[vout]"
    n = len(keep)
    partes = [f"[0:a]aresample={SR},aformat=channel_layouts=stereo,asetpts=N/SR/TB,asplit={n}" + "".join(f"[s{i}]" for i in range(n))]
    for i, (s, e) in enumerate(keep):
        a0, a1 = round(s * FPS) * (SR // FPS), round(e * FPS) * (SR // FPS)
        d = (a1 - a0) / SR
        partes.append(f"[s{i}]atrim=start_pts={a0}:end_pts={a1},asetpts=PTS-STARTPTS,"
                      f"afade=t=in:d=0.02,afade=t=out:st={max(0, d - 0.02):.4f}:d=0.02[p{i}]")
    vol = ",".join(f"volume=enable='between(t,{a:.3f},{b:.3f})':volume=0" for a, b in censuras_final) or "anull"
    partes.append("".join(f"[p{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1,{vol},asplit=2[a1][a2]")
    return v + ";" + ";".join(partes)


def base(pasta_corte, rosto: bool = True) -> dict:
    pasta = Path(pasta_corte)
    canal = config.carregar_canal(config.pasta_trabalho(pasta))
    corte = config.carregar_corte(pasta)
    ws = util.ler_json(pasta / "palavras.json", [])
    if not ws:
        raise util.ErroUsuario("a transcrição (palavras.json) está vazia ou não existe: rode o transcrever antes")
    ws = aplicar_correcoes(ws, corte["correcoes"])
    cens = achar_censuras(ws, corte["censurar"], canal["idioma"], canal["opcoes"].get("censurar_palavroes", True))
    for i in cens:
        ws[i] = {**ws[i], "w": mascarar(ws[i]["w"]), "censura": True}
    bruto = pasta / corte.get("bruto", "bruto.mp4")
    keep = calcular_keep(ws, corte["trechos"], corte["pausa_max"])
    keep = refinar_keep(keep, util.envelope_db(bruto, sr=16000), corte["pausa_max"])
    total = round(sum(e - s for s, e in keep), 6)
    cens_final = [[round(remap(keep, ws[i]["s"] - 0.02), 3), round(remap(keep, ws[i]["e"] + 0.02), 3)] for i in cens
                  if any(s - 0.01 <= ws[i]["s"] <= e for s, e in keep)]
    espelhar = bool(corte.get("espelhar", canal["opcoes"].get("espelhar", False)))
    enc = ambiente.encoder_video(pasta=config.pasta_trabalho(pasta))
    if enc[1] == "libx264":
        enc = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "16"]
    util.rodar([util.ffmpeg(), "-v", "error", "-y", "-i", str(bruto),
                "-filter_complex", _filtro(keep, cens_final, espelhar),
                "-map", "[vout]", "-map", "[a1]", *enc, "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", "-ar", str(SR),
                str(pasta / "base.mp4"),
                "-map", "[a2]", "-ac", "1", "-c:a", "pcm_f32le", "-ar", str(SR), str(pasta / "voz.wav")])
    info = util.sondar(pasta / "base.mp4")
    tl_ws = palavras_no_corte(ws, keep)
    util.gravar_json(pasta / "timeline.json", {"duracao": total, "keep": keep, "censuras": cens_final,
                                               "largura": info["largura"], "altura": info["altura"],
                                               "espelhado": espelhar, "palavras": tl_ws})
    (pasta / "timeline.txt").write_text("\n".join(linhas_texto(tl_ws)) + "\n", encoding="utf-8", newline="\n")
    r = {"ok": True, "duracao": total, "pedacos": len(keep), "censuras": len(cens_final),
         "palavras": len(tl_ws), "timeline": str(pasta / "timeline.txt"), "espelhado": espelhar}
    if total > canal["opcoes"].get("max_segundos", 90) + 1:
        r["aviso"] = f"o corte tem {total:.1f} s, acima do máximo de {canal['opcoes']['max_segundos']} s do canal"
    if rosto:
        from . import rosto as mod_rosto
        rr = mod_rosto.rastrear(pasta / "base.mp4", pasta / "rostos.json")
        r["rosto"] = {"planos": len(rr["cortes"]) + 1, "amostras_com_rosto": rr["com_rosto"]}
    return r


def registrar(sub):
    p = sub.add_parser("base", help="monta base.mp4 + timeline (e rastreia o rosto) a partir do corte.json")
    p.add_argument("corte"); p.add_argument("--sem-rosto", action="store_true")
    p.set_defaults(func=lambda a: base(a.corte, rosto=not a.sem_rosto))
