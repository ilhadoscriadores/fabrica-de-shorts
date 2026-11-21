"""Mineração viral: Shorts do nicho com mais views (últimos meses + campeões de até 2 anos) numa planilha."""
from __future__ import annotations

import csv
import datetime as dt
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import config, origem, util

# filtro "sp" do YouTube (protobuf em base64): ordenar por views + data + menos de 4 min
SP = {"mes": "CAMSBAgEGAE%3D", "ano": "CAMSBAgFGAE%3D", "sempre": "CAMSAhgB"}
COLUNAS = ["views", "data", "dias", "duracao", "canal", "titulo", "url", "termo", "recente", "feito", "origem"]


def _buscar_yt(termo: str, sp: str, limite: int, idioma: str) -> list[dict]:
    url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(termo) + "&sp=" + sp
    with origem._ydl(origem.opcoes_ydl(idioma, extract_flat=True, skip_download=True, playlistend=limite)) as y:
        info = y.extract_info(url, download=False)
    return list(info.get("entries") or [])


def _detalhes(vid: str, idioma: str) -> dict:
    with origem._ydl(origem.opcoes_ydl(idioma, skip_download=True)) as y:
        info = y.extract_info(f"https://www.youtube.com/shorts/{vid}", download=False)
    return {"upload_date": info.get("upload_date"), "title": info.get("title"), "view_count": info.get("view_count")}


def _feitos(pasta: Path) -> set[str]:
    ids = set()
    for p in (pasta / "cortes").glob("*/corte.json"):
        url = (util.ler_json(p, {}).get("modelo") or {}).get("url") or ""
        if url:
            ids.add(url.rstrip("/").rsplit("/", 1)[-1].split("=")[-1].split("?")[0])
    return ids


def minerar(pasta=".", dias: int = 90, limite: int = 40, max_dur: int = 180, max_idade: int = 730,
            datar_ate: int = 25) -> Path:
    pasta = Path(pasta)
    canal = config.carregar_canal(pasta)
    termos = canal.get("termos_busca") or ([canal["nicho"] + " podcast corte"] if canal.get("nicho") else [])
    if not termos:
        raise util.ErroUsuario("o canal.json não tem termos_busca nem nicho: rode /fabrica-de-shorts:comecar")
    idioma = canal["idioma"]
    meus = {util.normalizar(x) for x in (canal.get("nome", ""), canal.get("arroba", "")) if util.normalizar(x)}
    ignorar = {util.normalizar(x) for x in canal.get("ignorar_canais", [])} | meus
    vistos: dict[str, dict] = {}
    erros = []

    def uma(args):
        termo, sp = args
        try:
            return termo, _buscar_yt(termo, sp, limite, idioma)
        except Exception as e:  # limite do YouTube, rede
            erros.append(f"{termo}: {str(e)[:120]}")
            return termo, []

    with ThreadPoolExecutor(4) as ex:
        for (termo, entradas), faixa in zip(ex.map(uma, [(t, sp) for t in termos for sp in SP.values()]),
                                            [f for _ in termos for f in SP]):
            for e in entradas:
                vid = e.get("id")
                canal_e = (e.get("channel") or e.get("uploader") or "").strip()
                handles = {util.normalizar(canal_e), util.normalizar(e.get("uploader_id") or ""),
                           util.normalizar(e.get("channel_handle") or "")}
                dur = e.get("duration") or 0
                views = e.get("view_count") or 0
                if not vid or (handles & ignorar) or (dur and dur > max_dur):
                    continue
                ordem = {"mes": 0, "ano": 1, "sempre": 2}
                if vid in vistos and ordem[faixa] < ordem[vistos[vid]["faixa"]]:
                    vistos[vid]["faixa"] = faixa
                if vid not in vistos or views > vistos[vid]["views"]:
                    antiga = vistos.get(vid, {}).get("faixa", faixa)
                    vistos[vid] = {"views": views, "duracao": dur, "canal": canal_e, "titulo": e.get("title", ""),
                                   "url": f"https://www.youtube.com/shorts/{vid}", "termo": termo, "id": vid,
                                   "faixa": min(antiga, faixa, key=ordem.get)}
    melhores = sorted(vistos.values(), key=lambda r: -r["views"])[:limite]
    hoje = dt.date.today()

    falhas = []

    def datar(r):
        d = None
        if len(falhas) < 3:  # o YouTube começou a recusar: para de perguntar e fica com a faixa da busca
            try:
                d = _detalhes(r["id"], idioma).get("upload_date")
            except Exception:
                falhas.append(r["id"])
        if d:
            data = dt.datetime.strptime(d, "%Y%m%d").date()
            r["data"] = data.isoformat()
            r["dias"] = (hoje - data).days
        return r

    with ThreadPoolExecutor(4) as ex:
        datados = list(ex.map(datar, melhores[:datar_ate]))
    melhores = datados + melhores[datar_ate:]
    feitos = _feitos(pasta)
    linhas = []
    for r in melhores:
        d = r.get("dias")
        if d is not None and d > max_idade:
            continue
        if d is None:  # sem data exata: usa a faixa da busca (mês / ano / qualquer data)
            dias_txt = {"mes": "<=30", "ano": "<=365"}.get(r["faixa"], "")
            recente = "sim" if r["faixa"] == "mes" else "?"
        else:
            dias_txt, recente = d, ("sim" if d <= dias else "nao")
        linhas.append({"views": r["views"], "data": r.get("data", ""), "dias": dias_txt,
                       "duracao": r["duracao"], "canal": r["canal"], "titulo": r["titulo"], "url": r["url"],
                       "termo": r["termo"], "recente": recente,
                       "feito": "sim" if r["id"] in feitos else "", "origem": ""})
    saida = pasta / "mineracao" / "planilha_virais.csv"
    saida.parent.mkdir(parents=True, exist_ok=True)
    with open(saida, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS)
        w.writeheader()
        w.writerows(linhas)
    minerar.erros = erros
    return saida


def _cmd(args):
    saida = minerar(".", dias=args.dias, limite=args.limite)
    linhas = list(csv.DictReader(open(saida, encoding="utf-8-sig")))
    topo = [f"{int(l['views']):>11,} | {l['duracao']:>3}s | {l['dias'] or '?':>4}d | {'novo' if l['recente'] == 'sim' else '    '}"
            f" | {'FEITO' if l['feito'] else '     '} | {l['canal'][:22]:22} | {l['titulo'][:60]} | {l['url']}"
            for l in linhas[: args.mostrar]]
    print("\n".join(topo))
    return {"ok": bool(linhas), "planilha": str(saida), "total": len(linhas),
            "erros_de_busca": getattr(minerar, "erros", [])[:5]}


def registrar(sub):
    p = sub.add_parser("minerar", help="minera os Shorts mais vistos do nicho (canal.json) para a planilha")
    p.add_argument("--dias", type=int, default=90, help="o que conta como recente (padrão 90)")
    p.add_argument("--limite", type=int, default=40, help="quantos vídeos por busca")
    p.add_argument("--mostrar", type=int, default=15)
    p.set_defaults(func=_cmd)
