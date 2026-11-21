"""Achar o trecho pelo som (corte de live da Twitch/Kick ou vídeo sem legenda)."""
import numpy as np

from fabrica import origem, origem_audio as oa


def _vod(seg=1800, seed=1):
    rng = np.random.default_rng(seed)
    # "fala": ruído modulado, para não ser periódico
    x = rng.standard_normal(seg * oa.SR).astype(np.float32)
    x *= (0.3 + np.abs(np.sin(np.arange(len(x)) / 997.0))).astype(np.float32)
    return x


def test_localizar_acha_o_corte_dentro_da_vod_mesmo_com_ruido_e_volume_diferente():
    vod = _vod()
    ini = 1234.5
    corte = vod[int(ini * oa.SR):int((ini + 28) * oa.SR)] * 0.4
    corte = corte + 0.15 * np.random.default_rng(9).standard_normal(len(corte)).astype(np.float32)  # trilha/compressão
    reg = oa.localizar(corte, vod)
    assert reg and reg[0]["acertos"] == 3
    assert abs(reg[0]["inicio"] + 2.0 - ini) < 0.1  # 2 s de folga antes
    assert reg[0]["inicio_hms"] == "0:20:32" and reg[0]["por"] == "audio"


def test_localizar_nao_inventa_quando_o_corte_e_de_outra_vod():
    corte = _vod(60, seed=2)[:28 * oa.SR]
    assert oa.localizar(corte, _vod(seed=3)) == []


def test_corte_com_vinheta_no_comeco_ainda_acha():
    """O começo do Reel tem vinheta que não está na live: os pedaços saem do meio para o fim."""
    vod = _vod()
    corte = np.concatenate([_vod(6, seed=5)[:6 * oa.SR], vod[600 * oa.SR:622 * oa.SR]])
    reg = oa.localizar(corte, vod)
    assert reg and abs(reg[0]["inicio"] + 2.0 - (600 - 6)) < 0.1


class _YdlCanal:
    def __init__(self, opts):
        self.opts = opts

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def extract_info(self, url, download=False):
        if url.endswith("/videos"):
            return {"entries": [{"url": f"https://www.twitch.tv/videos/{n}"} for n in (5, 4, 3, 2, 1)]}
        return {"id": url.rsplit("/", 1)[-1]}


def test_pagina_de_videos_do_canal_vira_as_ultimas_vods(monkeypatch):
    monkeypatch.setattr(origem, "_YDL", _YdlCanal)
    lista = origem.expandir_candidatos(["https://www.twitch.tv/fulano/videos", "https://www.twitch.tv/videos/99",
                                        "https://www.youtube.com/watch?v=abc"])
    assert lista == [f"https://www.twitch.tv/videos/{n}" for n in (5, 4, 3, 2)] + \
        ["https://www.twitch.tv/videos/99", "https://www.youtube.com/watch?v=abc"]


def test_achar_sem_resultado_explica_o_que_fazer(monkeypatch, tmp_path):
    """Antes: "episodios": [] sem dizer nada. Agora: dica com o link de vídeos da Twitch quando o corte cita a Twitch."""
    txt = tmp_path / "X.txt"
    txt.write_text("00:00:01 whoa whoa this is like in the movies\n", encoding="utf-8")
    monkeypatch.setattr(origem, "legenda", lambda url, pasta, idioma="pt", transcrever_se_faltar=False: {
        "titulo": "Video by fulano", "canal": "Fulano", "descricao": "#gta6 #twitchstreamer", "txt": str(txt)})
    monkeypatch.setattr(origem, "buscar", lambda *a, **k: [])
    r = origem.achar("https://www.instagram.com/reel/X/", tmp_path, busca="fulano gta")
    assert r["episodios"] == []
    assert "https://www.twitch.tv/fulano/videos" in r["dica"] and "--candidatos" in r["dica"]


def test_achar_sem_texto_do_modelo_tambem_da_a_dica(monkeypatch, tmp_path):
    import pytest
    from fabrica import util
    monkeypatch.setattr(origem, "legenda", lambda *a, **k: {"titulo": "x", "canal": "c", "descricao": "", "txt": None})
    with pytest.raises(util.ErroUsuario, match="--candidatos"):
        origem.achar("https://www.instagram.com/reel/X/", tmp_path)


def test_achar_pula_live_depois_do_corte_e_para_quando_acha(monkeypatch, tmp_path):
    """A live mais nova (depois do Reel) não é baixada; achou com folga, as outras também não."""
    datas = {"https://www.twitch.tv/videos/3": 1795300000,  # 22/11 (depois do corte de 20/11)
             "https://www.twitch.tv/videos/2": 1795110000,  # 20/11
             "https://www.twitch.tv/videos/1": 1795000000}  # 19/11

    class Ydl(_YdlCanal):
        def extract_info(self, url, download=False):
            return {"id": url.rsplit("/", 1)[-1], "title": "live", "duration": 36000, "timestamp": datas.get(url)}

    baixados = []
    monkeypatch.setattr(origem, "_YDL", Ydl)
    monkeypatch.setattr(origem, "legenda", lambda *a, **k: {"titulo": "Reel", "canal": "c", "data": "20261120", "txt": None})
    monkeypatch.setattr(oa, "baixar_audio", lambda url, pasta, ydl: baixados.append(url) or url)
    monkeypatch.setattr(oa, "ler", lambda caminho: np.ones(100 * oa.SR, np.float32))
    monkeypatch.setattr(oa, "localizar", lambda ref, ep: [{"inicio": 10.0, "fim": 40.0, "acertos": 3}])
    r = origem.achar("https://www.instagram.com/reel/X/", tmp_path, candidatos=list(datas))
    assert baixados == ["https://www.instagram.com/reel/X/", "https://www.twitch.tv/videos/2"]
    assert "pulada" in r["episodios"][-1] or "pulada" in r["episodios"][0]
    assert r["episodios"][0]["url"] == "https://www.twitch.tv/videos/2" and "dica" not in r
