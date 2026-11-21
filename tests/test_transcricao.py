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


class _Info:
    def __init__(self, lang, prob):
        self.language, self.language_probability = lang, prob


def _modelo_falso(monkeypatch, respostas, chamadas):
    """respostas(language, vad_filter) -> (segs, info)"""
    class FalsoModelo:
        def __init__(self, *a, **k):
            pass

        def transcribe(self, audio, language=None, vad_filter=True, **k):
            chamadas.append((language, vad_filter))
            return respostas(language, vad_filter)

    import faster_whisper
    monkeypatch.setattr(faster_whisper, "WhisperModel", FalsoModelo)
    monkeypatch.setattr(transcricao.ambiente, "whisper_dispositivo", lambda: ("cpu", "int8", "small"))


def _video(tmp_path, d=2):
    v = tmp_path / "v.mp4"
    util.rodar([util.ffmpeg(), "-v", "error", "-y", "-f", "lavfi", "-i", f"sine=d={d}", str(v)])
    return v


def test_transcrever_detecta_o_idioma_da_fala_e_nao_traduz(tmp_path, monkeypatch):
    """Canal em pt, fala em inglês: o Whisper não recebe language='pt' (senão traduz) e o idioma fica gravado."""
    chamadas = []
    _modelo_falso(monkeypatch, lambda lang, vad: ([_Seg()], _Info("en", 0.97)), chamadas)
    transcricao.transcrever(_video(tmp_path), tmp_path / "palavras.json", idioma_padrao="pt")
    assert chamadas == [(None, True)]
    assert transcricao.idioma_do_corte(tmp_path) == "en"


def test_transcrever_sem_certeza_usa_o_idioma_do_canal(tmp_path, monkeypatch):
    chamadas = []
    _modelo_falso(monkeypatch, lambda lang, vad: ([_Seg()], _Info("gl", 0.3)), chamadas)
    transcricao.transcrever(_video(tmp_path), tmp_path / "palavras.json", idioma_padrao="pt")
    assert chamadas == [(None, True), ("pt", True)]
    assert transcricao.idioma_do_corte(tmp_path) == "pt"


def test_transcrever_refaz_sem_vad_quando_quase_nada_sai(tmp_path, monkeypatch):
    """Fala por baixo de jogo/música: com o VAD sai 1 palavra em 12 s; sem ele, a fala toda."""
    class Muitas:
        words = [_Palavra(f" w{i}", i * 0.5, i * 0.5 + 0.3) for i in range(20)]

    class Uma:
        words = [_Palavra(" oi", 0.1, 0.4)]

    chamadas = []
    _modelo_falso(monkeypatch, lambda lang, vad: ([Uma() if vad else Muitas()], _Info("en", 0.9)), chamadas)
    ws = transcricao.transcrever(_video(tmp_path, 12), tmp_path / "palavras.json")
    assert chamadas == [(None, True), ("en", False)]
    assert len(ws) == 20
