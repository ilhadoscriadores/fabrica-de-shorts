"""canal.json (o jeito do canal) e corte.json (o plano de cada corte): padrões e conferência em português."""
from __future__ import annotations

import copy
from pathlib import Path

from . import util

PADRAO_CANAL = {
    "versao": 1,
    "nome": "",
    "arroba": "",
    "nicho": "",
    "idioma": "pt",
    "termos_busca": [],
    "ignorar_canais": [],
    "admirados": [],
    "estilo_aprovado": False,
    "estilo": {"cor": "#FFD60A", "fonte": "Montserrat", "legenda_top": 1180, "marca_opacidade": 0.08, "zoom": True},
    "opcoes": {"espelhar": False, "selo": False, "censurar_palavroes": True, "max_segundos": 90},
    "convite_mostrado": False,
}

ENTRADAS = {"zoom", "flash", "slide-esq", "slide-dir"}
MOVIMENTOS = {"in-left", "in-right", "out", "up"}


def _mesclar(base: dict, novo: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (novo or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _mesclar(out[k], v)
        else:
            out[k] = v
    return out


def carregar_canal(pasta=".") -> dict:
    p = Path(pasta) / "canal.json"
    if not p.exists():
        raise util.ErroUsuario("não achei o canal.json nesta pasta. Rode /fabrica-de-shorts:comecar primeiro "
                               "(ou abra o Claude Code na pasta da sua fábrica).")
    return _mesclar(PADRAO_CANAL, util.ler_json(p))


def pasta_trabalho(pasta_corte) -> Path:
    """cortes/NNN-nome → a pasta da fábrica (onde está o canal.json)."""
    return Path(pasta_corte).resolve().parent.parent


def _duracao(arquivo: Path) -> float | None:
    if not arquivo.exists():
        return None
    try:
        return util.sondar(arquivo)["duracao"]
    except Exception:
        return None


def _normalizar_corte(c: dict) -> dict:
    c = dict(c)
    c.setdefault("pausa_max", 0.35)
    c.setdefault("censurar", [])
    c.setdefault("edicao", {})
    corr = c.get("correcoes", [])
    if isinstance(corr, dict):  # formato antigo {"palavra@tempo": "nova"}
        lista = []
        for k, v in corr.items():
            if "@" in k:
                palavra, t = k.rsplit("@", 1)
                lista.append({"t": float(t), "de": palavra, "para": v})
        corr = lista
    c["correcoes"] = corr
    return c


def validar_corte(corte: dict, pasta_corte, etapa: str = "base") -> list[str]:
    """Lista de problemas (vazia = tudo certo). etapa 'base' confere o corte; 'render' confere também a edição."""
    pasta_corte = Path(pasta_corte)
    c = _normalizar_corte(corte)
    erros: list[str] = []
    trechos = c.get("trechos")
    if not isinstance(trechos, list) or not trechos:
        erros.append("o corte.json precisa de \"trechos\": [[início, fim], ...] em segundos do bruto.mp4")
        trechos = []
    dur_bruto = _duracao(pasta_corte / c.get("bruto", "bruto.mp4"))
    if dur_bruto is None:
        erros.append("não achei o bruto.mp4 na pasta do corte (baixe o trecho primeiro)")
    anterior = -1.0
    for i, t in enumerate(trechos, 1):
        if not (isinstance(t, (list, tuple)) and len(t) == 2 and all(isinstance(x, (int, float)) for x in t)):
            erros.append(f"trecho {i} tem que ser [início, fim] em segundos: {t}")
            continue
        a, b = t
        if a < 0 or b <= a:
            erros.append(f"trecho {i} ({a}–{b}): o fim precisa ser depois do início")
        elif dur_bruto is not None and b > dur_bruto + 0.5:
            erros.append(f"trecho {i} ({a}–{b}) passa do fim do bruto ({dur_bruto:.1f} s)")
        if a < anterior:
            erros.append(f"trecho {i} começa antes do fim do trecho anterior: os trechos vão em ordem")
        anterior = b
    pm = c.get("pausa_max")
    if not isinstance(pm, (int, float)) or not 0.1 <= pm <= 2:
        erros.append("pausa_max tem que ficar entre 0.1 e 2 segundos (o padrão é 0.35)")
    for i, x in enumerate(c["censurar"], 1):
        if not isinstance(x, dict) or "t" not in x:
            erros.append(f"censurar {i}: use {{\"t\": segundo_no_bruto, \"palavra\": \"...\"}}")
    for i, x in enumerate(c["correcoes"], 1):
        if not isinstance(x, dict) or not {"t", "de", "para"} <= set(x):
            erros.append(f"correção {i}: use {{\"t\": segundo, \"de\": \"errada\", \"para\": \"certa\"}}")
    if etapa == "render":
        erros += _validar_edicao(c.get("edicao") or {}, pasta_corte)
    return erros


def _validar_edicao(ed: dict, pasta_corte: Path) -> list[str]:
    erros = []
    trab = pasta_trabalho(pasta_corte)
    tl = util.ler_json(pasta_corte / "timeline.json", {}) if (pasta_corte / "timeline.json").exists() else {}
    dur = tl.get("duracao")

    def fora(nome, s, e=None):
        if dur is None:
            return
        fim = e if e is not None else s
        if s < 0 or fim > dur + 0.05:
            erros.append(f"{nome} em {s}–{fim} s fica fora do corte (o corte tem {dur} s)")

    for i, im in enumerate(ed.get("imagens", []), 1):
        arq = im.get("arquivo", "")
        if not (pasta_corte / "imagens" / arq).exists():
            erros.append(f"imagem {i}: não achei imagens/{arq}")
        if im.get("e", 0) <= im.get("s", 0):
            erros.append(f"imagem {i} ({arq}): o fim (e) precisa ser depois do início (s)")
        if im.get("entrada", "zoom") not in ENTRADAS:
            erros.append(f"imagem {i}: entrada tem que ser uma de {sorted(ENTRADAS)}")
        if im.get("movimento", "in-right") not in MOVIMENTOS:
            erros.append(f"imagem {i}: movimento tem que ser um de {sorted(MOVIMENTOS)}")
        fora(f"imagem {i} ({arq})", im.get("s", 0), im.get("e", 0))
    for i, et in enumerate(ed.get("etiquetas", []), 1):
        if not et.get("texto"):
            erros.append(f"etiqueta {i} sem texto")
        fora(f"etiqueta {i}", et.get("s", 0), et.get("e", 0))
    for i, ef in enumerate(ed.get("efeitos", []), 1):
        arq = ef.get("arquivo", "")
        if not (trab / "biblioteca" / "efeitos" / arq).exists():
            erros.append(f"efeito {i}: não achei biblioteca/efeitos/{arq}")
        fora(f"efeito {i}", ef.get("t", 0))
    tr = ed.get("trilha")
    if tr and tr.get("arquivo") and not (trab / "biblioteca" / "trilhas" / tr["arquivo"]).exists():
        erros.append(f"trilha: não achei biblioteca/trilhas/{tr['arquivo']}")
    g = ed.get("gancho")
    if g and not g.get("texto"):
        erros.append("gancho sem texto")
    return erros


def carregar_corte(pasta_corte, etapa: str = "base") -> dict:
    pasta_corte = Path(pasta_corte)
    c = util.ler_json(pasta_corte / "corte.json")
    erros = validar_corte(c, pasta_corte, etapa)
    if erros:
        raise util.ErroUsuario("o corte.json tem problemas:\n- " + "\n- ".join(erros))
    return _normalizar_corte(c)
