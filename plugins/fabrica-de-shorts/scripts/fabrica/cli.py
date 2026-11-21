"""Entrada única: fabrica.py <comando> [opções]. Cada módulo registra seus comandos."""
from __future__ import annotations

import argparse
import datetime as dt
import importlib
import time
import traceback
from pathlib import Path

from . import util

MODULOS = ["ambiente", "preparar", "mineracao", "origem", "transcricao", "base", "rosto",
           "montagem", "revisao", "entrega", "imagens", "biblioteca"]


def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="fabrica.py", description="Fábrica de Shorts · Ilha dos Criadores")
    sub = p.add_subparsers(dest="comando", required=True)
    for nome in MODULOS:
        try:
            mod = importlib.import_module(f"fabrica.{nome}")
        except ModuleNotFoundError as e:
            if e.name == f"fabrica.{nome}":
                continue
            raise
        if hasattr(mod, "registrar"):
            mod.registrar(sub)
    return p


def _cronometrar(args, inicio: float, ok: bool):
    """Todo comando que trabalha num corte anota o próprio tempo em cortes/NNN/tempos.csv."""
    pasta = getattr(args, "corte", None)
    if not pasta or not Path(pasta).is_dir() or args.comando == "tempo":
        return
    arq = Path(pasta) / "tempos.csv"
    novo = not arq.exists()
    with open(arq, "a", encoding="utf-8", newline="\n") as f:
        if novo:
            f.write("etapa,inicio,segundos,status\n")
        f.write(f"{args.comando},{dt.datetime.fromtimestamp(inicio).isoformat(timespec='seconds')},"
                f"{time.time() - inicio:.1f},{'ok' if ok else 'erro'}\n")


def main(argv=None):
    util._utf8()
    args = construir_parser().parse_args(argv)
    inicio = time.time()
    try:
        dados = args.func(args)
    except util.ErroUsuario as e:
        _cronometrar(args, inicio, False)
        util.resultado({"ok": False, "erro": str(e)}, 1)
    except util.ErroComando as e:
        _cronometrar(args, inicio, False)
        util.resultado({"ok": False, "erro": str(e)}, 2)
    except KeyboardInterrupt:
        util.resultado({"ok": False, "erro": "interrompido"}, 2)
    except Exception as e:  # erro interno: traceback curto para o Claude consertar
        _cronometrar(args, inicio, False)
        traceback.print_exc(limit=6)
        util.resultado({"ok": False, "erro": f"erro interno: {type(e).__name__}: {e}"}, 2)
    _cronometrar(args, inicio, True)
    if isinstance(dados, dict):
        util.resultado(dados, 1 if dados.get("reprovado") else 0)
    util.resultado({"ok": True})
