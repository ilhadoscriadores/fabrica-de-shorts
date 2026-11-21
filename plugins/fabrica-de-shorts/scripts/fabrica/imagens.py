"""Imagens ilustrativas: o Codex (plano do ChatGPT) gera em paralelo; sem Codex, a lista do que faltou."""
from __future__ import annotations

import os
import re
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import util

GRATIS = ("- ChatGPT (plano grátis gera imagens): https://chatgpt.com\n"
          "- Microsoft Designer / Bing Image Creator (grátis): https://designer.microsoft.com\n"
          "- Google Gemini (grátis): https://gemini.google.com\n"
          "- Leonardo.ai (créditos grátis por dia): https://leonardo.ai")
REGRAS = "No text, no logos, no insignia, no real or recognizable people, no gore."


def _codex() -> list[str] | None:
    """Comando do Codex. No Windows chama o node direto (o .cmd quebra prompt com acento e símbolo)."""
    c = shutil.which("codex")
    if not c:
        return None
    if os.name == "nt" and c.lower().endswith(".cmd"):
        js = Path(c).parent / "node_modules" / "@openai" / "codex" / "bin" / "codex.js"
        node = util.achar("node")
        if js.exists() and node:
            return [node, str(js)]
    return [c]


def _limpar(txt: str) -> str:
    return re.sub(r'[%^&|<>"`]', "", txt)


def gerar(pasta_corte, estilo: str = "", paralelo: int = 4) -> dict:
    pasta = Path(pasta_corte)
    pi = pasta / "imagens"
    pi.mkdir(exist_ok=True)
    lista = [l.split("|", 1) for l in (pi / "prompts.txt").read_text(encoding="utf-8").splitlines()
             if "|" in l and l.strip()] if (pi / "prompts.txt").exists() else []
    if not lista:
        raise util.ErroUsuario("escreva imagens/prompts.txt (uma por linha: nome|descrição da cena)")
    pedidos = [(n.strip(), d.strip()) for n, d in lista if not (pi / f"{n.strip()}.png").exists()]
    cmd = _codex()
    feitas = []
    if cmd and pedidos:
        geradas_dir = Path.home() / ".codex" / "generated_images"
        inicio = time.time()

        def uma(item):
            nome, desc = item
            prompt = _limpar(f"Use your image generation tool to create ONE photorealistic vertical image "
                             f"(portrait 2:3, 1024x1536): {desc}. Style: {estilo or 'cinematic, dramatic light'}. "
                             f"{REGRAS} Save it as imagens/{nome}.png and reply only with the saved path.")
            log = pi / f"log_{nome}.txt"
            try:
                r = util.rodar([*cmd, "exec", "--skip-git-repo-check", "-s", "workspace-write",
                                "--add-dir", str(geradas_dir), "-C", str(pasta), prompt], timeout=900)
                log.write_text((r.stdout or "")[-4000:], encoding="utf-8")
            except Exception as e:
                log.write_text(str(e)[-4000:], encoding="utf-8")
            return nome

        with ThreadPoolExecutor(paralelo) as ex:
            list(ex.map(uma, pedidos))
        # se o Codex salvou só na pasta dele, pega as mais novas
        soltas = sorted((p for p in geradas_dir.rglob("*.png") if p.stat().st_mtime >= inicio),
                        key=lambda p: p.stat().st_mtime) if geradas_dir.exists() else []
        for nome, _ in pedidos:
            if not (pi / f"{nome}.png").exists() and soltas:
                shutil.copy2(soltas.pop(0), pi / f"{nome}.png")
    for nome, _ in lista:
        if (pi / f"{nome.strip()}.png").exists():
            feitas.append(nome.strip())
    faltando = [n.strip() for n, _ in lista if n.strip() not in feitas]
    if faltando:
        txt = ["# Imagens que faltaram", "",
               "Gere cada uma em 9:16 (ou 2:3, em pé), salve aqui na pasta imagens/ com o nome indicado (.png) e rode o render de novo.", ""]
        txt += [f"- **{n}.png**: {d.strip()}" for n, d in lista if n.strip() in faltando]
        txt += ["", "Onde gerar de graça:", GRATIS, "",
                "Regra: nada de pessoa real reconhecível, logo ou texto na imagem."]
        (pi / "FALTANDO.md").write_text("\n".join(txt) + "\n", encoding="utf-8", newline="\n")
    elif (pi / "FALTANDO.md").exists():
        (pi / "FALTANDO.md").unlink()
    return {"ok": True, "geradas": feitas, "faltando": faltando, "codex": bool(cmd)}


def registrar(sub):
    p = sub.add_parser("imagens", help="gera as imagens de imagens/prompts.txt com o Codex (ou lista o que faltou)")
    p.add_argument("--corte", required=True); p.add_argument("--estilo", default="")
    p.set_defaults(func=lambda a: gerar(a.corte, a.estilo))
