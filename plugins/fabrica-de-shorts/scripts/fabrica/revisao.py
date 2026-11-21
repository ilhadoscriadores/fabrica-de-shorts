"""Revisão automática de todo vídeo antes da entrega (porta do revisao_frames.py do canal de GTA 6).

Confere imagem e som quadro a quadro e, num corte da fábrica, a legenda contra a voz, o rosto e os palavrões."""
from __future__ import annotations

import difflib
import json
from pathlib import Path

import numpy as np

from . import audio, legendas, montagem, util

FPS = 30


def _quadros(video, largura=108):
    info = util.sondar(video)
    h = max(2, int(round(largura * info["altura"] / info["largura"] / 2)) * 2)
    raw = util.rodar_bytes([util.ffmpeg(), "-v", "error", "-i", str(video), "-vf", f"scale={largura}:{h}",
                            "-f", "rawvideo", "-pix_fmt", "gray", "-"])
    return np.frombuffer(raw, np.uint8).reshape(-1, h, largura).astype(np.float32), info


def _faixas(idx, fps=FPS, minimo=1):
    """Índices de quadro → trechos 'a–b s'."""
    out, ini, ant = [], None, None
    for i in list(idx) + [None]:
        if i is not None and ant is not None and i == ant + 1:
            ant = i
            continue
        if ini is not None and ant - ini + 1 >= minimo:
            out.append((ini / fps, (ant + 1) / fps))
        ini = ant = i
    return out


def _fora(ign, a, b):
    return not any(x <= a and b <= y for x, y in ign)


def _transcrever_final(video):
    from . import transcricao
    tmp = Path(video).with_suffix(".revisao.words.json")
    try:
        return transcricao.transcrever(video, tmp, modelo="base")
    finally:
        tmp.unlink(missing_ok=True)
        tmp.with_suffix(".txt").unlink(missing_ok=True)


def segunda_conferencia(blocos, palavras_final, limite=0.25):
    """Compara o começo de cada bloco com a mesma palavra na transcrição do vídeo pronto (com música por baixo)."""
    ref, idx_bloco = [], {}
    for bi, b in enumerate(blocos):
        for k, p in enumerate(b["palavras"]):
            if k == 0:
                idx_bloco[len(ref)] = bi
            ref.append(util.normalizar(p["w"]))
    hip = [util.normalizar(w["w"]) for w in palavras_final]
    sm = difflib.SequenceMatcher(None, ref, hip, autojunk=False)
    probs = []
    for blk in sm.get_matching_blocks():
        for k in range(blk.size):
            i = blk.a + k
            if i in idx_bloco:
                b = blocos[idx_bloco[i]]
                t_leg, t_voz = b["f0"] / FPS, palavras_final[blk.b + k]["s"]
                if abs(t_leg - t_voz) > limite and not b["palavras"][0].get("censura"):
                    texto = " ".join(p["w"] for p in b["palavras"])
                    probs.append(f"legenda \"{texto}\" em {t_leg:.2f}s está {abs(t_leg - t_voz) * 1000:.0f} ms "
                                 f"{'antes' if t_leg < t_voz else 'depois'} da voz no vídeo pronto (2ª conferência)")
    return probs


def revisar(video, pasta_corte=None, transcrever_de_novo: bool = True) -> dict:
    video = Path(video)
    erros, avisos, ok = [], [], []
    pasta = Path(pasta_corte) if pasta_corte else None
    corte = util.ler_json(pasta / "corte.json", {}) if pasta and (pasta / "corte.json").exists() else {}
    ign = [tuple(x) for x in (corte.get("revisao") or {}).get("ignorar", [])]

    # ---- som e tamanho ----
    q, info = _quadros(video)
    fps = info.get("fps", FPS) or FPS
    dv, da = info.get("duracao_video", 0), info.get("duracao_audio")
    if da is None:
        erros.append("o vídeo não tem som")
    elif abs(dv - da) > 1 / fps + 0.025:
        erros.append(f"áudio e vídeo de tamanho diferente: vídeo {dv:.3f}s, áudio {da:.3f}s")
    else:
        ok.append(f"áudio e vídeo do mesmo tamanho ({dv:.2f} s)")
    if da is not None:
        pts = util.rodar([util.ffprobe(), "-v", "error", "-select_streams", "a", "-show_entries", "packet=pts_time",
                          "-of", "csv=p=0", str(video)]).stdout.split()
        ts = [float(x.strip(",")) for x in pts if x.strip(",") not in ("", "N/A")]
        saltos = [f"{a:.2f}s" for a, b in zip(ts, ts[1:]) if b - a > 0.03]
        (erros.append(f"saltos no tempo do áudio em {', '.join(saltos[:5])}") if saltos
         else ok.append("áudio contínuo, sem saltos de tempo"))
        I, TP = audio.medir(video)
        if not -15.0 <= I <= -13.0:
            erros.append(f"volume fora do padrão: {I:.1f} LUFS (o certo é −14 ±1)")
        if TP > -0.95:
            erros.append(f"pico alto demais: {TP:.1f} dBTP (o máximo é −1): pode estourar")
        if -15.0 <= I <= -13.0 and TP <= -0.95:
            ok.append(f"volume {I:.1f} LUFS, pico {TP:.1f} dBTP")

    # ---- imagem quadro a quadro ----
    luma = q.mean(axis=(1, 2))
    pretos = [f for f in _faixas(np.where(luma < 10)[0], fps) if _fora(ign, *f)]
    dif = np.r_[np.inf, np.abs(np.diff(q, axis=0)).mean(axis=(1, 2))]
    congelados = [f for f in _faixas(np.where(dif < 0.05)[0], fps, minimo=12) if _fora(ign, *f)]
    (erros.append("quadro preto em " + ", ".join(f"{a:.2f}–{b:.2f}s" for a, b in pretos[:5])) if pretos
     else ok.append("nenhum quadro preto"))
    (erros.append("imagem congelada em " + ", ".join(f"{a:.2f}–{b:.2f}s" for a, b in congelados[:5])) if congelados
     else ok.append("nenhuma imagem congelada"))

    # ---- corte da fábrica: legenda, rosto, palavrão, área segura ----
    if pasta and (pasta / "legendas.json").exists():
        blocos = util.ler_json(pasta / "legendas.json")
        dados = util.ler_json(pasta / "dados.json", {})
        tl = util.ler_json(pasta / "timeline.json", {})
        rostos = util.ler_json(pasta / "rostos.json", {}) if (pasta / "rostos.json").exists() else {}
        env = util.envelope_db(pasta / "voz.wav")
        probs = legendas.conferir(blocos, None, FPS, env=env)
        for p in probs[:12]:
            erros.append(f"legenda \"{p['texto']}\" em {p['t']:.2f}s: {p['problema']}")
        if len(probs) > 12:
            erros.append(f"... e mais {len(probs) - 12} blocos de legenda fora da voz")
        if not probs:
            ok.append(f"legenda na voz: {len(blocos)} blocos a menos de 80 ms da voz limpa")
        if transcrever_de_novo:
            seg = segunda_conferencia(blocos, _transcrever_final(video))
            erros += seg[:8]
            if not seg:
                ok.append("2ª conferência (Whisper no vídeo pronto): nenhuma legenda a mais de 250 ms")
        top = (dados.get("legenda") or {}).get("top", 1180)
        if rostos:
            cobre = montagem.legenda_em_cima_do_rosto(blocos, top, rostos)
            (erros.append(f"legenda em cima do rosto em {len(cobre)} blocos (ex.: {cobre[0]['f0'] / FPS:.1f}s)") if cobre
             else ok.append("legenda nunca cobre o rosto"))
            cortado = _rosto_cortado(rostos)
            (erros.append("rosto cortado pela borda em " + ", ".join(cortado[:4])) if cortado
             else ok.append("rosto sempre dentro do quadro 9:16"))
            for e in dados.get("etiquetas", []):
                cx = (40, e["top"], 1040, e["top"] + 110)
                am = [p for p in rostos.get("principal", []) if "cx" in p and e["f0"] / FPS <= p["t"] < e["f1"] / FPS]
                if am and sum(_cruza(cx, montagem.rosto_na_tela(p, rostos["largura"], rostos["altura"],
                              montagem.camera_em(rostos["camera"], p["t"]))) for p in am) / len(am) > 0.15:
                    erros.append(f"etiqueta \"{e['texto']}\" em cima do rosto em {e['f0'] / FPS:.1f}s")
        vaza = []
        for a, b in tl.get("censuras", []):
            trecho = env[int((a + 0.03) * 100): max(int((a + 0.03) * 100) + 1, int((b - 0.03) * 100))]
            if len(trecho) and trecho.max() > -50:
                vaza.append(f"{a:.2f}s")
        if vaza:
            erros.append("palavrão com som em " + ", ".join(vaza))
        elif tl.get("censuras"):
            ok.append(f"{len(tl['censuras'])} palavrões mudos")
        maior = max((b["tam"] for b in blocos), default=92)
        if top + maior * 1.2 > montagem.FUNDO_SEGURO:
            erros.append(f"legenda abaixo da área segura do Shorts (passa de y {montagem.FUNDO_SEGURO})")
        for e in dados.get("etiquetas", []):
            if e["top"] < 150 or e["top"] + 110 > montagem.FUNDO_SEGURO:
                avisos.append(f"etiqueta \"{e['texto']}\" perto da borda (y {e['top']}): pode ficar embaixo dos botões do app")
        largas = [b for b in blocos if legendas._largura(b["palavras"], b["tam"]) > 900]
        if largas:
            avisos.append(f"{len(largas)} blocos de legenda passam de 900 px: podem encostar nos botões do lado direito")
        for a in (util.ler_json(pasta / "avisos_render.json", []) if (pasta / "avisos_render.json").exists() else []):
            avisos.append(a)

    aprovado = not erros
    destino = (pasta or video.parent) / "revisao.md"
    linhas = [f"# Revisão automática · {video.name}", "",
              f"**Resultado: {'APROVADO' if aprovado else f'REPROVADO ({len(erros)} problemas)'}**", ""]
    if erros:
        linhas += ["## Problemas (corrigir antes de postar)"] + [f"- {e}" for e in erros] + [""]
    if avisos:
        linhas += ["## Avisos"] + [f"- {a}" for a in avisos] + [""]
    linhas += ["## Conferido e ok"] + [f"- {o}" for o in ok]
    destino.write_text("\n".join(linhas) + "\n", encoding="utf-8", newline="\n")
    r = {"ok": True, "aprovado": aprovado, "erros": erros, "avisos": avisos, "conferido": ok, "relatorio": str(destino)}
    util.gravar_json(destino.with_suffix(".json"), r)
    return r


def _cruza(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _rosto_cortado(rostos):
    """Rosto principal saindo mais de 10% pela lateral do quadro 9:16 em mais de 20% das amostras do plano."""
    bw, bh, cam = rostos["largura"], rostos["altura"], rostos["camera"]
    ruins = []
    marcas = [0.0] + list(rostos.get("cortes", [])) + [1e9]
    for a, b in zip(marcas, marcas[1:]):
        am = [p for p in rostos.get("principal", []) if "cx" in p and a <= p["t"] < b]
        if not am:
            continue
        fora = 0
        for p in am:
            x0, _, x1, _ = montagem.rosto_na_tela(p, bw, bh, montagem.camera_em(cam, p["t"]))
            folga = (x1 - x0) * 0.1
            if x0 < -folga or x1 > montagem.W + folga:
                fora += 1
        if fora / len(am) > 0.2:
            ruins.append(f"{a:.1f}s")
    return ruins


def registrar(sub):
    p = sub.add_parser("revisar", help="revisão automática de um vídeo (com --corte confere legenda, rosto e palavrões)")
    p.add_argument("video"); p.add_argument("--corte"); p.add_argument("--rapida", action="store_true",
                                                                       help="pula a 2ª transcrição")

    def cmd(a):
        r = revisar(a.video, a.corte, transcrever_de_novo=not a.rapida)
        r["reprovado"] = not r["aprovado"]
        return r
    p.set_defaults(func=cmd)
