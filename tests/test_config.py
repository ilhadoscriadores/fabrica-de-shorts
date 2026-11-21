import json

import pytest

from fabrica import config, util


@pytest.fixture
def area(tmp_path):
    """Pasta de trabalho com canal.json e um corte com bruto de 10 s."""
    (tmp_path / "canal.json").write_text(json.dumps({"nome": "Canal Teste", "arroba": "@teste", "nicho": "podcast"}), encoding="utf-8")
    corte = tmp_path / "cortes" / "001-teste"
    (corte / "imagens").mkdir(parents=True)
    util.rodar([util.ffmpeg(), "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=320x180:d=10:r=30",
                "-f", "lavfi", "-i", "sine=d=10", "-shortest", "-c:v", "libx264", "-preset", "ultrafast",
                str(corte / "bruto.mp4")])
    (tmp_path / "biblioteca" / "efeitos" / "whoosh").mkdir(parents=True)
    (tmp_path / "biblioteca" / "efeitos" / "whoosh" / "w1.wav").write_bytes(b"RIFF")
    return tmp_path, corte


def test_padroes_preenchidos(area):
    pasta, _ = area
    c = config.carregar_canal(pasta)
    assert c["idioma"] == "pt"
    assert c["estilo"]["cor"] == "#FFD60A"
    assert c["opcoes"] == {"espelhar": False, "selo": False, "censurar_palavroes": True, "max_segundos": 90}
    assert c["estilo_aprovado"] is False
    assert c["nome"] == "Canal Teste"


def test_canal_faltando_manda_rodar_comecar(tmp_path):
    with pytest.raises(util.ErroUsuario) as e:
        config.carregar_canal(tmp_path)
    assert "comecar" in str(e.value)


def test_trecho_fora_do_bruto_da_erro_em_portugues(area):
    _, corte = area
    erros = config.validar_corte({"trechos": [[5, 20]]}, corte)
    assert erros and "trecho" in erros[0] and "bruto" in erros[0]


def test_corte_sem_trechos(area):
    _, corte = area
    erros = config.validar_corte({"trechos": []}, corte)
    assert any("trechos" in e for e in erros)


def test_imagem_inexistente_da_erro(area):
    _, corte = area
    c = {"trechos": [[1, 8]], "edicao": {"imagens": [{"arquivo": "x.png", "s": 1, "e": 3}]}}
    erros = config.validar_corte(c, corte, etapa="render")
    assert any("x.png" in e for e in erros)


def test_efeito_inexistente_e_existente(area):
    _, corte = area
    c = {"trechos": [[1, 8]], "edicao": {"efeitos": [{"t": 1, "arquivo": "whoosh/w1.wav"},
                                                     {"t": 2, "arquivo": "whoosh/nao.wav"}]}}
    erros = config.validar_corte(c, corte, etapa="render")
    assert len(erros) == 1 and "whoosh/nao.wav" in erros[0]


def test_tempos_de_edicao_alem_da_duracao_avisam(area):
    _, corte = area
    util.gravar_json(corte / "timeline.json", {"duracao": 6.0, "palavras": []})
    c = {"trechos": [[1, 8]], "edicao": {"etiquetas": [{"s": 7, "e": 9, "texto": "OI"}]}}
    erros = config.validar_corte(c, corte, etapa="render")
    assert any("etiqueta" in e and "6.0" in e for e in erros)


def test_carregar_corte_aplica_padroes_e_levanta(area):
    _, corte = area
    util.gravar_json(corte / "corte.json", {"trechos": [[1, 8]]})
    c = config.carregar_corte(corte)
    assert c["pausa_max"] == 0.35 and c["censurar"] == [] and c["correcoes"] == [] and c["edicao"] == {}
    util.gravar_json(corte / "corte.json", {"trechos": [[9, 30]]})
    with pytest.raises(util.ErroUsuario):
        config.carregar_corte(corte)


def test_correcoes_no_formato_antigo_viram_lista(area):
    _, corte = area
    util.gravar_json(corte / "corte.json", {"trechos": [[1, 8]], "correcoes": {"via@3.06": "vi"}})
    c = config.carregar_corte(corte)
    assert c["correcoes"] == [{"t": 3.06, "de": "via", "para": "vi"}]
