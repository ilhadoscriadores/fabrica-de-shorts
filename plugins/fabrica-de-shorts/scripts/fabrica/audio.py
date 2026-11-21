"""Som: efeitos prontos para a edição, trilha que abaixa sob a voz e o master em -14 LUFS."""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import util

SR = 48000


def medir(arquivo) -> tuple[float, float]:
    """(loudness integrado em LUFS, pico verdadeiro em dBTP)."""
    r = util.rodar([util.ffmpeg(), "-hide_banner", "-nostats", "-i", str(arquivo), "-vn",
                    "-af", "ebur128=peak=true", "-f", "null", "-"])
    txt = r.stderr
    resumo = txt[txt.rfind("Summary:"):] if "Summary:" in txt else txt
    I = float(re.findall(r"I:\s+(-?[\d.]+|-inf) LUFS", resumo)[-1].replace("-inf", "-70"))
    picos = re.findall(r"Peak:\s+(-?[\d.]+|-inf) dBFS", resumo)
    TP = float(picos[-1].replace("-inf", "-70")) if picos else 0.0
    return I, TP


def preparar_efeito(src, dst, dur_max: float = 3.0):
    """Corta o silêncio do começo, limita o tamanho, faz fade e deixa todos no mesmo volume."""
    src, dst = Path(src), Path(dst)
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
        return dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    af = (f"silenceremove=start_periods=1:start_threshold=-45dB,atrim=0:{dur_max},"
          f"afade=t=out:st={max(0.0, dur_max - 0.15):.3f}:d=0.15,loudnorm=I=-16:TP=-1.5")
    util.rodar([util.ffmpeg(), "-v", "error", "-y", "-i", str(src), "-af", af, "-ar", str(SR), "-ac", "2",
                "-c:a", "pcm_s16le", str(dst)])
    return dst


def trilha_com_ducking(musica, voz_wav, duracao: float, dst, alvo: float = -29.0):
    """Trilha em loop no tamanho do corte, com EQ abrindo espaço para a voz e abaixando quando a pessoa fala."""
    I, _ = medir(musica)
    ganho = max(-40.0, min(20.0, alvo - I))
    I_voz, _ = medir(voz_wav)  # o limiar acompanha o volume da voz (podcast gravado baixo também abaixa a trilha)
    limiar = min(0.5, max(0.001, 10 ** ((I_voz - 12) / 20)))
    fc = (f"[0:a]aresample={SR},aformat=channel_layouts=stereo,asetpts=N/SR/TB,"
          f"highpass=f=60,equalizer=f=2500:t=o:w=1:g=-5,volume={ganho:.2f}dB[m];"
          f"[1:a]aresample={SR},aformat=channel_layouts=stereo,asetpts=N/SR/TB,apad[v];"
          f"[m][v]sidechaincompress=threshold={limiar:.5f}:ratio=6:attack=20:release=400:makeup=1,"
          f"atrim=end_sample={round(duracao * SR)}[out]")
    util.rodar([util.ffmpeg(), "-v", "error", "-y", "-stream_loop", "-1", "-i", str(musica), "-i", str(voz_wav),
                "-filter_complex", fc, "-map", "[out]", "-t", f"{duracao:.3f}", "-c:a", "pcm_s16le", str(dst)])
    return dst


def _loudnorm_json(arquivo) -> dict:
    r = util.rodar([util.ffmpeg(), "-hide_banner", "-nostats", "-i", str(arquivo), "-vn",
                    "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"])
    bloco = r.stderr[r.stderr.rfind("{"): r.stderr.rfind("}") + 1]
    return json.loads(bloco)


def masterizar(wav_in, wav_out, alvo: float = -14.0, teto: float = -1.0) -> tuple[float, float]:
    """Loudnorm em 2 passadas e até 2 acertos de ganho: −14 ±0,5 LUFS e pico ≤ −1 dBTP."""
    m = _loudnorm_json(wav_in)
    af = (f"loudnorm=I={alvo}:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
          f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    atual = Path(wav_out).with_suffix(".passo1.wav")
    util.rodar([util.ffmpeg(), "-v", "error", "-y", "-i", str(wav_in), "-af", af, "-ar", str(SR), "-c:a", "pcm_f32le", str(atual)])
    I, TP = medir(atual)
    for i in range(2):
        if abs(I - alvo) <= 0.5 and TP <= teto:
            break
        prox = Path(wav_out).with_suffix(f".passo{i + 2}.wav")
        util.rodar([util.ffmpeg(), "-v", "error", "-y", "-i", str(atual),
                    "-af", f"volume={alvo - I:.2f}dB,alimiter=limit=0.82:level=0:attack=3:release=60",
                    "-ar", str(SR), "-c:a", "pcm_f32le", str(prox)])
        atual.unlink(missing_ok=True)
        atual = prox
        I, TP = medir(atual)
    Path(wav_out).unlink(missing_ok=True)
    atual.replace(wav_out)
    return I, TP
