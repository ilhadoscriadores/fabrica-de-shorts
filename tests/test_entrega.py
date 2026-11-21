import datetime as dt
import json

from fabrica import biblioteca, entrega, imagens, util


def test_novo_corte_numera(tmp_path):
    (tmp_path / "cortes" / "001-x").mkdir(parents=True)
    (tmp_path / "cortes" / "007-y").mkdir()
    p = entrega.novo_corte(tmp_path, "Sgt Fulano: a ação!")
    assert p.name == "008-sgt-fulano-a-acao"
    assert (p / "tempos.csv").read_text(encoding="utf-8").splitlines()[1].startswith("missao,")


def test_novo_corte_comeca_a_missao_no_minerar(tmp_path):
    (tmp_path / ".fabrica").mkdir()
    inicio = (dt.datetime.now() - dt.timedelta(minutes=12)).isoformat(timespec="seconds")
    (tmp_path / ".fabrica" / "missao_inicio.txt").write_text(inicio, encoding="utf-8")
    p = entrega.novo_corte(tmp_path, "x")
    assert (p / "tempos.csv").read_text(encoding="utf-8").splitlines()[1] == f"missao,{inicio},0,inicio"
    assert not (tmp_path / ".fabrica" / "missao_inicio.txt").exists()
    assert entrega.tempo(p, "ver")["total_s"] >= 12 * 60


def test_novo_corte_ignora_inicio_velho(tmp_path):
    (tmp_path / ".fabrica").mkdir()
    velho = (dt.datetime.now() - dt.timedelta(hours=4)).isoformat(timespec="seconds")
    (tmp_path / ".fabrica" / "missao_inicio.txt").write_text(velho, encoding="utf-8")
    p = entrega.novo_corte(tmp_path, "x")
    assert velho not in (p / "tempos.csv").read_text(encoding="utf-8")
    assert entrega.tempo(p, "ver")["total_s"] < 60
    assert not (tmp_path / ".fabrica" / "missao_inicio.txt").exists()


def test_tempo_inicio_fim(tmp_path):
    p = entrega.novo_corte(tmp_path, "x")
    with open(p / "tempos.csv", "a", encoding="utf-8") as f:
        f.write("render,2026-11-21T10:00:00,300.0,ok\nbase,2026-11-21T09:50:00,40.0,ok\n")
    r = entrega.tempo(p, "fim")
    assert r["total_s"] >= 0 and r["maquina_s"] == 340.0
    assert r["etapas_mais_longas"][0].startswith("render")


def test_postagem_tem_credito_e_origem(tmp_path):
    c = tmp_path / "cortes" / "001-x"
    (c / "imagens").mkdir(parents=True)
    (tmp_path / "biblioteca").mkdir()
    (tmp_path / "biblioteca" / "LICENCAS.md").write_text(
        "| trilhas/epico/heroic.mp3 | Kevin MacLeod | CC BY 4.0 | crédito: \"Heroic Age\" Kevin MacLeod (incompetech.com) |\n", encoding="utf-8")
    util.gravar_json(c / "origem.json", {"url": "https://www.youtube.com/watch?v=ng-Q6ZD0XmI", "inicio_real": 12032,
                                         "fim_real": 12339, "titulo": "SARGENTO FULANO - Podcast Exemplo #100", "canal": "Canal do Podcast Exemplo"})
    util.gravar_json(c / "timeline.json", {"duracao": 89.5, "palavras": []})
    util.gravar_json(c / "corte.json", {
        "modelo": {"url": "https://www.youtube.com/shorts/68L5Flrr0Mo", "titulo": "SGT FULANO", "canal": "Cortes Exemplo", "views": 3754517},
        "edicao": {"imagens": [{"arquivo": "a.png", "s": 1, "e": 2}], "trilha": {"arquivo": "epico/heroic.mp3"}},
        "postagem": {"titulo": "Gritou a senha do BOPE 😨", "legenda_tiktok": "Você atiraria?", "descricao": "Sgt Fulano conta.",
                     "hashtags": ["#bope", "#podcast"]}})
    txt = entrega.postagem(c).read_text(encoding="utf-8")
    assert "Gritou a senha do BOPE" in txt and "#bope #podcast" in txt
    assert ("Vídeo original: SARGENTO FULANO - Podcast Exemplo #100 · "
            "https://www.youtube.com/watch?v=ng-Q6ZD0XmI&t=12032s") in txt
    assert "Episódio" not in txt  # o vídeo baixado pode ser um vídeo curto do canal do podcast
    assert txt.count("SARGENTO FULANO") == 2  # 1 na descrição, 1 na origem
    assert "Canal do Podcast Exemplo" in txt
    assert "geradas por IA" in txt
    assert "Heroic Age" in txt
    assert "1min29" in txt
    assert "3.754.517" in txt and "68L5Flrr0Mo" in txt


def test_postagem_link_no_comeco_do_primeiro_trecho(tmp_path):
    c = tmp_path / "cortes" / "001-x"
    c.mkdir(parents=True)
    util.gravar_json(c / "origem.json", {"url": "https://www.youtube.com/watch?v=abc", "inicio_real": 12032})
    util.gravar_json(c / "corte.json", {"trechos": [[50.6, 80.0], [100.0, 120.0]],
                                        "postagem": {"titulo": "T", "hashtags": []}})
    txt = entrega.postagem(c).read_text(encoding="utf-8")
    assert "https://www.youtube.com/watch?v=abc&t=12082s" in txt


def test_postagem_usa_o_tempo_do_tempo_fim(tmp_path):
    c = entrega.novo_corte(tmp_path, "x")
    with open(c / "tempos.csv", "a", encoding="utf-8") as f:
        f.write("render,2026-11-21T10:00:00,300.0,ok\nmissao,2026-11-21T10:30:00,754,fim\n")
    util.gravar_json(c / "corte.json", {"postagem": {"titulo": "T", "hashtags": []}})
    txt = entrega.postagem(c).read_text(encoding="utf-8")
    assert "TEMPO DE PRODUÇÃO: 12min34 (máquina 5min00)" in txt
    assert entrega.tempo(c, "ver")["total_s"] == 754


def test_capa_1080x1920(corte_sintetico):
    _, c = corte_sintetico
    p = entrega.capa(c, "A POLÍCIA CHEGOU E ELE CORREU")
    info = util.sondar(p)
    assert (info["largura"], info["altura"]) == (1080, 1920)


def test_imagens_sem_codex_escreve_faltando(tmp_path, monkeypatch):
    c = tmp_path / "cortes" / "001-x"
    (c / "imagens").mkdir(parents=True)
    (c / "imagens" / "prompts.txt").write_text("01_mata|uma mata densa à noite\n02_viatura|uma viatura na estrada\n", encoding="utf-8")
    monkeypatch.setattr(imagens.shutil, "which", lambda n: None)
    r = imagens.gerar(c)
    assert r["geradas"] == [] and r["faltando"] == ["01_mata", "02_viatura"]
    md = (c / "imagens" / "FALTANDO.md").read_text(encoding="utf-8")
    assert "uma mata densa à noite" in md and "ChatGPT" in md


def test_indice_marca_usados_recentes(tmp_path):
    ef = tmp_path / "biblioteca" / "efeitos"
    for rel in ("whoosh/a.mp3", "whoosh/b.mp3", "impacto/c.mp3"):
        (ef / rel).parent.mkdir(parents=True, exist_ok=True)
        (ef / rel).write_bytes(b"x")
    (tmp_path / "biblioteca" / "trilhas" / "tensao").mkdir(parents=True)
    (tmp_path / "biblioteca" / "trilhas" / "tensao" / "t.mp3").write_bytes(b"x")
    util.gravar_json(tmp_path / "cortes" / "001-x" / "corte.json", {"edicao": {"efeitos": [{"arquivo": "whoosh/a.mp3"}],
                                                                             "trilha": {"arquivo": "tensao/t.mp3"}}})
    ind = biblioteca.indice(tmp_path)
    assert ind["efeitos"]["whoosh"] == ["a.mp3 (usado)", "b.mp3"]
    assert ind["trilhas"]["tensao"] == ["t.mp3 (usado)"]


def test_baixar_kit_grava_licenca(tmp_path, monkeypatch):
    (tmp_path / "biblioteca").mkdir()
    (tmp_path / "biblioteca" / "LICENCAS.md").write_text("# Licenças\n", encoding="utf-8")
    monkeypatch.setattr(biblioteca, "_baixar", lambda url, destino: destino.write_bytes(b"audio"))
    r = biblioteca.baixar_kit(tmp_path, tipos=("trilhas",))
    assert r["baixados"] >= 20
    lic = (tmp_path / "biblioteca" / "LICENCAS.md").read_text(encoding="utf-8")
    assert "Mixkit" in lic and "trilhas/comedia/" in lic
    assert any((tmp_path / "biblioteca" / "trilhas" / "comedia").iterdir())


def test_postagem_sem_views_usa_curtidas_e_nao_quebra(tmp_path):
    """Instagram não informa views: views null não pode derrubar o postagem."""
    from fabrica import entrega, util
    for modelo, esperado, proibido in (
        ({"url": "https://www.instagram.com/reel/X/", "titulo": "T", "canal": "c", "views": None, "curtidas": 232831},
         "232.831 curtidas", "views"),
        ({"url": "https://www.instagram.com/reel/X/", "titulo": "T", "canal": "c", "views": None}, "· c", "0 views"),
    ):
        c = tmp_path / ("c" + str(len(esperado)))
        c.mkdir()
        util.gravar_json(c / "corte.json", {"modelo": modelo, "postagem": {"titulo": "T", "hashtags": []}})
        txt = entrega.postagem(c).read_text(encoding="utf-8")
        linha = next(l for l in txt.splitlines() if l.startswith('  "T"'))
        assert esperado in linha and proibido not in linha
