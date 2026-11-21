import json
import subprocess

import pytest

from fabrica import util


def test_rodar_caminho_com_acento(tmp_path):
    pasta = tmp_path / "Shorts automático" / "Gabriel Dias"
    pasta.mkdir(parents=True)
    saida = pasta / "saída teste.wav"
    util.rodar([util.ffmpeg(), "-v", "error", "-y", "-f", "lavfi", "-i", "sine=d=0.2", str(saida)])
    assert saida.exists() and saida.stat().st_size > 1000


def test_rodar_erro_mostra_o_comando(tmp_path):
    with pytest.raises(util.ErroComando) as e:
        util.rodar([util.ffmpeg(), "-v", "error", "-i", str(tmp_path / "nao-existe.mp4"), "-f", "null", "-"])
    assert "ffmpeg" in str(e.value)


def test_resultado_imprime_json(capsys):
    with pytest.raises(SystemExit) as e:
        util.resultado({"ok": True, "pasta": "Shorts automático"})
    assert e.value.code == 0
    linha = capsys.readouterr().out.strip().splitlines()[-1]
    assert linha.startswith("RESULTADO: ")
    assert json.loads(linha[len("RESULTADO: "):]) == {"ok": True, "pasta": "Shorts automático"}


def test_envelope_db_de_tom_e_silencio(tmp_path):
    wav = tmp_path / "a.wav"
    util.rodar([util.ffmpeg(), "-v", "error", "-y", "-f", "lavfi", "-i",
                "sine=f=440:d=0.5,apad=pad_dur=0.5", "-ar", "48000", "-ac", "1", str(wav)])
    env = util.envelope_db(wav)
    assert len(env) == pytest.approx(100, abs=2)
    assert env[10:40].mean() > -30
    assert env[60:90].mean() < -80
