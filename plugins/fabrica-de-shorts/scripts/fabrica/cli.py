"""Entrada única: fabrica.py <comando> [opções]. Cada módulo registra seus comandos."""
from __future__ import annotations

import argparse
import importlib
import traceback

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


def main(argv=None):
    util._utf8()
    args = construir_parser().parse_args(argv)
    try:
        dados = args.func(args)
    except util.ErroUsuario as e:
        util.resultado({"ok": False, "erro": str(e)}, 1)
    except util.ErroComando as e:
        util.resultado({"ok": False, "erro": str(e)}, 2)
    except KeyboardInterrupt:
        util.resultado({"ok": False, "erro": "interrompido"}, 2)
    except Exception as e:  # erro interno: traceback curto para o Claude consertar
        traceback.print_exc(limit=6)
        util.resultado({"ok": False, "erro": f"erro interno: {type(e).__name__}: {e}"}, 2)
    if isinstance(dados, dict):
        util.resultado(dados, 1 if dados.get("reprovado") else 0)
    util.resultado({"ok": True})
