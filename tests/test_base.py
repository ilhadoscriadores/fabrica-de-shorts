import numpy as np
import pytest

from fabrica import base, util


def W(w, s, e):
    return {"w": w, "s": s, "e": e}


# ---------- funções puras ----------
def test_correcao_por_tempo_aproximado():
    ws = [W("eu", 1.0, 1.2), W("via", 1.3, 1.6), W("a", 1.7, 1.8), W("via", 5.0, 5.3), W("bop", 6.0, 6.4)]
    out = base.aplicar_correcoes(ws, [{"t": 5.2, "de": "via", "para": "vi"}, {"t": 6.5, "de": "bop.", "para": "BOPE"}])
    assert [w["w"] for w in out] == ["eu", "via", "a", "vi", "BOPE"]


def test_correcao_apaga_e_divide():
    ws = [W("contra-senha,", 2.0, 3.0), W("né", 3.1, 3.3)]
    out = base.aplicar_correcoes(ws, [{"t": 2.0, "de": "contra-senha", "para": "contra senha,"},
                                      {"t": 3.2, "de": "né", "para": ""}])
    assert [w["w"] for w in out] == ["contra", "senha,"]
    assert out[0]["e"] == pytest.approx(2.5) and out[1]["s"] == pytest.approx(2.5)


def test_mascarar_palavrao():
    assert base.mascarar("porra,") == "p*rra,"
    assert base.mascarar("Caralho!") == "C*ralho!"


def test_palavroes_automaticos_e_pedidos():
    ws = [W("que", 1, 1.2), W("porra", 1.3, 1.7), W("legal", 1.8, 2.2), W("droga", 3, 3.4)]
    idx = base.achar_censuras(ws, [{"t": 3.1, "palavra": "droga"}], idioma="pt", automatico=True)
    assert idx == [1, 3]


def test_trecho_encaixa_em_borda_de_palavra():
    ws = [W("a", 9.0, 9.4), W("bom", 10.05, 10.4), W("dia", 10.5, 10.9), W("gente", 11.4, 11.8)]
    keep = base.calcular_keep(ws, [[10.2, 10.95]], pausa_max=0.35, fps=30)
    # começa antes de "bom" (corta a palavra no meio não) e termina depois de "dia", sem entrar em "gente"
    assert keep[0][0] <= 10.05 - 0.03 and keep[0][0] > 9.4
    assert keep[-1][1] >= 10.9 and keep[-1][1] < 11.4
    for s, e in keep:  # tudo na grade de quadros
        assert round(s * 30, 6) == round(s * 30) and round(e * 30, 6) == round(e * 30)


def test_pausa_longa_cortada_e_remapeada():
    ws = [W("um", 1.0, 1.4), W("dois", 1.5, 1.9), W("tres", 3.1, 3.5)]  # pausa de 1,2 s
    keep = base.calcular_keep(ws, [[0.9, 3.6]], pausa_max=0.35, fps=30)
    assert len(keep) == 2
    total = sum(e - s for s, e in keep)
    assert total < 3.6 - 0.9 - 0.9
    assert base.remap(keep, 3.1) == pytest.approx(base.remap(keep, 1.9) + 0.2, abs=0.05)


def test_trecho_sem_palavras_da_erro():
    with pytest.raises(util.ErroUsuario):
        base.calcular_keep([W("a", 1, 2)], [[5, 8]], pausa_max=0.35, fps=30)


def test_linhas_do_timeline():
    ws = [W("Oi,", 0, 0.3), W("tudo", 0.4, 0.6), W("bem?", 0.7, 1.0), W("Eu", 2.0, 2.2), W("sim.", 2.3, 2.6)]
    assert base.linhas_texto(ws) == ["[0.0] Oi, tudo bem?", "[2.0] Eu sim."]


def test_fim_do_pedaco_nao_invade_a_palavra_seguinte():
    ws = [W("bom", 10.05, 10.4), W("dia", 10.5, 10.9), W("gente", 10.92, 11.3)]
    keep = base.calcular_keep(ws, [[10.0, 10.9]], pausa_max=0.35, fps=30)
    assert keep[-1][1] <= 10.92 - 0.005  # arredondar para cima daria 10,933 (dentro de "gente")
    assert keep[-1][1] == pytest.approx(10.9)


def test_palavra_so_entra_se_cabe_no_pedaco():
    keep = [[0.0, 1.0], [2.0, 3.0]]
    ws = [W("a", 0.2, 0.6), W("fantasma", 0.98, 1.3), W("curta", 0.96, 1.0), W("b", 2.1, 2.5)]
    tl = base.palavras_no_corte(ws, keep)
    assert [w["w"] for w in tl] == ["a", "curta", "b"]
    assert tl[-1]["s"] == pytest.approx(1.1) and tl[-1]["orig"] == 2.1


def _env(vozes, dur=6.0):
    """Envelope de 10 ms: -20 dB nas vozes, -70 dB no resto."""
    t = np.arange(int(dur * 100)) / 100
    env = np.full(len(t), -70.0)
    for a, b in vozes:
        env[(t >= a - 1e-9) & (t < b - 1e-9)] = -20.0
    return env


def _na_grade(keep):
    return all(round(x * 30, 6) == round(x * 30) for par in keep for x in par)


def test_silencio_esticado_sai_pelo_audio():
    keep = [[28 / 30, 124 / 30]]  # 0,933 a 4,133: o Whisper esticou uma palavra até 2,9
    out = base.refinar_keep(keep, _env([(1.0, 2.0), (3.0, 4.0)]), pausa_max=0.35)
    assert len(out) == 2
    assert out[0] == [pytest.approx(28 / 30), pytest.approx(2.1)]  # 2,0 + 0,07 para cima na grade
    assert out[1] == [pytest.approx(2.9), pytest.approx(124 / 30)]  # 3,0 - 0,07 para baixo
    assert _na_grade(out)


def test_silencio_curto_fica():
    keep = [[28 / 30, 124 / 30]]
    assert base.refinar_keep(keep, _env([(1.0, 2.0), (2.45, 4.0)]), pausa_max=0.35) == keep


def test_silencio_na_borda_nao_deixa_toco_mudo():
    keep = [[28 / 30, 124 / 30]]
    out = base.refinar_keep(keep, _env([(1.8, 4.0)]), pausa_max=0.35)  # mudo de 0,93 a 1,8
    assert len(out) == 1 and out[0][0] == pytest.approx(1.7) and out[0][1] == pytest.approx(124 / 30)
    out = base.refinar_keep(keep, _env([(1.0, 3.0)]), pausa_max=0.35)  # mudo de 3,0 até o fim
    assert len(out) == 1 and out[0][1] == pytest.approx(3.1)


def test_pedaco_todo_mudo_nao_some():
    keep = [[1.0, 2.0]]
    assert base.refinar_keep(keep, _env([(4.0, 5.0)]), pausa_max=0.35) == keep


# ---------- integração (ffmpeg) ----------
@pytest.fixture
def corte(tmp_path):
    util.gravar_json(tmp_path / "canal.json", {"nome": "T", "arroba": "@t", "idioma": "pt"})
    c = tmp_path / "cortes" / "001-t"
    c.mkdir(parents=True)
    # metade esquerda branca, direita preta; tom contínuo
    util.rodar([util.ffmpeg(), "-v", "error", "-y", "-f", "lavfi", "-i", "color=white:s=640x360:r=30:d=12",
                "-f", "lavfi", "-i", "color=black:s=320x360:r=30:d=12", "-f", "lavfi", "-i", "sine=f=300:d=12",
                "-filter_complex", "[0:v][1:v]overlay=320:0[v]", "-map", "[v]", "-map", "2:a",
                "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", str(c / "bruto.mp4")])
    palavras = [W("isso", 1.0, 1.4), W("é", 1.5, 1.7), W("uma", 1.8, 2.1), W("porra", 2.2, 2.7),
                W("de", 2.8, 2.9), W("teste", 3.0, 3.5), W("depois", 5.0, 5.5), W("continua", 5.6, 6.2)]
    util.gravar_json(c / "palavras.json", palavras)
    return tmp_path, c


def _corte_json(c, **extra):
    util.gravar_json(c / "corte.json", {"trechos": [[0.9, 3.6], [4.9, 6.3]], **extra})


def test_base_gera_tudo_com_av_igual(corte):
    _, c = corte
    _corte_json(c)
    r = base.base(c, rosto=False)
    info = util.sondar(c / "base.mp4")
    tl = util.ler_json(c / "timeline.json")
    assert info["largura"] == 640 and info["altura"] == 360
    assert abs(info["duracao_video"] - info["duracao_audio"]) <= 1 / 30 + 0.025
    assert abs(info["duracao_video"] - tl["duracao"]) <= 1 / 30 + 0.001
    voz = util.ler_audio(c / "voz.wav")
    assert len(voz) / 48000 == pytest.approx(tl["duracao"], abs=0.002)
    assert (c / "timeline.txt").read_text(encoding="utf-8").startswith("[0.")
    assert r["duracao"] == tl["duracao"]


def test_palavrao_mascarado_e_mudo(corte):
    _, c = corte
    _corte_json(c)
    base.base(c, rosto=False)
    tl = util.ler_json(c / "timeline.json")
    p = next(w for w in tl["palavras"] if w["censura"])
    assert p["w"] == "p*rra"
    env = util.envelope_db(c / "voz.wav")
    meio = env[int((p["s"] + 0.05) * 100): int((p["e"] - 0.05) * 100)]
    assert meio.max() < -50
    assert env[int(0.3 * 100): int(0.6 * 100)].mean() > -40  # o resto continua com som


def test_base_com_espelhar(corte):
    pasta, c = corte
    util.gravar_json(pasta / "canal.json", {"nome": "T", "opcoes": {"espelhar": True}})
    _corte_json(c)
    base.base(c, rosto=False)
    raw = util.rodar_bytes([util.ffmpeg(), "-v", "error", "-i", str(c / "base.mp4"), "-frames:v", "1",
                            "-f", "rawvideo", "-pix_fmt", "gray", "-"])
    q = np.frombuffer(raw, np.uint8).reshape(360, 640)
    assert q[:, :300].mean() < 60 and q[:, 340:].mean() > 200


def test_transcricao_vazia_da_erro_claro(corte):
    _, c = corte
    util.gravar_json(c / "palavras.json", [])
    _corte_json(c)
    with pytest.raises(util.ErroUsuario) as e:
        base.base(c, rosto=False)
    assert "transcri" in str(e.value)


def test_base_corta_silencio_que_o_whisper_esticou(tmp_path):
    util.gravar_json(tmp_path / "canal.json", {"nome": "T", "arroba": "@t", "idioma": "pt"})
    c = tmp_path / "cortes" / "001-t"
    c.mkdir(parents=True)
    util.rodar([util.ffmpeg(), "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=320x180:r=30:d=6",
                "-f", "lavfi", "-i", "sine=f=220:d=6",
                "-filter_complex", "[1:a]volume='if(between(t,1,2)+between(t,3,4),0.4,0.0003)':eval=frame[a]",
                "-map", "0:v", "-map", "[a]", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", str(c / "bruto.mp4")])
    ws = [W("eu", 1.0, 1.4), W("tava", 1.45, 2.9), W("na", 3.0, 3.4), W("mata", 3.5, 4.0)]  # "tava" esticada
    util.gravar_json(c / "palavras.json", ws)
    util.gravar_json(c / "corte.json", {"trechos": [[0.9, 4.1]]})
    so_whisper = sum(e - s for s, e in base.calcular_keep(ws, [[0.9, 4.1]], pausa_max=0.35))
    r = base.base(c, rosto=False)
    assert 0.78 <= so_whisper - r["duracao"] <= 0.9  # ~0,86 s (1 s de silêncio menos 0,07 de cada lado)
    assert r["pedacos"] == 2 and r["palavras"] == 4
    env = util.envelope_db(c / "voz.wav")
    mudo = env < -40
    maior, run = 0, 0
    for m in mudo[5:-5]:
        run = run + 1 if m else 0
        maior = max(maior, run)
    assert maior < 30  # nenhum silêncio de 0,3 s ou mais no meio da fala
