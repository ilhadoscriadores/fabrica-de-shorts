import numpy as np
import pytest

from fabrica import audio, util


def _gerar(tmp_path, nome, filtro, dur):
    p = tmp_path / nome
    util.rodar([util.ffmpeg(), "-v", "error", "-y", "-f", "lavfi", "-i", f"{filtro}:d={dur}", "-ar", "48000", str(p)])
    return p


def test_masterizar_chega_em_menos_14(tmp_path):
    ruido = _gerar(tmp_path, "rosa.wav", "anoisesrc=c=pink:a=0.05", 20)
    I0, _ = audio.medir(ruido)
    assert I0 < -20
    out = tmp_path / "m.wav"
    audio.masterizar(ruido, out)
    I, TP = audio.medir(out)
    assert I == pytest.approx(-14, abs=0.5)
    assert TP <= -1.0


def test_preparar_efeito_corta_e_normaliza(tmp_path):
    src = _gerar(tmp_path, "e.wav", "sine=f=500", 6)
    dst = tmp_path / "e2.wav"
    audio.preparar_efeito(src, dst, dur_max=2.0)
    info = util.sondar(dst)
    assert info["duracao"] == pytest.approx(2.0, abs=0.05)


def test_ducking_abaixa_sob_a_voz(tmp_path):
    musica = _gerar(tmp_path, "mus.wav", "sine=f=330", 4)
    voz = tmp_path / "voz.wav"
    util.rodar([util.ffmpeg(), "-v", "error", "-y", "-f", "lavfi", "-i", "sine=f=200:d=10",
                "-af", "volume='if(between(t,4,7),0.3,0)':eval=frame", "-ac", "1", "-ar", "48000", str(voz)])
    out = tmp_path / "tri.wav"
    audio.trilha_com_ducking(musica, voz, 10.0, out)
    assert util.sondar(out)["duracao"] == pytest.approx(10.0, abs=0.03)
    env = util.envelope_db(out)
    fora, dentro = env[100:350].mean(), env[450:650].mean()
    assert fora - dentro >= 6  # abaixa quando a voz fala
    assert fora < -20  # trilha baixinha
