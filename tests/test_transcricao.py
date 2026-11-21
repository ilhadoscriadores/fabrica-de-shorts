import numpy as np

from fabrica import transcricao, util


class _Palavra:
    def __init__(self, w, s, e):
        self.word, self.start, self.end = w, s, e


class _Seg:
    words = [_Palavra(" oi", 0.1, 0.4), _Palavra(" gente.", 0.5, 0.9)]


def test_transcrever_manda_audio_decodificado_pelo_ffmpeg(tmp_path, monkeypatch):
    v = tmp_path / "v.mp4"
    util.rodar([util.ffmpeg(), "-v", "error", "-y", "-f", "lavfi", "-i", "sine=d=2", str(v)])
    visto = {}

    class FalsoModelo:
        def __init__(self, *a, **k):
            pass

        def transcribe(self, audio, **k):
            visto["audio"] = audio
            return [_Seg()], None

    import faster_whisper
    monkeypatch.setattr(faster_whisper, "WhisperModel", FalsoModelo)
    monkeypatch.setattr(transcricao.ambiente, "whisper_dispositivo", lambda: ("cpu", "int8", "small"))
    ws = transcricao.transcrever(v, tmp_path / "palavras.json", idioma="pt")
    assert isinstance(visto["audio"], np.ndarray) and len(visto["audio"]) == 32000
    assert ws == [{"w": "oi", "s": 0.1, "e": 0.4}, {"w": "gente.", "s": 0.5, "e": 0.9}]
    assert (tmp_path / "transcricao.txt").read_text(encoding="utf-8") == "[0.1–0.9] oi gente.\n"


def test_linhas_txt_tem_inicio_e_fim_da_frase():
    ws = [{"w": "Oi,", "s": 0.0, "e": 0.3}, {"w": "tudo", "s": 0.4, "e": 0.6}, {"w": "bem?", "s": 0.7, "e": 1.04},
          {"w": "Eu", "s": 2.0, "e": 2.2}, {"w": "sim", "s": 2.3, "e": 2.66}]
    assert transcricao.linhas_txt(ws) == ["[0.0–1.0] Oi, tudo bem?", "[2.0–2.7] Eu sim"]
    assert transcricao.linhas(ws) == [(0.0, "Oi, tudo bem?"), (2.0, "Eu sim")]  # o achar ainda usa só o início
