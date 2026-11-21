"""Biblioteca de efeitos e trilhas: índice curto (o que já foi usado nos últimos cortes) e o kit grátis do Mixkit."""
from __future__ import annotations

import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import util

AUDIO = (".mp3", ".wav", ".ogg", ".m4a")


def _usados(pasta: Path, ultimos: int = 3) -> set[str]:
    cortes = sorted((p for p in (pasta / "cortes").glob("*/corte.json")), key=lambda p: p.parent.name)[-ultimos:]
    out = set()
    for c in cortes:
        ed = util.ler_json(c, {}).get("edicao") or {}
        out |= {e.get("arquivo", "") for e in ed.get("efeitos", [])}
        if ed.get("trilha"):
            out.add(ed["trilha"].get("arquivo", ""))
    return out


def indice(pasta=".") -> dict:
    pasta = Path(pasta)
    usados = _usados(pasta)
    out = {}
    for tipo in ("efeitos", "trilhas"):
        base = pasta / "biblioteca" / tipo
        grupos: dict[str, list[str]] = {}
        for f in sorted(base.rglob("*")) if base.exists() else []:
            if f.suffix.lower() in AUDIO:
                rel = f.relative_to(base).as_posix()
                cat = rel.split("/", 1)[0] if "/" in rel else "(solto)"
                grupos.setdefault(cat, []).append(f.name + (" (usado)" if rel in usados else ""))
        out[tipo] = grupos
    return out


def _baixar(url: str, destino: Path):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        destino.write_bytes(r.read())


def baixar_kit(pasta=".", tipos=("trilhas", "efeitos")) -> dict:
    """Baixa do próprio Mixkit (licença grátis, sem crédito) as trilhas e efeitos da lista do plugin."""
    pasta = Path(pasta)
    kit = util.ler_json(util.raiz_plugin() / "assets" / "kit-mixkit.json")
    itens = []
    for tipo in tipos:
        for it in kit[tipo]:
            itens.append((tipo, it))
    feitos, erros = [], []

    def um(par):
        tipo, it = par
        destino = pasta / "biblioteca" / tipo / it["arquivo"]
        if destino.exists():
            return None
        destino.parent.mkdir(parents=True, exist_ok=True)
        try:
            _baixar(it["url"], destino)
            return (tipo, it)
        except Exception as e:
            erros.append(f"{it['titulo']}: {str(e)[:80]}")
            return None

    with ThreadPoolExecutor(4) as ex:
        feitos = [x for x in ex.map(um, itens) if x]
    if feitos:
        lic = pasta / "biblioteca" / "LICENCAS.md"
        linhas = ["", "## Kit Mixkit (baixado pela Fábrica direto do mixkit.co)", "",
                  f"Músicas: {kit['licenca_musica']}", f"Efeitos: {kit['licenca_efeitos']}", "",
                  "| Arquivo | Título | Fonte | Crédito |", "|---|---|---|---|"]
        linhas += [f"| {tipo}/{it['arquivo']} | {it['titulo']} | {it['url']} | não precisa |" for tipo, it in feitos]
        with open(lic, "a", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(linhas) + "\n")
    mb = sum((pasta / "biblioteca" / t / it["arquivo"]).stat().st_size for t, it in feitos) / 1e6
    return {"ok": not erros or bool(feitos), "baixados": len(feitos), "mb": round(mb, 1), "erros": erros[:5]}


def _cmd_indice(args):
    ind = indice(".")
    for tipo, grupos in ind.items():
        print(f"## {tipo}")
        for cat, arqs in grupos.items():
            print(f"{cat}: {', '.join(arqs)}")
    return {"ok": True, "efeitos": sum(len(v) for v in ind["efeitos"].values()),
            "trilhas": sum(len(v) for v in ind["trilhas"].values())}


def registrar(sub):
    p = sub.add_parser("biblioteca", help="lista efeitos e trilhas por pasta, marcando os usados nos últimos 3 cortes")
    p.set_defaults(func=_cmd_indice)
    p = sub.add_parser("baixar-kit", help="baixa o kit grátis do Mixkit (trilhas por clima + efeitos)")
    p.add_argument("--so", choices=["trilhas", "efeitos"])
    p.set_defaults(func=lambda a: baixar_kit(".", (a.so,) if a.so else ("trilhas", "efeitos")))
