"""Achar o trecho pelo SOM: para corte de live (Twitch, Kick) ou vídeo sem legenda.

Baixa só o áudio da VOD (~90 MB por hora), compara pedaços de 5 s do corte modelo com a VOD inteira
(correlação normalizada, a 2 kHz) e devolve onde o corte começa. Três pedaços concordando = achou.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from . import util

SR = 2000            # 2 kHz basta para casar o mesmo áudio e deixa 8 h de live em ~230 MB de memória
JANELA = 5.0         # segundos de cada pedaço do corte
PONTOS = (0.35, 0.55, 0.75)  # de onde saem os pedaços (fração do corte): longe do começo, que costuma ter vinheta
CORR_MIN = 0.3       # correlação mínima de um pedaço (o mesmo áudio dá 0,5 a 1; áudio diferente dá ~0,1)
CONCORDA = 1.5       # dois pedaços concordam se apontam o mesmo começo com essa folga (s)
BLOCO = SR * 600     # a VOD é varrida em blocos de 10 min


def e_youtube(url: str) -> bool:
    return any(x in (url or "") for x in ("youtube.com", "youtu.be"))


def melhor_correlacao(ep: np.ndarray, ref: np.ndarray) -> tuple[float, float]:
    """(correlação, segundo na VOD) do melhor encaixe de `ref` (já sem média e com norma 1) em `ep`."""
    n = len(ref)
    melhor = (0.0, 0.0)
    if len(ep) < n:
        return melhor
    for st in range(0, len(ep) - n + 1, BLOCO):
        x = ep[st:st + BLOCO + n].astype(np.float64)
        if len(x) < n:
            break
        tam = 1 << int(np.ceil(np.log2(len(x) + n)))
        c = np.fft.irfft(np.fft.rfft(x, tam) * np.conj(np.fft.rfft(ref, tam)), tam)[:len(x) - n + 1]
        acum = np.concatenate([[0.0], np.cumsum(x * x)])
        energia = np.sqrt(np.maximum(acum[n:] - acum[:-n], 1e-12))[:len(c)]
        cc = np.where(energia > 1e-4, c / energia, 0.0)  # trecho mudo (VOD silenciada) não conta
        i = int(np.argmax(cc))
        if cc[i] > melhor[0]:
            melhor = (float(cc[i]), (st + i) / SR)
    return melhor


def localizar(ref: np.ndarray, ep: np.ndarray, folga: float = 2.0) -> list[dict]:
    """Onde o corte modelo (ref) está na VOD (ep), os dois mono a SR. Melhores primeiro (lista vazia = não achou)."""
    dur = len(ref) / SR
    jan = JANELA if dur >= JANELA * 2 else max(1.5, dur / 3)
    achados = []
    for f in PONTOS:
        s = min(max(0.0, dur * f - jan / 2), max(0.0, dur - jan))
        r = ref[int(s * SR):int((s + jan) * SR)].astype(np.float64)
        r = r - r.mean()
        norma = np.linalg.norm(r)
        if norma < 1e-6:  # pedaço mudo no corte
            continue
        corr, t = melhor_correlacao(ep, r / norma)
        if corr >= CORR_MIN:
            achados.append((t - s, corr))
    grupos: list[list[tuple[float, float]]] = []
    for ini, corr in sorted(achados):
        if grupos and ini - grupos[-1][-1][0] <= CONCORDA:
            grupos[-1].append((ini, corr))
        else:
            grupos.append([(ini, corr)])
    out = []
    for g in grupos:
        melhor_corr = max(c for _, c in g)
        if len(g) < 2 and melhor_corr < 0.5:  # um pedaço sozinho só vale se o encaixe for muito bom
            continue
        ini = sorted(i for i, _ in g)[len(g) // 2]
        a, b = max(0.0, ini - folga), ini + dur + folga
        out.append({"inicio": round(a, 1), "fim": round(b, 1), "acertos": len(g), "cobertura": round(len(g) / len(PONTOS), 2),
                    "correlacao": round(melhor_corr, 2), "inicio_hms": _hms(a), "fim_hms": _hms(b), "por": "audio"})
    return sorted(out, key=lambda r: (-r["acertos"], -r["correlacao"]))


def _hms(s: float) -> str:
    s = int(s)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}"


def baixar_audio(url: str, pasta, ydl) -> Path:
    """Só o som do vídeo (formato de áudio da Twitch/Kick ou o pior vídeo), guardado em <pasta>/<id>.audio.*"""
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    with ydl({"quiet": True, "no_warnings": True, "noprogress": True, "skip_download": True}) as y:
        info = y.extract_info(url, download=False)
    vid = info.get("id", "video")
    # o áudio já baixado (aqui ou pelo `legenda --transcrever`, que grava <id>.m4a) é reaproveitado
    prontos = [p for p in pasta.glob(f"{vid}.*") if p.suffix.lower() in (".m4a", ".mp4", ".webm", ".opus", ".mp3", ".aac")
               and (p.name.startswith(f"{vid}.audio.") or p.name == f"{vid}{p.suffix}")]
    if prontos:
        return prontos[0]
    opts = {"quiet": True, "no_warnings": True, "noprogress": True, "format": "bestaudio/worst",
            "concurrent_fragment_downloads": 8, "outtmpl": {"default": str(pasta / f"{vid}.audio.%(ext)s")}}
    with ydl(opts) as y:
        y.extract_info(url, download=True)
    prontos = [p for p in pasta.glob(f"{vid}.audio.*") if p.suffix not in (".part", ".ytdl")]
    if not prontos:
        raise util.ErroComando(f"não consegui baixar o áudio de {url}")
    return prontos[0]


def ler(caminho) -> np.ndarray:
    return util.ler_audio(caminho, sr=SR)
