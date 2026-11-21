"""Monta o dados.json do editor, renderiza no Remotion e finaliza: −14 LUFS, BT.709, versão nova sem sobrescrever."""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import sys
import time
from pathlib import Path

from . import ambiente, audio, config, legendas, util

FPS = 30
W, H = 1080, 1920
TOPOS_LEGENDA = [1260, 1100, 1340, 1020]
FUNDO_SEGURO = 1520
DUR_SELO = 4.7


def proxima_versao(pasta_corte) -> int:
    ns = [int(m.group(1)) for p in Path(pasta_corte).glob("final_v*.mp4")
          if (m := re.match(r"final_v(\d+)", p.name))]
    return max(ns, default=0) + 1


def _publicar(src: Path, dst: Path):
    """Coloca o arquivo no public/ do editor (link quando dá, cópia quando não)."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() and dst.stat().st_size == src.stat().st_size and dst.stat().st_mtime >= src.stat().st_mtime:
        return
    dst.unlink(missing_ok=True)
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def _h(txt: str) -> str:
    return hashlib.sha1(txt.encode("utf-8")).hexdigest()[:10]


# ---------- geometria: onde o rosto cai na tela 9:16 ----------
def camera_em(camera, t):
    if not camera:
        return 0.5, 0.4
    ant = camera[0]
    for p in camera:
        if p["t"] > t:
            if p["t"] == ant["t"]:
                return ant["cx"], ant["cy"]
            k = (t - ant["t"]) / (p["t"] - ant["t"])
            return ant["cx"] + k * (p["cx"] - ant["cx"]), ant["cy"] + k * (p["cy"] - ant["cy"])
        ant = p
    return ant["cx"], ant["cy"]


def rosto_na_tela(face, bw, bh, cam):
    """Retângulo (x0, y0, x1, y1) do rosto no quadro 1080x1920, com folga para o zoom lento."""
    k = max(W / bw, H / bh)
    vw, vh = bw * k, bh * k
    left = min(0.0, max(W - vw, W / 2 - cam[0] * vw))
    top = min(0.0, max(H - vh, H / 2 - cam[1] * vh)) if vh > H else 0.0
    cx, cy = left + face["cx"] * vw, top + face["cy"] * vh
    fw, fh = face["w"] * vw * 1.12, face["h"] * vh * 1.12
    return cx - fw / 2, cy - fh / 2, cx + fw / 2, cy + fh / 2


def _cruza(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def caixa_legenda(bloco, top):
    w = legendas._largura(bloco["palavras"], bloco["tam"])
    return W / 2 - w / 2, top, W / 2 + w / 2, top + bloco["tam"] * 1.2


def legenda_em_cima_do_rosto(blocos, top, rostos, limite=0.15):
    """Blocos em que a legenda cobre o rosto em mais de 15% das amostras."""
    if not rostos:
        return []
    bw, bh, cam = rostos["largura"], rostos["altura"], rostos["camera"]
    ruins = []
    for b in blocos:
        a, e = b["f0"] / FPS, b["f1"] / FPS
        amostras = [p for p in rostos.get("principal", []) if a <= p["t"] < e and "cx" in p]
        if not amostras:
            continue
        cx = caixa_legenda(b, top)
        n = sum(1 for p in amostras if _cruza(cx, rosto_na_tela(p, bw, bh, camera_em(cam, p["t"]))))
        if n / len(amostras) > limite:
            ruins.append(b)
    return ruins


def _peito(rostos, top_legenda):
    if not rostos or not rostos.get("principal"):
        return 980
    bw, bh, cam = rostos["largura"], rostos["altura"], rostos["camera"]
    ys = sorted(rosto_na_tela(p, bw, bh, camera_em(cam, p["t"]))[3] for p in rostos["principal"] if "cx" in p)
    if not ys:
        return 980
    return int(max(860, min(top_legenda - 140, ys[len(ys) // 2] + 40)))


# ---------- dados.json ----------
def _biblioteca(pasta_trab, sub, rel):
    return pasta_trab / "biblioteca" / sub / rel


def _sons_da_pasta(pasta_trab, categoria):
    d = pasta_trab / "biblioteca" / "efeitos" / categoria
    return sorted(p for p in d.glob("*") if p.suffix.lower() in (".wav", ".mp3", ".ogg")) if d.exists() else []


def montar_dados(pasta_corte) -> dict:
    pasta = Path(pasta_corte).resolve()
    trab = config.pasta_trabalho(pasta)
    canal = config.carregar_canal(trab)
    corte = config.carregar_corte(pasta, etapa="render")
    ed = corte.get("edicao") or {}
    tl = util.ler_json(pasta / "timeline.json")
    rostos = util.ler_json(pasta / "rostos.json", {}) if (pasta / "rostos.json").exists() else {}
    cid = pasta.name
    pub = trab / "editor" / "public" / cid
    avisos = []
    dur = tl["duracao"]
    frames = round(dur * FPS)
    f = lambda s: max(0, min(frames, round(float(s) * FPS)))  # noqa: E731

    _publicar(pasta / "base.mp4", pub / "base.mp4")
    blocos = legendas.blocos(tl["palavras"], FPS, destaques=ed.get("destaques", []), duracao=dur)
    blocos = legendas.ancorar(blocos, pasta / "voz.wav", FPS, duracao=dur)
    util.gravar_json(pasta / "legendas.json", blocos, indent=None)
    preferido = int(canal["estilo"].get("legenda_top", 1180))
    candidatos = [preferido] + [t for t in TOPOS_LEGENDA if t != preferido]
    top = min(candidatos, key=lambda t: (len(legenda_em_cima_do_rosto(blocos, t, rostos)), candidatos.index(t)))
    cor = ed.get("cor") or canal["estilo"]["cor"]

    sons = []
    for i, ef in enumerate(ed.get("efeitos", [])):
        src = _biblioteca(trab, "efeitos", ef["arquivo"])
        dst = pub / "sfx" / f"{_h(ef['arquivo'])}.wav"
        audio.preparar_efeito(src, dst, dur_max=float(ef.get("dur_max", 3.0)))
        sons.append({"src": f"{cid}/sfx/{dst.name}", "f": f(ef["t"]), "vol": float(ef.get("vol", 0.5))})
    whooshes = _sons_da_pasta(trab, "whoosh")
    imagens = []
    for i, im in enumerate(ed.get("imagens", [])):
        src = pasta / "imagens" / im["arquivo"]
        _publicar(src, pub / "img" / im["arquivo"])
        f0 = f(im["s"])
        imagens.append({"src": f"{cid}/img/{im['arquivo']}", "f0": f0, "f1": max(f0 + 1, f(im["e"])),
                        "entrada": im.get("entrada", "zoom"), "movimento": im.get("movimento", ["in-right", "in-left", "out", "up"][i % 4]),
                        "tremidas": [f(t) for t in im.get("tremidas", [])], "carimbo": im.get("carimbo"),
                        "sepia": bool(im.get("sepia")), "sirene": bool(im.get("sirene"))})
        if whooshes and im.get("whoosh", True):
            w = whooshes[(int(_h(cid), 16) + i) % len(whooshes)]
            dst = pub / "sfx" / f"whoosh_{_h(str(w.name))}.wav"
            audio.preparar_efeito(w, dst, dur_max=1.5)
            sons.append({"src": f"{cid}/sfx/{dst.name}", "f": max(0, f0 - 4), "vol": float(im.get("vol_whoosh", 0.3))})
    bips = _sons_da_pasta(trab, "bip")
    if tl.get("censuras") and bips:
        dst = pub / "sfx" / "bip.wav"
        audio.preparar_efeito(bips[0], dst, dur_max=1.0)
        for a, b in tl["censuras"]:
            sons.append({"src": f"{cid}/sfx/bip.wav", "f": f(a), "vol": 0.5, "dur": max(1, round((b - a) * FPS))})
    elif tl.get("censuras"):
        avisos.append("sem bip na biblioteca (biblioteca/efeitos/bip): o palavrão fica só mudo")

    trilha = None
    tr = ed.get("trilha")
    if tr and tr.get("arquivo"):
        dst = pub / f"trilha_{_h(tr['arquivo'] + str(dur))}.wav"
        if not dst.exists():
            audio.trilha_com_ducking(_biblioteca(trab, "trilhas", tr["arquivo"]), pasta / "voz.wav", dur, dst,
                                     alvo=float(tr.get("lufs", -29)))
        trilha = {"src": f"{cid}/{dst.name}", "vol": 1.0}
    else:
        tem = any((trab / "biblioteca" / "trilhas").rglob("*.mp3")) or any((trab / "biblioteca" / "trilhas").rglob("*.wav"))
        avisos.append("corte sem trilha" + ("" if tem else " (a biblioteca de trilhas está vazia: rode o kit do Mixkit no comecar)"))

    g = ed.get("gancho")
    marca_top = _peito(rostos, top)
    dados = {
        "fps": FPS, "duracaoFrames": frames,
        "base": {"src": f"{cid}/base.mp4", "largura": tl["largura"], "altura": tl["altura"]},
        "camera": [{"f": f(p["t"]), "cx": p["cx"], "cy": p["cy"]} for p in rostos.get("camera", [])] or [{"f": 0, "cx": 0.5, "cy": 0.4}],
        "zoom": bool(canal["estilo"].get("zoom", True)), "cor": cor,
        "legenda": {"top": top, "blocos": [{k: b[k] for k in ("f0", "f1", "tam", "palavras")} for b in blocos]},
        "gancho": {"texto": g["texto"], "emoji": g.get("emoji"), "f0": 0, "f1": f(g.get("ate", 3.0))} if g else None,
        "credito": {"texto": ed["credito"], "f1": f(4.6)} if ed.get("credito") else None,
        "imagens": imagens,
        "etiquetas": [{"f0": f(e["s"]), "f1": f(e["e"]), "texto": e["texto"], "emoji": e.get("emoji"), "top": int(e.get("top", 300))}
                      for e in ed.get("etiquetas", [])],
        "marca": {"texto": canal["arroba"].upper(), "top": marca_top, "opacidade": float(canal["estilo"].get("marca_opacidade", 0.08))}
        if canal.get("arroba") else None,
        "sons": sons, "trilha": trilha, "selo": None,
    }
    for b in dados["legenda"]["blocos"]:
        for p in b["palavras"]:
            p.pop("s", None)
            p.pop("e", None)
    util.gravar_json(pasta / "dados.json", dados, indent=None)
    dados["_avisos"] = avisos
    dados["_marca_top"] = marca_top
    return dados


# ---------- render ----------
def _env_tmp(trab: Path) -> dict:
    tmp = trab / ".fabrica" / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    return dict(os.environ, TEMP=str(tmp), TMP=str(tmp))


def _npx_render(editor: Path, comp: str, saida: Path, extra: list[str], env):
    args = ["npx", "remotion", "render", "src/index.ts", comp, str(saida), *extra, "--log=error"]
    if sys.platform == "win32":
        args.append("--gl=angle")
    util.rodar(args, cwd=editor, env=env, timeout=7200)


COR = ["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv"]
BSF = "h264_metadata=colour_primaries=1:transfer_characteristics=1:matrix_coefficients=1:video_full_range_flag=0"


def _encoder_final(trab):
    enc = ambiente.encoder_video(pasta=trab)
    if enc[1] == "libx264":
        return ["-c:v", "libx264", "-preset", "slow", "-crf", "17", "-profile:v", "high", "-level", "4.2"]
    return enc + ["-profile:v", "high"]


def _selo(trab, editor, env, lado, cor) -> Path:
    cache = trab / ".fabrica" / "selo" / f"selo_{lado}_{cor.strip('#')}.mov"
    if not cache.exists():
        cache.parent.mkdir(parents=True, exist_ok=True)
        _npx_render(editor, "Selo", cache, ["--codec=prores", "--prores-profile=4444", "--pixel-format=yuva444p10le",
                                            f'--props={{"lado":"{lado}","cor":"{cor}"}}'], env)
    return cache


def render(pasta_corte, revisar: bool = True) -> dict:
    pasta = Path(pasta_corte).resolve()
    trab = config.pasta_trabalho(pasta)
    canal = config.carregar_canal(trab)
    editor = trab / "editor"
    if not (editor / "node_modules").exists():
        raise util.ErroUsuario("o editor ainda não tem as dependências: rode o preparar (npm install) antes")
    t0 = time.time()
    dados = montar_dados(pasta)
    avisos = dados.pop("_avisos")
    marca_top = dados.pop("_marca_top")
    env = _env_tmp(trab)
    n = proxima_versao(pasta)
    tmp = trab / ".fabrica" / "tmp"
    mov, mix, master, enc_tmp = (tmp / f"{pasta.name}_v{n}{s}" for s in (".mov", "_mix.wav", "_master.wav", "_enc.mp4"))
    _npx_render(editor, "Corte", mov, [f"--props={pasta / 'dados.json'}", "--codec=h264", "--crf=14", "--audio-codec=pcm-16"], env)
    t_render = time.time() - t0
    util.rodar([util.ffmpeg(), "-v", "error", "-y", "-i", str(mov), "-vn", "-c:a", "pcm_f32le", str(mix)])
    I, TP = audio.masterizar(mix, master)
    vf = "scale=in_range=pc:out_range=tv:in_color_matrix=bt601:out_color_matrix=bt709:flags=accurate_rnd+full_chroma_int,format=yuv420p"
    enc = _encoder_final(trab)
    util.rodar([util.ffmpeg(), "-v", "error", "-y", "-i", str(mov), "-i", str(master), "-map", "0:v", "-map", "1:a",
                "-vf", vf, *enc, *COR, "-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-movflags", "+faststart", str(enc_tmp)])
    final = pasta / f"final_v{n}.mp4"
    util.rodar([util.ffmpeg(), "-v", "error", "-y", "-i", str(enc_tmp), "-map", "0", "-c", "copy", "-bsf:v", BSF,
                "-movflags", "+faststart", str(final)])
    r = {"ok": True, "final": str(final), "versao": n, "duracao": round(dados["duracaoFrames"] / FPS, 2),
         "lufs": I, "pico_dbtp": TP, "render_s": round(t_render), "avisos": avisos}
    if canal["opcoes"].get("selo"):
        sel = (config.carregar_corte(pasta, "render").get("edicao") or {}).get("selo")             or {"inicio": min(20.0, r["duracao"] / 3), "lado": "esq"}
        mov_selo = _selo(trab, editor, env, sel.get("lado", "esq"), sel.get("cor", dados["cor"]))
        y = max(0, int(sel.get("top", marca_top - 35)))
        fc = (f"[1:v]scale=out_color_matrix=bt709:out_range=tv,format=yuva420p,setpts=PTS-STARTPTS+{float(sel['inicio']):.3f}/TB[s];"
              f"[0:v][s]overlay=0:{y}:eof_action=pass,format=yuv420p[v]")
        com = pasta / f"final_v{n}_selo.mp4"
        util.rodar([util.ffmpeg(), "-v", "error", "-y", "-i", str(final), "-i", str(mov_selo), "-filter_complex", fc,
                    "-map", "[v]", "-map", "0:a", *enc, *COR, "-c:a", "copy", "-movflags", "+faststart", str(enc_tmp)])
        util.rodar([util.ffmpeg(), "-v", "error", "-y", "-i", str(enc_tmp), "-map", "0", "-c", "copy", "-bsf:v", BSF,
                    "-movflags", "+faststart", str(com)])
        r["final_selo"] = str(com)
    for p in (mov, mix, master, enc_tmp):
        p.unlink(missing_ok=True)
    r["total_s"] = round(time.time() - t0)
    if revisar:
        from . import revisao
        rv = revisao.revisar(final, pasta)
        r["revisao"] = {"aprovado": rv["aprovado"], "erros": rv["erros"][:8], "avisos": rv["avisos"][:6],
                        "relatorio": rv["relatorio"]}
        r["reprovado"] = not rv["aprovado"]
    return r


def registrar(sub):
    p = sub.add_parser("render", help="monta, renderiza, finaliza (−14 LUFS, BT.709) e revisa: cortes/NNN/final_vN.mp4")
    p.add_argument("corte"); p.add_argument("--sem-revisao", action="store_true")
    p.set_defaults(func=lambda a: render(a.corte, revisar=not a.sem_revisao))
    d = sub.add_parser("dados", help="só monta o dados.json (sem renderizar), para conferir")
    d.add_argument("corte")
    d.set_defaults(func=lambda a: {"ok": True, "avisos": montar_dados(a.corte)["_avisos"]})
