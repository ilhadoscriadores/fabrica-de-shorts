import pytest

from fabrica import montagem, util


def test_proxima_versao_nao_sobrescreve(tmp_path):
    assert montagem.proxima_versao(tmp_path) == 1
    (tmp_path / "final_v1.mp4").write_bytes(b"x")
    (tmp_path / "final_v2_selo.mp4").write_bytes(b"x")
    assert montagem.proxima_versao(tmp_path) == 3


def test_dados_expande_whoosh_e_bip(corte_sintetico):
    pasta, c = corte_sintetico
    tl = util.ler_json(c / "timeline.json")
    ed = {"imagens": [{"arquivo": "01.png", "s": 1.0, "e": 2.5, "entrada": "flash"}],
          "efeitos": [{"t": 0.5, "arquivo": "impacto/boom-curto.mp3", "vol": 0.4}],
          "gancho": {"texto": "A POLÍCIA CHEGOU", "emoji": "🚨", "ate": 2.0}, "destaques": ["polícia"]}
    util.gravar_json(c / "corte.json", {"trechos": [[0.9, 5.9]], "censurar": [{"t": 3.6, "palavra": "e"}], "edicao": ed})
    from fabrica import base
    base.base(c, rosto=False)
    d = montagem.montar_dados(c)
    srcs = [s["src"] for s in d["sons"]]
    assert any("whoosh" in s for s in srcs), srcs
    assert any("bip" in s for s in srcs)
    bip = next(s for s in d["sons"] if "bip" in s["src"])
    assert 1 <= bip["dur"] <= 30
    assert d["imagens"][0]["f0"] == 30 and d["imagens"][0]["entrada"] == "flash"
    assert d["gancho"]["f1"] == 60
    assert d["duracaoFrames"] == round(util.ler_json(c / "timeline.json")["duracao"] * 30)
    pub = pasta / "editor" / "public"
    for s in [d["base"]["src"]] + srcs + [i["src"] for i in d["imagens"]]:
        assert (pub / s).exists(), s
    palavras = [p for b in d["legenda"]["blocos"] for p in b["palavras"]]
    assert any(p["destaque"] for p in palavras)
    assert (c / "dados.json").exists() and (c / "legendas.json").exists()


def test_sem_trilha_quando_biblioteca_vazia(corte_sintetico):
    _, c = corte_sintetico
    d = montagem.montar_dados(c)
    assert d["trilha"] is None
    assert any("trilha" in a for a in d["_avisos"])


def test_legenda_fora_do_rosto(corte_sintetico):
    _, c = corte_sintetico
    r = util.ler_json(c / "rostos.json")
    # rosto grande bem onde a legenda padrão ficaria (y ≈ 1180–1280 de 1920)
    for a in r["amostras"]:
        a["rostos"] = [{"cx": 0.5, "cy": 0.64, "w": 0.1, "h": 0.06}]
    r["principal"] = [{"t": a["t"], "cx": 0.5, "cy": 0.64, "w": 0.1, "h": 0.06} for a in r["amostras"]]
    util.gravar_json(c / "rostos.json", r)
    d = montagem.montar_dados(c)
    assert d["legenda"]["top"] != 1180


@pytest.mark.lento
def test_render_curto(corte_sintetico, plugin_dir):
    pasta, c = corte_sintetico
    from conftest import _junction
    _junction(plugin_dir / "editor" / "node_modules", pasta / "editor" / "node_modules")
    util.gravar_json(c / "corte.json", {"trechos": [[0.9, 5.9]], "edicao": {
        "imagens": [{"arquivo": "01.png", "s": 1.0, "e": 2.5}],
        "efeitos": [{"t": 0.5, "arquivo": "impacto/boom-curto.mp3"}], "gancho": {"texto": "TESTE", "ate": 1.5}}})
    r = montagem.render(c, revisar=False)
    final = c / "final_v1.mp4"
    assert final.exists() and r["final"].endswith("final_v1.mp4")
    info = util.sondar(final)
    assert (info["largura"], info["altura"]) == (1080, 1920) and info["fps"] == pytest.approx(30)
    assert abs(info["duracao_video"] - info["duracao_audio"]) <= 1 / 30 + 0.03
    from fabrica import audio
    I, TP = audio.medir(final)
    assert I == pytest.approx(-14, abs=1.0) and TP <= -1.0
