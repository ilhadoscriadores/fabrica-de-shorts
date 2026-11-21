import numpy as np
import pytest

from fabrica import legendas, util


def W(w, s, e, censura=False):
    return {"w": w, "s": s, "e": e, "censura": censura}


def _seguidas(texto, t0=0.0, dur=0.25, vao=0.05):
    out, t = [], t0
    for w in texto.split():
        out.append(W(w, round(t, 3), round(t + dur, 3)))
        t += dur + vao
    return out


def _texto(b):
    return " ".join(p["w"] for p in b["palavras"])


def test_blocos_respeitam_3_palavras_16_chars():
    ws = _seguidas("ele chegou na delegacia com o carro todo amassado e ninguém acreditou na história dele")
    bs = legendas.blocos(ws)
    assert all(len(b["palavras"]) <= 3 for b in bs)
    assert all(len(_texto(b)) <= 16 or len(b["palavras"]) == 1 for b in bs)
    assert " ".join(_texto(b) for b in bs) == "ELE CHEGOU NA DELEGACIA COM O CARRO TODO AMASSADO E NINGUÉM ACREDITOU NA HISTÓRIA DELE"


def test_quebra_na_pontuacao_e_na_pausa():
    ws = [W("Oi,", 0, 0.3), W("tudo", 0.35, 0.6), W("bem", 0.65, 0.9), W("hoje", 1.5, 1.8)]
    bs = legendas.blocos(ws)
    assert [_texto(b) for b in bs] == ["OI", "TUDO BEM", "HOJE"]


def test_nao_termina_em_preposicao():
    ws = _seguidas("eu fui para a casa da minha mãe ontem")
    for b in legendas.blocos(ws)[:-1]:
        assert b["palavras"][-1]["w"] not in {"PARA", "A", "DA", "DE", "O"}, [_texto(x) for x in legendas.blocos(ws)]


def test_bloco_fica_ate_o_proximo():
    ws = [W("primeira", 0, 0.4), W("frase.", 0.45, 0.8), W("segunda", 1.3, 1.7), W("frase.", 1.75, 2.1)]
    bs = legendas.blocos(ws)
    assert bs[0]["f1"] == bs[1]["f0"]


def test_destaque_e_censura_marcados():
    ws = [W("que", 0, 0.2), W("p*rra", 0.3, 0.6, censura=True), W("bope", 0.7, 1.0)]
    bs = legendas.blocos(ws, destaques={"BOPE"})
    ps = bs[0]["palavras"]
    assert ps[1]["censura"] and ps[1]["w"] == "P*RRA" and ps[2]["destaque"] and not ps[0]["destaque"]


def test_tamanho_cabe_na_largura():
    ws = [W("inconstitucionalissimamente", 0, 1.0)]
    b = legendas.blocos(ws)[0]
    assert 40 <= b["tam"] < 92


# ---------- âncora e conferência com voz sintética ----------
INICIOS = [1.0, 2.5, 4.0]


def _voz(tmp_path):
    sr = 48000
    t = np.arange(int(5.5 * sr)) / sr
    x = (np.random.default_rng(1).standard_normal(len(t)) * 10 ** (-70 / 20)).astype(np.float32)
    for a in INICIOS:
        m = (t >= a) & (t < a + 0.8)
        x[m] += (0.3 * np.sin(2 * np.pi * 220 * t[m])).astype(np.float32)
    raw = tmp_path / "voz.f32"
    raw.write_bytes(x.tobytes())
    wav = tmp_path / "voz.wav"
    util.rodar([util.ffmpeg(), "-v", "error", "-y", "-f", "f32le", "-ar", "48000", "-ac", "1", "-i", str(raw), "-c:a", "pcm_f32le", str(wav)])
    return wav


def _palavras_adiantadas(atraso):
    ws = []
    for i, a in enumerate(INICIOS):
        ws += [W(f"frase{i}", a + atraso, a + atraso + 0.35), W(f"fim{i}.", a + atraso + 0.4, a + atraso + 0.75)]
    return ws


def test_ancora_corrige_whisper_adiantado(tmp_path):
    wav = _voz(tmp_path)
    bs = legendas.ancorar(legendas.blocos(_palavras_adiantadas(-0.3)), wav)
    for b, a in zip(bs, INICIOS):
        assert b["f0"] / 30 == pytest.approx(a, abs=0.034)


def test_conferir_passa_quando_esta_na_voz(tmp_path):
    wav = _voz(tmp_path)
    assert legendas.conferir(legendas.blocos(_palavras_adiantadas(0.0)), wav) == []


def test_conferir_acusa_atraso_de_120ms(tmp_path):
    wav = _voz(tmp_path)
    probs = legendas.conferir(legendas.blocos(_palavras_adiantadas(0.12)), wav)
    assert len(probs) == 3 and all("DEPOIS" in p["problema"] for p in probs)


def test_conferir_acusa_adiantada(tmp_path):
    wav = _voz(tmp_path)
    probs = legendas.conferir(legendas.blocos(_palavras_adiantadas(-0.15)), wav)
    assert len(probs) == 3 and all("ANTES" in p["problema"] for p in probs)
