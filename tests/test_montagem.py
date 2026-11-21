import os
import time
from pathlib import Path

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


@pytest.mark.parametrize("mudanca", [{"trechos": [[0.9, 4.4]]}, {"correcoes": [{"t": 1.0, "de": "olha", "para": "Olha"}]},
                                     {"censurar": [{"t": 2.3, "palavra": "a"}]}, {"pausa_max": 0.5}, {"espelhar": True}])
def test_plano_mudou_pede_base_de_novo(corte_sintetico, mudanca):
    _, c = corte_sintetico
    assert util.ler_json(c / "timeline.json")["hash_plano"]
    corte = util.ler_json(c / "corte.json")
    util.gravar_json(c / "corte.json", {**corte, "edicao": {"gancho": {"texto": "SÓ A EDIÇÃO MUDOU"}}})
    montagem.montar_dados(c)  # edição não muda a base
    util.gravar_json(c / "corte.json", {**corte, **mudanca})
    with pytest.raises(util.ErroUsuario) as e:
        montagem.montar_dados(c)
    assert "FAB base" in str(e.value) and "de novo antes do render" in str(e.value)


def test_public_fica_so_com_o_corte_atual(corte_sintetico):
    """O Remotion copia o public/ inteiro a cada render: pastas de cortes antigos não podem se acumular."""
    pasta, c = corte_sintetico
    pub = pasta / "editor" / "public"
    velho, outro_render = pub / "007-velho", pub / "008-renderizando-agora"
    for p in (velho / "sfx", outro_render):
        p.mkdir(parents=True)
    (velho / "base.mp4").write_bytes(b"x")
    (pub / "exemplo").mkdir(exist_ok=True)
    antigo = time.time() - 6 * 3600
    for p in (velho, pub / "exemplo", pub / "fontes", pub / "ilha-logo.png"):
        os.utime(p, (antigo, antigo))
    montagem.montar_dados(c)
    assert not velho.exists()
    assert outro_render.exists()  # mexida agora: pode ser outro corte renderizando ao mesmo tempo
    assert (pub / c.name / "base.mp4").exists()
    for fica in ("fontes", "exemplo", "ilha-logo.png"):
        assert (pub / fica).exists(), fica


def test_render_apaga_a_pasta_do_corte_no_public_mesmo_com_erro(corte_sintetico, monkeypatch):
    pasta, c = corte_sintetico
    (pasta / "editor" / "node_modules").mkdir(exist_ok=True)

    def falha(*a, **k):
        assert (pasta / "editor" / "public" / c.name / "base.mp4").exists()
        raise util.ErroComando("remotion falhou")
    monkeypatch.setattr(montagem, "_npx_render", falha)
    with pytest.raises(util.ErroComando):
        montagem.render(c, revisar=False)
    assert not (pasta / "editor" / "public" / c.name).exists()
    assert (c / "base.mp4").exists()  # o link no public sai; a base do corte fica


def _ligar_selo(pasta):
    canal = util.ler_json(pasta / "canal.json")
    canal.setdefault("opcoes", {})["selo"] = True
    util.gravar_json(pasta / "canal.json", canal)


def test_render_revisa_o_final_antes_do_selo(corte_sintetico, monkeypatch):
    """Falha no selo não pode deixar o final_vN.mp4 sem revisão (nem os temporários grandes no disco)."""
    pasta, c = corte_sintetico
    (pasta / "editor" / "node_modules").mkdir(exist_ok=True)
    _ligar_selo(pasta)

    def remotion_falso(editor, comp, saida, extra, env):
        if comp == "Selo":
            raise util.ErroComando("remotion falhou no selo")
        dur = util.ler_json(c / "dados.json")["duracaoFrames"] / 30
        util.rodar([util.ffmpeg(), "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=gray:s=1080x1920:r=30:d={dur}",
                    "-f", "lavfi", "-i", f"sine=d={dur}:sample_rate=48000", "-c:v", "libx264", "-preset", "ultrafast",
                    "-c:a", "pcm_s16le", str(saida)])
    monkeypatch.setattr(montagem, "_npx_render", remotion_falso)
    from fabrica import revisao
    revisados = []
    monkeypatch.setattr(revisao, "revisar", lambda video, pasta_corte: revisados.append(Path(video).name) or
                        {"aprovado": True, "erros": [], "avisos": [], "relatorio": str(c / "revisao.md")})
    with pytest.raises(util.ErroComando):
        montagem.render(c)
    assert revisados == ["final_v1.mp4"] and (c / "final_v1.mp4").exists()
    assert not list((pasta / ".fabrica" / "tmp").glob(f"{c.name}_v1*"))


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
    assert "pico_dbtp" not in r and r["pico_master_dbtp"] <= -1.0  # pico do master (antes do AAC)
    assert not (pasta / "editor" / "public" / c.name).exists()


@pytest.mark.lento
def test_render_com_selo(corte_sintetico, plugin_dir):
    pasta, c = corte_sintetico
    from conftest import _junction
    _junction(plugin_dir / "editor" / "node_modules", pasta / "editor" / "node_modules")
    _ligar_selo(pasta)
    util.gravar_json(c / "corte.json", {"trechos": [[0.9, 5.9]], "edicao": {
        "gancho": {"texto": "TESTE", "ate": 1.5}, "selo": {"inicio": 1.0, "lado": "dir", "cor": "#ff3b3b"}}})
    r = montagem.render(c, revisar=False)
    final, com = c / "final_v1.mp4", c / "final_v1_selo.mp4"
    assert final.exists() and com.exists() and r["final_selo"] == str(com)
    a, b = util.sondar(final), util.sondar(com)
    assert (a["largura"], a["altura"]) == (b["largura"], b["altura"]) == (1080, 1920)
    assert b["duracao"] == pytest.approx(a["duracao"], abs=0.05)
    assert b["duracao_video"] == pytest.approx(a["duracao_video"], abs=1 / 30 + 0.01)


def test_resumo_da_revisao_conta_todos_os_erros():
    rv = {"aprovado": False, "erros": [f"erro {i}" for i in range(12)], "avisos": [], "relatorio": "revisao.md"}
    r = montagem._resumo_revisao(rv)
    assert len(r["erros"]) == 8 and r["erros_total"] == 12 and r["aprovado"] is False
