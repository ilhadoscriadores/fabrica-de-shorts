import random

import pytest

from fabrica import origem, util

VTT = """WEBVTT
Kind: captions
Language: pt

00:00:01.000 --> 00:00:03.000 align:start position:0%
eu<00:00:01.500><c> tava</c><00:00:02.000><c> na</c><00:00:02.500><c> mata</c>

00:00:03.000 --> 00:00:03.010 align:start position:0%
eu tava na mata


00:00:03.010 --> 00:00:05.000 align:start position:0%
eu tava na mata
quando<00:00:03.500><c> ouvi</c><00:00:04.000><c> o</c><00:00:04.500><c> tiro</c>

00:00:05.000 --> 00:00:07.000 align:start position:0%
quando ouvi o tiro
e corri
"""


def test_vtt_para_linhas_sem_repeticao():
    linhas = origem.vtt_para_linhas(VTT)
    assert [t for t, _ in linhas] == [1.0, 3.01, 5.0]
    assert [x for _, x in linhas] == ["eu tava na mata", "quando ouvi o tiro", "e corri"]


def test_txt_com_tempo(tmp_path):
    p = tmp_path / "a.txt"
    origem.gravar_txt(origem.vtt_para_linhas(VTT), p)
    assert p.read_text(encoding="utf-8").splitlines()[1] == "00:00:03 quando ouvi o tiro"


def test_segundos_aceita_formatos():
    assert origem.segundos("3:20:36") == 12036
    assert origem.segundos("20:36") == 1236
    assert origem.segundos("75.5") == 75.5
    assert origem.segundos(12) == 12


def _episodio_sintetico(trechos):
    """4 h de fala aleatória; insere cada (tempo, texto) do corte no lugar certo."""
    rnd = random.Random(7)
    vocab = [f"palavra{i}" for i in range(3000)]
    linhas, t = [], 0.0
    pendentes = sorted(trechos)
    while t < 4 * 3600:
        if pendentes and t >= pendentes[0][0]:
            alvo, texto = pendentes.pop(0)
            ws = texto.split()
            for i in range(0, len(ws), 7):
                linhas.append((t, " ".join(ws[i:i + 7])))
                t += 2.5
            continue
        linhas.append((t, " ".join(rnd.choice(vocab) for _ in range(7))))
        t += 2.5
    return linhas


def test_localizar_acha_dois_trechos():
    parte1 = ("eu tava deitado no chão da mata e comecei a rezar baixinho porque os tiros não paravam "
              "e eu pensei que era o fim da minha vida ali naquela trilha escura")
    parte2 = ("aí eu gritei a senha e o cara de preto respondeu a contrassenha errada e eu fiquei "
              "sem saber se atirava ou se esperava o resto da equipe chegar")
    ep = _episodio_sintetico([(12036, parte1), (12243, parte2)])
    ref = (parte1 + " " + parte2).split()
    regioes = origem.localizar(ref, ep)
    inicios = sorted(r["inicio"] for r in regioes[:2])
    assert inicios[0] == pytest.approx(12036, abs=3)
    assert inicios[1] == pytest.approx(12243, abs=3)
    assert all(r["acertos"] >= 10 for r in regioes[:2])


def test_localizar_sem_nada_parecido_devolve_vazio():
    ep = _episodio_sintetico([])
    assert origem.localizar("isso nunca foi dito em lugar nenhum mesmo".split(), ep) == []


def test_baixar_monta_opcoes_do_trecho(monkeypatch, tmp_path):
    vistos = {}

    class FalsoYDL:
        def __init__(self, opts):
            vistos.update(opts)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def extract_info(self, url, download=True):
            (tmp_path / "bruto.mp4").write_bytes(b"x")
            return {"title": "Episódio 183", "channel": "Podcast X", "duration": 15000}

    monkeypatch.setattr(origem, "_YDL", FalsoYDL)
    monkeypatch.setattr(origem.util, "sondar", lambda p: {"duracao": 330.0})
    r = origem.baixar("https://www.youtube.com/watch?v=abc", "3:20:36", "3:25:35", tmp_path, margem=4)
    faixas = list(vistos["download_ranges"](None, None))
    assert faixas[0]["start_time"] == 12032 and faixas[0]["end_time"] == 12339
    assert "height<=1080" in vistos["format"]
    assert vistos["merge_output_format"] == "mp4"
    o = util.ler_json(tmp_path / "origem.json")
    assert o["inicio_real"] == 12032 and o["url"].endswith("abc") and o["titulo"] == "Episódio 183"
    assert r["bruto"].endswith("bruto.mp4")


def test_baixar_nao_baixa_de_novo_se_o_bruto_existe(monkeypatch, tmp_path):
    (tmp_path / "bruto.mp4").write_bytes(b"x")
    monkeypatch.setattr(origem, "_YDL", None)  # se tentar baixar, quebra
    monkeypatch.setattr(origem.util, "sondar", lambda p: {"duracao": 10.0})
    r = origem.baixar("https://youtu.be/abc", 10, 20, tmp_path)
    assert r["ja_existia"] is True
