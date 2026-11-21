import json
import os
import subprocess

import pytest

from fabrica import util


def test_rodar_caminho_com_acento(tmp_path):
    pasta = tmp_path / "Shorts automático" / "Gabriel Dias"
    pasta.mkdir(parents=True)
    saida = pasta / "saída teste.wav"
    util.rodar([util.ffmpeg(), "-v", "error", "-y", "-f", "lavfi", "-i", "sine=d=0.2", str(saida)])
    assert saida.exists() and saida.stat().st_size > 1000


def _pastas_do_winget(tmp_path, monkeypatch):
    """LOCALAPPDATA e ProgramFiles falsos e um PATH que não acha nada (sessão aberta antes do winget)."""
    local, pf = tmp_path / "Local", tmp_path / "Arquivos de Programas"
    (pf / "nodejs").mkdir(parents=True)
    (local / "Microsoft" / "WinGet" / "Links").mkdir(parents=True)
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setenv("ProgramFiles", str(pf))
    monkeypatch.delenv("FABRICA_FFMPEG", raising=False)
    monkeypatch.setattr(util.shutil, "which", lambda *a, **k: None)
    return local, pf


@pytest.mark.skipif(os.name != "nt", reason="winget só existe no Windows")
def test_acha_ffmpeg_e_node_do_winget_fora_do_path(tmp_path, monkeypatch):
    local, pf = _pastas_do_winget(tmp_path, monkeypatch)
    with pytest.raises(util.ErroUsuario):
        util.ffmpeg()
    binario = local / "Microsoft" / "WinGet" / "Packages" / "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe" / "ffmpeg-8.0-full_build" / "bin"
    binario.mkdir(parents=True)
    for n in ("ffmpeg.exe", "ffprobe.exe"):
        (binario / n).write_bytes(b"x")
    (pf / "nodejs" / "node.exe").write_bytes(b"x")
    (pf / "nodejs" / "npx.cmd").write_text("x")
    assert util.ffmpeg() == str(binario / "ffmpeg.exe")
    assert util.ffprobe() == str(binario / "ffprobe.exe")
    assert util._resolver("npx") == str(pf / "nodejs" / "npx.cmd")
    assert util._resolver("node") == str(pf / "nodejs" / "node.exe")
    assert util._resolver("nao-existe") == "nao-existe"
    links = local / "Microsoft" / "WinGet" / "Links"
    (links / "ffmpeg.exe").write_bytes(b"x")
    assert util.ffmpeg() == str(links / "ffmpeg.exe")  # o atalho do winget vem primeiro


@pytest.mark.skipif(os.name != "nt", reason="winget só existe no Windows")
def test_rodar_poe_a_pasta_achada_no_path(tmp_path, monkeypatch):
    """npm install roda scripts que chamam `node`: a pasta do Node achada fora do PATH vai junto."""
    _, pf = _pastas_do_winget(tmp_path, monkeypatch)
    (pf / "nodejs" / "npx.cmd").write_text("@echo %PATH%\r\n")
    r = util.rodar(["npx"])
    assert str(pf / "nodejs").lower() in r.stdout.lower()


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
