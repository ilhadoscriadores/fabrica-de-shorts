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


# ---------- legenda vazia (o YouTube às vezes devolve 200 sem corpo) ----------
VTT_BOM = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\neu tava na mata\n"


class _Resposta:
    def __init__(self, corpo):
        self.corpo = corpo

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self.corpo


def _ydl_com_legenda(downloads=None):
    class FalsoYDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def extract_info(self, url, download=True):
            if download:  # áudio para transcrever
                if downloads is not None:
                    downloads.append(url)
                outtmpl = self.opts["outtmpl"]["default"]
                from pathlib import Path
                Path(outtmpl.replace("%(id)s", "abc").replace("%(ext)s", "m4a")).write_bytes(b"audio")
            return {"id": "abc", "title": "Episódio", "channel": "Podcast",
                    "automatic_captions": {"pt-orig": [{"ext": "vtt", "url": "https://legenda/abc"}]}}
    return FalsoYDL


def _servir(monkeypatch, corpos):
    pedidos = []

    def urlopen(req, timeout=60):
        pedidos.append(req.full_url)
        return _Resposta(corpos[min(len(pedidos), len(corpos)) - 1])
    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    return pedidos


def test_legenda_vazia_tenta_de_novo_e_avisa(monkeypatch, tmp_path):
    monkeypatch.setattr(origem, "_YDL", _ydl_com_legenda())
    esperas = []
    monkeypatch.setattr(origem, "_esperar", esperas.append)
    pedidos = _servir(monkeypatch, [b""])
    r = origem.legenda("https://youtu.be/abc", tmp_path, "pt")
    assert r["txt"] is None
    assert r["aviso"].startswith("legenda vazia: o YouTube recusou; tente de novo em 1 minuto")
    assert "use --transcrever" not in r["aviso"]  # o achar não tem esse parâmetro
    assert "`FAB legenda https://youtu.be/abc --transcrever`" in r["aviso"]
    assert len(pedidos) == 3 and esperas == [5, 15]
    assert not list(tmp_path.glob("*.vtt"))


def test_legenda_so_com_cabecalho_conta_como_vazia(monkeypatch, tmp_path):
    monkeypatch.setattr(origem, "_YDL", _ydl_com_legenda())
    monkeypatch.setattr(origem, "_esperar", lambda s: None)
    pedidos = _servir(monkeypatch, [b"WEBVTT\nKind: captions\n\n", VTT_BOM.encode()])
    r = origem.legenda("https://youtu.be/abc", tmp_path, "pt")
    assert len(pedidos) == 2
    assert r["txt"] and "eu tava na mata" in (tmp_path / "abc.txt").read_text(encoding="utf-8")


def test_vtt_vazio_em_cache_e_apagado_e_baixado_de_novo(monkeypatch, tmp_path):
    (tmp_path / "abc.pt-orig.vtt").write_bytes(b"")
    monkeypatch.setattr(origem, "_YDL", _ydl_com_legenda())
    monkeypatch.setattr(origem, "_esperar", lambda s: None)
    pedidos = _servir(monkeypatch, [VTT_BOM.encode()])
    r = origem.legenda("https://youtu.be/abc", tmp_path, "pt")
    assert len(pedidos) == 1
    assert r["txt"] and (tmp_path / "abc.pt-orig.vtt").read_text(encoding="utf-8") == VTT_BOM


def test_legenda_vazia_com_transcrever_transcreve(monkeypatch, tmp_path):
    from fabrica import transcricao
    baixados = []
    monkeypatch.setattr(origem, "_YDL", _ydl_com_legenda(baixados))
    monkeypatch.setattr(origem, "_esperar", lambda s: None)
    _servir(monkeypatch, [b""])
    monkeypatch.setattr(transcricao, "transcrever",
                        lambda audio, saida, modelo, idioma: [{"w": "eu", "s": 1.0, "e": 1.2}, {"w": "tava", "s": 1.3, "e": 1.6}])
    r = origem.legenda("https://youtu.be/abc", tmp_path, "pt", transcrever_se_faltar=True)
    assert r.get("transcrito") is True and baixados
    assert "eu tava" in (tmp_path / "abc.txt").read_text(encoding="utf-8")


def test_achar_episodio_sem_legenda_tem_erro(monkeypatch, tmp_path):
    ref = tmp_path / "ref.txt"
    ref.write_text("00:00:01 eu tava na mata\n", encoding="utf-8")
    aviso = "legenda vazia: o YouTube recusou; tente de novo em 1 minuto"

    def legenda(url, pasta, idioma="pt", transcrever_se_faltar=False):
        if "modelo" in url:
            return {"txt": str(ref), "titulo": "corte"}
        return {"txt": None, "titulo": "Episódio 1", "aviso": aviso}
    monkeypatch.setattr(origem, "legenda", legenda)
    r = origem.achar("https://youtu.be/modelo", tmp_path, candidatos=["https://youtu.be/ep1"])
    ep = r["episodios"][0]
    assert "regioes" not in ep and ep["titulo"] == "Episódio 1"
    assert ep["erro"] == ("sem legenda: tente o vídeo do próprio canal do podcast ou "
                          "`FAB legenda https://youtu.be/ep1 --transcrever` (demora) e depois "
                          "`FAB achar https://youtu.be/modelo --candidatos https://youtu.be/ep1`")


def _ydl_sem_legenda():
    class FalsoYDL:
        def __init__(self, opts):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def extract_info(self, url, download=True):
            assert not download, "não pode baixar nem transcrever de novo"
            return {"id": url.rsplit("/", 1)[-1], "title": "Episódio", "channel": "Podcast"}
    return FalsoYDL


def test_achar_usa_a_transcricao_feita_pelo_legenda(monkeypatch, tmp_path):
    frase = "eu tava deitado no chão da mata e comecei a rezar baixinho"
    (tmp_path / "modelo.pt.vtt").write_text(f"WEBVTT\n\n00:00:01.000 --> 00:00:05.000\n{frase}\n", encoding="utf-8")
    util.gravar_json(tmp_path / "ep1.words.json",  # o que o `FAB legenda <url> --transcrever` deixou
                     [{"w": w, "s": 100 + i * 0.4, "e": 100.3 + i * 0.4} for i, w in enumerate(frase.split())])
    monkeypatch.setattr(origem, "_YDL", _ydl_sem_legenda())
    r = origem.achar("https://youtu.be/modelo", tmp_path, candidatos=["https://youtu.be/ep1"])
    ep = r["episodios"][0]
    assert "erro" not in ep, ep
    assert ep["regioes"] and ep["regioes"][0]["inicio"] == pytest.approx(98, abs=1)


def test_links_da_descricao():
    desc = ("Vídeo completo: https://www.youtube.com/watch?v=ng-Q6ZD0XmI&t=120s\n"
            "parte 2: https://youtu.be/68L5Flrr0Mo?si=x | live https://www.youtube.com/live/AbC_123-xyZ\n"
            "original: Q6ZD0XmIng1 · repetido youtu.be/ng-Q6ZD0XmI · o próprio Short youtu.be/SHORTabc123\n"
            "Episódio original: Inteligente demais")
    assert origem.links_da_descricao(desc, ignorar="SHORTabc123") == [
        "https://www.youtube.com/watch?v=ng-Q6ZD0XmI", "https://www.youtube.com/watch?v=68L5Flrr0Mo",
        "https://www.youtube.com/watch?v=AbC_123-xyZ", "https://www.youtube.com/watch?v=Q6ZD0XmIng1"]
    assert origem.links_da_descricao("vídeo completo:  dQw4w9WgXcQ") == ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"]
    assert origem.links_da_descricao(None) == []


def test_legenda_devolve_os_links_da_descricao_inteira(monkeypatch, tmp_path):
    ydl = _ydl_com_legenda()
    orig = ydl.extract_info

    def extract_info(self, url, download=True):
        return {**orig(self, url, download), "description": "x" * 900 + " vídeo completo: youtu.be/ng-Q6ZD0XmI"}
    monkeypatch.setattr(ydl, "extract_info", extract_info)
    monkeypatch.setattr(origem, "_YDL", ydl)
    _servir(monkeypatch, [VTT_BOM.encode()])
    r = origem.legenda("https://youtu.be/abc", tmp_path, "pt")
    assert r["links_na_descricao"] == ["https://www.youtube.com/watch?v=ng-Q6ZD0XmI"]


def test_achar_poe_o_link_da_descricao_antes_da_busca(monkeypatch, tmp_path):
    ref = tmp_path / "ref.txt"
    ref.write_text("00:00:01 eu tava na mata\n", encoding="utf-8")
    vistos = []
    ep = "https://www.youtube.com/watch?v=ng-Q6ZD0XmI"

    def legenda(url, pasta, idioma="pt", transcrever_se_faltar=False):
        if "modelo" in url:
            return {"txt": str(ref), "links_na_descricao": [ep]}
        vistos.append(url)
        return {"txt": None}
    monkeypatch.setattr(origem, "legenda", legenda)
    monkeypatch.setattr(origem, "buscar", lambda termo, limite, longos, idioma: [
        {"url": "https://www.youtube.com/watch?v=outro123456"}, {"url": ep}])
    origem.achar("https://youtu.be/modelo", tmp_path, busca="honorio")
    assert vistos == [ep, "https://www.youtube.com/watch?v=outro123456"]


def test_vtt_decodifica_entidades_html():
    vtt = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\neu&nbsp;tava &amp; voc&ecirc; disse &quot;oi&quot; &gt;&gt; d&#39;\n"
    assert origem.vtt_para_linhas(vtt) == [(1.0, "eu tava & você disse \"oi\" >> d'")]


# ---------- baixar: ffmpeg do yt-dlp falha às vezes ----------
def _ydl_que_falha(tmp_path, falhas):
    chamadas = []

    class FalsoYDL:
        def __init__(self, opts):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def extract_info(self, url, download=True):
            chamadas.append(url)
            if len(chamadas) <= falhas:
                (tmp_path / "bruto.f137.mp4.part").write_bytes(b"resto")
                (tmp_path / "bruto.mp4").write_bytes(b"pela metade")
                raise Exception("ERROR: ffmpeg exited with code 3199971767")
            assert not list(tmp_path.glob("bruto*")), "sobrou resto da tentativa anterior"
            (tmp_path / "bruto.mp4").write_bytes(b"x")
            return {"title": "Episódio", "channel": "Podcast", "duration": 1000}
    return FalsoYDL, chamadas


def test_baixar_tenta_de_novo_quando_o_ffmpeg_falha(monkeypatch, tmp_path):
    ydl, chamadas = _ydl_que_falha(tmp_path, falhas=1)
    monkeypatch.setattr(origem, "_YDL", ydl)
    monkeypatch.setattr(origem.util, "sondar", lambda p: {"duracao": 30.0})
    r = origem.baixar("https://youtu.be/abc", 10, 20, tmp_path)
    assert r["ok"] and len(chamadas) == 2
    assert sorted(p.name for p in tmp_path.glob("bruto*")) == ["bruto.mp4"]


def test_baixar_falha_duas_vezes_da_erro_curto(monkeypatch, tmp_path):
    ydl, chamadas = _ydl_que_falha(tmp_path, falhas=2)
    monkeypatch.setattr(origem, "_YDL", ydl)
    with pytest.raises(util.ErroComando) as e:
        origem.baixar("https://youtu.be/abc", 10, 20, tmp_path)
    assert len(chamadas) == 2
    msg = str(e.value)
    assert msg.startswith("não consegui baixar o trecho") and "Traceback" not in msg and len(msg) < 300
    assert not list(tmp_path.glob("bruto*"))  # nada pela metade que pareça um bruto pronto
