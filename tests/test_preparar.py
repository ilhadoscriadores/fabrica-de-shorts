import json

from fabrica import preparar, util


def test_preparar_cria_estrutura(tmp_path):
    r = preparar.preparar(tmp_path, sem_npm=True)
    for d in ("mineracao", "cortes", "biblioteca/efeitos", "biblioteca/trilhas", ".fabrica/tmp", "editor/src"):
        assert (tmp_path / d).is_dir(), d
    assert (tmp_path / "GUIA-DE-EDICAO.md").exists()
    assert (tmp_path / "canal.json").exists()
    assert (tmp_path / "biblioteca" / "efeitos" / "whoosh" / "whoosh-rapido.mp3").exists()
    assert (tmp_path / "biblioteca" / "efeitos" / "bip" / "bip-censura.mp3").exists()
    lic = (tmp_path / "biblioteca" / "LICENCAS.md").read_text(encoding="utf-8")
    assert "CC0" in lic and "whoosh/whoosh-rapido.mp3" in lic
    est = util.ler_json(tmp_path / ".fabrica" / "estado.json")
    assert est["plugin"] == "1.0.0"
    assert r["ok"] is True


def test_preparar_grava_respostas_no_canal(tmp_path):
    preparar.preparar(tmp_path, sem_npm=True, respostas={"nome": "Meu Canal", "arroba": "@meu", "nicho": "podcast de humor"})
    c = json.loads((tmp_path / "canal.json").read_text(encoding="utf-8"))
    assert c["nome"] == "Meu Canal" and c["arroba"] == "@meu" and c["nicho"] == "podcast de humor"
    assert c["opcoes"]["selo"] is False


def test_preparar_nao_sobrescreve_guia_nem_canal(tmp_path):
    preparar.preparar(tmp_path, sem_npm=True)
    (tmp_path / "GUIA-DE-EDICAO.md").write_text("meu guia", encoding="utf-8")
    (tmp_path / "canal.json").write_text('{"nome": "X"}', encoding="utf-8")
    preparar.preparar(tmp_path, sem_npm=True)
    assert (tmp_path / "GUIA-DE-EDICAO.md").read_text(encoding="utf-8") == "meu guia"
    assert json.loads((tmp_path / "canal.json").read_text(encoding="utf-8")) == {"nome": "X"}


def test_ressincronizar_mantem_canal_guia_e_cortes_do_editor(tmp_path):
    preparar.preparar(tmp_path, sem_npm=True)
    (tmp_path / "GUIA-DE-EDICAO.md").write_text("meu guia", encoding="utf-8")
    (tmp_path / "editor" / "src" / "Corte.tsx").write_text("velho", encoding="utf-8")
    (tmp_path / "editor" / "public" / "001-x").mkdir(parents=True)
    (tmp_path / "editor" / "public" / "001-x" / "base.mp4").write_bytes(b"x")
    r = preparar.preparar(tmp_path, sem_npm=True, ressincronizar=True)
    assert (tmp_path / "editor" / "src" / "Corte.tsx").read_text(encoding="utf-8") != "velho"
    assert (tmp_path / "editor" / "public" / "001-x" / "base.mp4").exists()
    assert (tmp_path / "GUIA-DE-EDICAO.md").read_text(encoding="utf-8") == "meu guia"
    assert r["editor_atualizado"] is True


def test_editor_copiado_sem_node_modules(tmp_path, plugin_dir):
    nm = plugin_dir / "editor" / "node_modules"
    preparar.preparar(tmp_path, sem_npm=True)
    assert not (tmp_path / "editor" / "node_modules").exists() or not nm.exists()
    assert (tmp_path / "editor" / "package.json").exists()
    assert not (tmp_path / "editor" / "public" / "exemplo").exists()


def test_avisa_quando_o_plugin_mudou_de_versao(tmp_path):
    preparar.preparar(tmp_path, sem_npm=True)
    util.gravar_json(tmp_path / ".fabrica" / "estado.json", {"plugin": "0.9.0", "editor": "0.9.0"})
    r = preparar.estado(tmp_path)
    assert r["editor_desatualizado"] is True and r["versao_editor"] == "0.9.0"
