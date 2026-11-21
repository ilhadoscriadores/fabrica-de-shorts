import json

from fabrica import biblioteca, entrega, imagens, util


def test_novo_corte_numera(tmp_path):
    (tmp_path / "cortes" / "001-x").mkdir(parents=True)
    (tmp_path / "cortes" / "007-y").mkdir()
    p = entrega.novo_corte(tmp_path, "Sgt Honório: a senha!")
    assert p.name == "008-sgt-honorio-a-senha"
    assert (p / "tempos.csv").read_text(encoding="utf-8").splitlines()[1].startswith("missao,")


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
                                         "fim_real": 12339, "titulo": "SARGENTO HONÓRIO - Fala Glauber #183", "canal": "Fala Glauber Podcast"})
    util.gravar_json(c / "timeline.json", {"duracao": 89.5, "palavras": []})
    util.gravar_json(c / "corte.json", {
        "modelo": {"url": "https://www.youtube.com/shorts/68L5Flrr0Mo", "titulo": "PM HONORIO", "canal": "Justiceiro Cortes", "views": 3754517},
        "edicao": {"imagens": [{"arquivo": "a.png", "s": 1, "e": 2}], "trilha": {"arquivo": "epico/heroic.mp3"}},
        "postagem": {"titulo": "Gritou a senha do BOPE 😨", "legenda_tiktok": "Você atiraria?", "descricao": "Sgt Honório conta.",
                     "hashtags": ["#bope", "#podcast"]}})
    txt = entrega.postagem(c).read_text(encoding="utf-8")
    assert "Gritou a senha do BOPE" in txt and "#bope #podcast" in txt
    assert "https://www.youtube.com/watch?v=ng-Q6ZD0XmI&t=12032s" in txt
    assert "Fala Glauber Podcast" in txt
    assert "geradas por IA" in txt
    assert "Heroic Age" in txt
    assert "1min29" in txt
    assert "3.754.517" in txt and "68L5Flrr0Mo" in txt


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
