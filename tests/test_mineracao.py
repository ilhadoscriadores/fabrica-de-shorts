import csv
import datetime as dt

from fabrica import mineracao, util


def _area(tmp_path):
    util.gravar_json(tmp_path / "canal.json", {"nome": "BO", "arroba": "@bo24horas", "nicho": "policial",
                                               "termos_busca": ["termo a", "termo b"], "ignorar_canais": ["Canal Chato"]})
    (tmp_path / "mineracao").mkdir()
    return tmp_path


def test_minerar_filtra_e_ordena(monkeypatch, tmp_path):
    pasta = _area(tmp_path)
    hoje = dt.date.today()
    base = [
        {"id": "a1", "title": "História boa", "channel": "Cortes X", "duration": 62, "view_count": 3_000_000},
        {"id": "a2", "title": "Longo demais", "channel": "Cortes X", "duration": 400, "view_count": 9_000_000},
        {"id": "a3", "title": "Meu próprio", "channel": "BO 24 Horas", "channel_id": "x", "uploader_id": "@bo24horas",
         "duration": 50, "view_count": 8_000_000},
        {"id": "a4", "title": "Ignorado", "channel": "Canal Chato", "duration": 50, "view_count": 7_000_000},
        {"id": "a5", "title": "Velho demais", "channel": "Cortes Y", "duration": 50, "view_count": 6_000_000},
        {"id": "a6", "title": "Recente", "channel": "Cortes Z", "duration": 80, "view_count": 1_000_000},
    ]
    monkeypatch.setattr(mineracao, "_buscar_yt", lambda termo, sp, limite, idioma: base)
    datas = {"a1": hoje - dt.timedelta(days=200), "a5": hoje - dt.timedelta(days=900), "a6": hoje - dt.timedelta(days=10)}
    monkeypatch.setattr(mineracao, "_detalhes", lambda vid, idioma: {"upload_date": datas[vid].strftime("%Y%m%d")})
    # um corte já feito com o a6 como modelo
    util.gravar_json(pasta / "cortes" / "001-x" / "corte.json", {"modelo": {"url": "https://www.youtube.com/shorts/a6"}})
    saida = mineracao.minerar(pasta, dias=90)
    linhas = list(csv.DictReader(open(saida, encoding="utf-8-sig")))
    ids = [l["url"].rsplit("/", 1)[1] for l in linhas]
    assert ids == ["a1", "a6"]
    assert linhas[0]["recente"] == "nao" and linhas[1]["recente"] == "sim"
    assert linhas[1]["feito"] == "sim" and linhas[0]["feito"] == ""
    assert int(linhas[0]["views"]) == 3_000_000 and linhas[0]["dias"] == "200"
    inicio = dt.datetime.fromisoformat((pasta / ".fabrica" / "missao_inicio.txt").read_text(encoding="utf-8").strip())
    assert abs((dt.datetime.now() - inicio).total_seconds()) < 60  # o cronômetro da missão começa aqui


def test_sp_dos_filtros():
    assert mineracao.SP == {"mes": "CAMSBAgEGAE%3D", "ano": "CAMSBAgFGAE%3D", "sempre": "CAMSAhgB"}


def _linha(i, recente="nao", feito=""):
    return {"views": str(1_000_000 - i * 1000), "duracao": "60", "dias": "100", "recente": recente,
            "feito": feito, "canal": f"Canal {i}", "titulo": f"Video {i}", "url": f"https://www.youtube.com/shorts/v{i}"}


def test_resumo_mostra_recentes_escondidos():
    linhas = [_linha(i, recente="sim" if i in (2, 20, 21, 22) else "nao") for i in range(30)]
    txt = mineracao._resumo(linhas, mostrar=15)
    topo, recentes = txt.split("Recentes (novo):")
    assert topo.count("youtube.com") == 15 and any(l.endswith("/v2") for l in topo.splitlines())
    assert [l.rsplit("/", 1)[1] for l in recentes.strip().splitlines()] == ["v20", "v21", "v22"]


def test_resumo_no_maximo_8_recentes():
    linhas = [_linha(i, recente="sim" if i >= 15 else "nao") for i in range(40)]
    _, recentes = mineracao._resumo(linhas, mostrar=15).split("Recentes (novo):")
    assert len(recentes.strip().splitlines()) == 8


def test_resumo_sem_recentes_escondidos_nao_tem_secao():
    assert "Recentes" not in mineracao._resumo([_linha(i) for i in range(5)], mostrar=15)
