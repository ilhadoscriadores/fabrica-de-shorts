"""Entrega: pasta do corte novo, cronômetro, capa e POSTAGEM.txt."""
from __future__ import annotations

import csv
import datetime as dt
import re
from pathlib import Path

from . import config, util

AGORA = lambda: dt.datetime.now().isoformat(timespec="seconds")  # noqa: E731


def _inicio_da_missao(pasta: Path) -> str:
    """O minerar grava .fabrica/missao_inicio.txt: com menos de 3 h, a missão começou lá (minerar e achar contam)."""
    marca = pasta / ".fabrica" / "missao_inicio.txt"
    if not marca.exists():
        return AGORA()
    try:
        ini = dt.datetime.fromisoformat(marca.read_text(encoding="utf-8").strip())
        idade = (dt.datetime.now() - ini).total_seconds()
    except (ValueError, OSError):
        idade = None
    marca.unlink(missing_ok=True)
    return ini.isoformat(timespec="seconds") if idade is not None and 0 <= idade < 3 * 3600 else AGORA()


def novo_corte(pasta, nome: str) -> Path:
    cortes = Path(pasta) / "cortes"
    cortes.mkdir(parents=True, exist_ok=True)
    nums = [int(m.group(1)) for p in cortes.iterdir() if p.is_dir() and (m := re.match(r"(\d{3})-", p.name))]
    destino = cortes / f"{max(nums, default=0) + 1:03d}-{util.slug(nome)}"
    inicio = _inicio_da_missao(Path(pasta))
    destino.mkdir()
    (destino / "imagens").mkdir()
    (destino / "tempos.csv").write_text(f"etapa,inicio,segundos,status\nmissao,{inicio},0,inicio\n",
                                        encoding="utf-8", newline="\n")
    return destino


def _linhas_tempo(pasta_corte):
    arq = Path(pasta_corte) / "tempos.csv"
    return list(csv.DictReader(open(arq, encoding="utf-8"))) if arq.exists() else []


def tempo(pasta_corte, acao: str = "ver") -> dict:
    pasta = Path(pasta_corte)
    linhas = _linhas_tempo(pasta)
    if acao == "inicio" or not any(l["etapa"] == "missao" and l["status"] == "inicio" for l in linhas):
        with open(pasta / "tempos.csv", "a", encoding="utf-8", newline="\n") as f:
            if not linhas and not (pasta / "tempos.csv").exists():
                f.write("etapa,inicio,segundos,status\n")
            f.write(f"missao,{AGORA()},0,inicio\n")
        linhas = _linhas_tempo(pasta)
    ini = dt.datetime.fromisoformat(next(l["inicio"] for l in linhas if l["etapa"] == "missao" and l["status"] == "inicio"))
    total = (dt.datetime.now() - ini).total_seconds()
    fins = [l for l in linhas if l["etapa"] == "missao" and l["status"] == "fim"]
    if acao == "ver" and fins:  # missão encerrada: vale o total do `tempo fim`
        total = float(fins[-1]["segundos"])
    if acao == "fim":
        with open(pasta / "tempos.csv", "a", encoding="utf-8", newline="\n") as f:
            f.write(f"missao,{AGORA()},{total:.0f},fim\n")
    etapas = [l for l in linhas if l["etapa"] != "missao"]
    maquina = sum(float(l["segundos"]) for l in etapas)
    longas = sorted(etapas, key=lambda l: -float(l["segundos"]))[:3]
    fmt = lambda s: f"{int(s) // 60}min{int(s) % 60:02d}"  # noqa: E731
    return {"ok": True, "total_s": round(total), "total": fmt(total), "maquina_s": round(maquina, 1),
            "etapas_mais_longas": [f"{l['etapa']} {fmt(float(l['segundos']))}" for l in longas]}


# ---------- capa ----------
def _quebrar(frase: str):
    ws = frase.upper().split()
    if len(ws) <= 2:
        return [" ".join(ws)]
    melhor = min(range(1, len(ws)), key=lambda i: abs(len(" ".join(ws[:i])) - len(" ".join(ws[i:]))))
    return [" ".join(ws[:melhor]), " ".join(ws[melhor:])]


def capa(pasta_corte, frase: str, t: float | None = None) -> Path:
    from PIL import Image, ImageDraw, ImageEnhance, ImageFont

    from . import montagem
    pasta = Path(pasta_corte)
    canal = config.carregar_canal(config.pasta_trabalho(pasta))
    corte = util.ler_json(pasta / "corte.json", {})
    ed = corte.get("edicao") or {}
    cor = ed.get("cor") or canal["estilo"]["cor"]
    rostos = util.ler_json(pasta / "rostos.json", {}) if (pasta / "rostos.json").exists() else {}
    cobertos = [(im["s"], im["e"]) for im in ed.get("imagens", [])]
    if t is None:
        cand = [p for p in rostos.get("principal", []) if "cx" in p and not any(a <= p["t"] <= b for a, b in cobertos)]
        t = max(cand, key=lambda p: p["w"])["t"] if cand else 1.0
    quadro = pasta / "capa_quadro.png"
    util.rodar([util.ffmpeg(), "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(pasta / "base.mp4"), "-frames:v", "1", str(quadro)])
    img = Image.open(quadro).convert("RGB")
    bw, bh = img.size
    cx, cy = montagem.camera_em(rostos.get("camera", []), t) if rostos else (0.5, 0.4)
    k = max(1080 / bw, 1920 / bh) * 1.08
    img = img.resize((round(bw * k), round(bh * k)), Image.LANCZOS)
    vw, vh = img.size
    left = int(min(max(0, cx * vw - 540), vw - 1080))
    top = int(min(max(0, cy * vh - 760), vh - 1920))
    img = img.crop((left, top, left + 1080, top + 1920))
    img = ImageEnhance.Contrast(ImageEnhance.Color(img).enhance(1.1)).enhance(1.08)
    grad = Image.new("L", (1, 1920))
    for y in range(1920):
        grad.putpixel((0, y), int(max(0, (y - 1000) / 920) ** 1.4 * 235))
    preto = Image.new("RGB", (1080, 1920), (0, 0, 0))
    img = Image.composite(preto, img, grad.resize((1080, 1920)))
    d = ImageDraw.Draw(img)
    fonte = util.raiz_plugin() / "assets" / "fontes" / "Montserrat-Black.ttf"
    linhas = _quebrar(frase)
    tam = 120
    while tam > 60 and max(ImageFont.truetype(str(fonte), tam).getlength(l) for l in linhas) > 980:
        tam -= 4
    f = ImageFont.truetype(str(fonte), tam)
    y = 1520 - len(linhas) * (tam + 16)
    for i, l in enumerate(linhas):
        w = f.getlength(l)
        d.text(((1080 - w) / 2, y), l, font=f, fill=cor if i == len(linhas) - 1 else "white",
               stroke_width=max(6, tam // 11), stroke_fill="black")
        y += tam + 16
    saida = pasta / "capa.jpg"
    img.save(saida, quality=92)
    quadro.unlink(missing_ok=True)
    return saida


# ---------- POSTAGEM.txt ----------
def _credito_trilha(trab: Path, arquivo: str | None) -> str | None:
    lic = trab / "biblioteca" / "LICENCAS.md"
    if not arquivo or not lic.exists():
        return None
    for l in lic.read_text(encoding="utf-8").splitlines():
        if arquivo in l and "crédito:" in l.lower():
            return l.split("crédito:", 1)[1].strip(" |")
    return None


def _milhar(n) -> str:
    return f"{int(n):,}".replace(",", ".")


def postagem(pasta_corte) -> Path:
    pasta = Path(pasta_corte)
    corte = util.ler_json(pasta / "corte.json")
    p = corte.get("postagem")
    if not p or not p.get("titulo"):
        raise util.ErroUsuario("preencha \"postagem\" no corte.json: titulo, legenda_tiktok, descricao, hashtags")
    ed = corte.get("edicao") or {}
    origem = util.ler_json(pasta / "origem.json", {})
    modelo = corte.get("modelo") or {}
    dur = util.ler_json(pasta / "timeline.json", {}).get("duracao", 0)
    trab = config.pasta_trabalho(pasta)
    tags = " ".join(p.get("hashtags", []))
    link = origem.get("url", "")
    if link and origem.get("inicio_real") is not None:  # o minuto onde o corte começa, não o começo do bruto
        primeiro = (corte.get("trechos") or [[0, 0]])[0][0]
        link += ("&" if "?" in link else "?") + f"t={int(origem['inicio_real'] + primeiro)}s"
    # o vídeo baixado nem sempre é o episódio inteiro (pode ser um vídeo curto do canal do podcast)
    original = f"Vídeo original: {origem['titulo']} · {link}" if origem.get("titulo") else f"Vídeo original: {link}"
    desc = [p.get("descricao", "").strip()]
    if origem.get("titulo") or origem.get("canal"):
        desc.append(f"Corte do {origem.get('canal') or 'podcast'}")
    if link:
        desc.append(original)
    if ed.get("imagens"):
        desc.append("Imagens ilustrativas geradas por IA.")
    cred = _credito_trilha(trab, (ed.get("trilha") or {}).get("arquivo"))
    if cred:
        desc.append(f"Música: {cred}")
    desc.append(tags)
    mins = lambda s: f"{int(s) // 3600}:{int(s) % 3600 // 60:02d}:{int(s) % 60:02d}"  # noqa: E731
    trechos = []
    if origem.get("inicio_real") is not None:
        for a, b in corte.get("trechos", []):
            trechos.append(f"{mins(origem['inicio_real'] + a)}–{mins(origem['inicio_real'] + b)}")
    t = tempo(pasta, "ver") if (pasta / "tempos.csv").exists() else None
    txt = [f"CORTE {pasta.name.upper()}", "=" * 40, "",
           "TÍTULO (YouTube)", f"{p['titulo']} {tags}".strip(), "",
           "LEGENDA (TikTok)", f"{p.get('legenda_tiktok', p['titulo'])} {tags}".strip(), "",
           "DESCRIÇÃO", *[x for x in desc if x], "",
           f"DURAÇÃO: {int(dur) // 60}min{int(dur) % 60:02d} ({dur:.1f} s), vertical 1080x1920, 30 fps".replace(".", ",", 1), "",
           "ORIGEM"]
    if modelo.get("url"):
        txt.append(f"- Corte viral modelado: {modelo['url']}")
        txt.append(f"  \"{modelo.get('titulo', '')}\" · {modelo.get('canal', '')} · {_milhar(modelo.get('views', 0))} views")
    if link:
        txt.append(f"- {original}")
    if trechos:
        txt.append(f"  Trechos: {', '.join(trechos)} (pausas encurtadas)")
    if t:
        txt += ["", f"TEMPO DE PRODUÇÃO: {t['total']} (máquina {int(t['maquina_s']) // 60}min{int(t['maquina_s']) % 60:02d})"]
    txt += ["", "Crédito e autorização do podcast são responsabilidade de quem posta."]
    saida = pasta / "POSTAGEM.txt"
    saida.write_text("\n".join(txt) + "\n", encoding="utf-8", newline="\n")
    return saida


def registrar(sub):
    p = sub.add_parser("novo-corte", help="cria cortes/NNN-nome e liga o cronômetro")
    p.add_argument("nome")
    p.set_defaults(func=lambda a: {"ok": True, "pasta": str(novo_corte(".", a.nome))})
    p = sub.add_parser("tempo", help="cronômetro do corte: inicio | fim | ver")
    p.add_argument("acao", choices=["inicio", "fim", "ver"]); p.add_argument("--corte", required=True)
    p.set_defaults(func=lambda a: tempo(a.corte, a.acao))
    p = sub.add_parser("capa", help="capa 1080x1920: quadro do vídeo com o rosto + frase curta")
    p.add_argument("--corte", required=True); p.add_argument("--frase", required=True); p.add_argument("--t", type=float)
    p.set_defaults(func=lambda a: {"ok": True, "capa": str(capa(a.corte, a.frase, a.t))})
    p = sub.add_parser("postagem", help="gera o POSTAGEM.txt a partir do corte.json")
    p.add_argument("--corte", required=True)
    p.set_defaults(func=lambda a: {"ok": True, "postagem": str(postagem(a.corte))})
