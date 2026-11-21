"""Monta a pasta de trabalho da fábrica: pastas, biblioteca inicial, editor Remotion, GUIA e canal.json."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from . import __version__, config, util

PASTAS = ["mineracao", "cortes", "biblioteca/efeitos", "biblioteca/trilhas", ".fabrica/tmp"]
IGNORAR_EDITOR = {"node_modules", "out", ".remotion"}
EDITOR_ARQUIVOS = ["package.json", "package-lock.json", "tsconfig.json", "remotion.config.ts"]


def _hash(p: Path) -> str:
    return hashlib.sha1(p.read_bytes()).hexdigest()[:12] if p.exists() else ""


def _copiar_editor(origem: Path, destino: Path, ressincronizar: bool) -> bool:
    """Copia o editor do plugin. Nunca leva node_modules nem as pastas dos cortes em public/."""
    if (destino / "package.json").exists() and not ressincronizar:
        return False
    destino.mkdir(parents=True, exist_ok=True)
    for nome in EDITOR_ARQUIVOS:
        if (origem / nome).exists():
            shutil.copy2(origem / nome, destino / nome)
    if (destino / "src").exists():
        shutil.rmtree(destino / "src")
    shutil.copytree(origem / "src", destino / "src")
    (destino / "public").mkdir(exist_ok=True)
    for item in (origem / "public").iterdir():
        if item.name == "exemplo":
            continue
        alvo = destino / "public" / item.name
        if item.is_dir():
            if alvo.exists():
                shutil.rmtree(alvo)
            shutil.copytree(item, alvo)
        else:
            shutil.copy2(item, alvo)
    return True


def _copiar_efeitos(origem: Path, biblioteca: Path) -> int:
    n = 0
    for f in origem.rglob("*"):
        if f.is_file() and f.suffix.lower() in (".mp3", ".wav", ".ogg"):
            alvo = biblioteca / "efeitos" / f.relative_to(origem)
            if not alvo.exists():
                alvo.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, alvo)
                n += 1
    lic = biblioteca / "LICENCAS.md"
    if not lic.exists():
        cc0 = (origem / "LICENCAS.md").read_text(encoding="utf-8").split("\n", 2)[2]
        lic.write_text("# Licenças da sua biblioteca\n\n"
                       "Toda trilha ou efeito que entrar aqui precisa ter a licença anotada. "
                       "Se a licença pedir crédito, a Fábrica coloca o crédito no POSTAGEM.txt.\n\n"
                       "## Pacote inicial (veio com a Fábrica de Shorts)\n" + cc0, encoding="utf-8", newline="\n")
    return n


def npm_install(editor: Path):
    util.rodar(["npm", "install", "--no-audit", "--no-fund", "--loglevel=error"], cwd=editor, timeout=1800)


def estado(pasta) -> dict:
    est = util.ler_json(Path(pasta) / ".fabrica" / "estado.json", {})
    v = est.get("editor")
    return {"versao_plugin": __version__, "versao_editor": v,
            "editor_desatualizado": bool(v) and v != __version__}


def preparar(pasta=".", sem_npm: bool = False, ressincronizar: bool = False, respostas: dict | None = None) -> dict:
    pasta = Path(pasta).resolve()
    plugin = util.raiz_plugin()
    feito = []
    for d in PASTAS:
        (pasta / d).mkdir(parents=True, exist_ok=True)
    n = _copiar_efeitos(plugin / "assets" / "efeitos-cc0", pasta / "biblioteca")
    if n:
        feito.append(f"{n} efeitos CC0 na biblioteca")
    guia = pasta / "GUIA-DE-EDICAO.md"
    if not guia.exists():
        shutil.copy2(plugin / "modelos" / "GUIA-DE-EDICAO.md", guia)
        feito.append("GUIA-DE-EDICAO.md criado")
    canal = pasta / "canal.json"
    if not canal.exists():
        dados = config._mesclar(config.PADRAO_CANAL, respostas or {})
        canal.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        feito.append("canal.json criado")
    elif respostas:
        dados = config._mesclar(util.ler_json(canal), respostas)
        canal.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    editor = pasta / "editor"
    est_path = pasta / ".fabrica" / "estado.json"
    est = util.ler_json(est_path, {})
    atualizado = _copiar_editor(plugin / "editor", editor, ressincronizar)
    if atualizado:
        feito.append("editor copiado" if not ressincronizar else "editor atualizado")
    pacote = _hash(editor / "package.json")
    precisa_npm = not (editor / "node_modules").exists() or est.get("pacote") != pacote
    if precisa_npm and not sem_npm:
        npm_install(editor)
        feito.append("npm install no editor")
    est.update(plugin=__version__, pacote=pacote if (not precisa_npm or not sem_npm) else est.get("pacote", ""))
    if atualizado or "editor" not in est:
        est["editor"] = __version__
    util.gravar_json(est_path, est)
    return {"ok": True, "pasta": str(pasta), "feito": feito, "editor_atualizado": atualizado,
            "npm_pendente": precisa_npm and sem_npm}


def _cmd(args):
    respostas = {k: v for k, v in (("nome", args.nome), ("arroba", args.arroba), ("nicho", args.nicho),
                                    ("idioma", args.idioma)) if v}
    return preparar(".", sem_npm=args.sem_npm, ressincronizar=args.ressincronizar, respostas=respostas or None)


def _cmd_estado(args):
    return {"ok": True, **estado(".")}


def registrar(sub):
    p = sub.add_parser("preparar", help="cria/atualiza a pasta de trabalho (pastas, biblioteca, editor)")
    p.add_argument("--sem-npm", action="store_true", help="não roda o npm install")
    p.add_argument("--ressincronizar", action="store_true", help="atualiza o editor para a versão do plugin")
    p.add_argument("--nome"); p.add_argument("--arroba"); p.add_argument("--nicho"); p.add_argument("--idioma")
    p.set_defaults(func=_cmd)
    e = sub.add_parser("estado", help="versão do plugin e do editor desta pasta")
    e.set_defaults(func=_cmd_estado)
