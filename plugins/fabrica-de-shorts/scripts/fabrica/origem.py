"""Achar a origem do corte: legenda do YouTube, busca do episódio, localizar o trecho e baixar só ele."""
from __future__ import annotations

import html
import re
import shutil
import time
from collections import defaultdict
from pathlib import Path

from . import util

_YDL = None  # trocado nos testes
ESPERAS_LEGENDA = (5, 15)  # novas tentativas quando a legenda vem sem fala


def _aviso_sem_legenda(url: str, vazia: bool) -> str:
    """Só cita comando que existe: o --transcrever é do `legenda`, não do `achar`."""
    motivo = "legenda vazia: o YouTube recusou; tente de novo em 1 minuto ou" if vazia else "o vídeo não tem legenda;"
    return f"{motivo} rode `FAB legenda {url} --transcrever` (demora)"


def _erro_achar_sem_legenda(url: str, modelo_url: str) -> str:
    return (f"sem legenda: tente o vídeo do próprio canal do podcast ou `FAB legenda {url} --transcrever` (demora) "
            f"e depois `FAB achar {modelo_url} --candidatos {url}`")


def _esperar(segundos: float):  # trocado nos testes
    time.sleep(segundos)


class _ComRecuo:
    """Abre o YoutubeDL com os clientes mweb/web_embedded (passam pelo "confirme que não é robô")
    e, se o YouTube recusar, tenta de novo com os clientes padrão do yt-dlp."""

    def __init__(self, cls, opts):
        self.cls, self.opts = cls, opts

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def extract_info(self, url, download=True):
        try:
            with self.cls(self.opts) as y:
                return y.extract_info(url, download=download)
        except Exception as e:
            msg = str(e).lower()
            if not any(x in msg for x in ("not a bot", "não é um bot", "format is not available", "reloaded", "po token")):
                raise
            o = dict(self.opts)
            o["extractor_args"] = {"youtube": {k: v for k, v in o["extractor_args"]["youtube"].items() if k != "player_client"}}
            with self.cls(o) as y:
                return y.extract_info(url, download=download)


def _ydl(opts):
    cls = _YDL
    if cls is None:
        import yt_dlp
        return _ComRecuo(yt_dlp.YoutubeDL, opts)
    return cls(opts)


CLIENTES = ["mweb", "web_embedded"]


def opcoes_ydl(idioma: str = "pt", **extra) -> dict:
    """Opções comuns: título no idioma do canal, Node como motor de JS, sem barulho no terminal."""
    lang = {"pt": "pt-BR", "en": "en-US", "es": "es-ES"}.get(idioma, idioma)
    o = {"quiet": True, "no_warnings": True, "noprogress": True,
         "http_headers": {"Accept-Language": f"{lang},{idioma};q=0.9"},
         "extractor_args": {"youtube": {"lang": [idioma], "player_client": list(CLIENTES)}}}
    if shutil.which("node"):
        o["js_runtimes"] = {"node": {}}
    try:
        o["ffmpeg_location"] = str(Path(util.ffmpeg()).parent)
    except util.ErroUsuario:
        pass
    o.update(extra)
    return o


def segundos(v) -> float:
    """'3:20:36', '20:36', '75.5' ou número → segundos."""
    if isinstance(v, (int, float)):
        return v
    v = str(v).strip().replace(",", ".")
    if ":" not in v:
        x = float(v)
        return int(x) if x.is_integer() else x
    total = 0.0
    for parte in v.split(":"):
        total = total * 60 + float(parte)
    return int(total) if total.is_integer() else total


def hms(s: float) -> str:
    s = int(round(s))
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


# ---------- legenda (VTT do YouTube) ----------
def _ts(x: str) -> float:
    h, m, s = x.split(":") if x.count(":") == 2 else ("0", *x.split(":"))
    return int(h) * 3600 + int(m) * 60 + float(s)


def vtt_para_linhas(texto: str) -> list[tuple[float, str]]:
    """Linhas (tempo, texto) sem as repetições da legenda automática do YouTube."""
    out, anterior, t = [], "", 0.0
    for linha in texto.splitlines():
        if "-->" in linha:
            t = round(_ts(linha.split("-->")[0].strip()), 3)
            continue
        if linha.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")) or not linha.strip():
            continue
        limpo = html.unescape(re.sub(r"<[^>]+>", "", linha)).replace("\xa0", " ")
        limpo = re.sub(r"\s+", " ", limpo).strip()
        if limpo and limpo != anterior:
            out.append((t, limpo))
            anterior = limpo
    return out


def gravar_txt(linhas, caminho):
    def f(s):
        s = int(s)
        return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"
    Path(caminho).write_text("\n".join(f"{f(t)} {x}" for t, x in linhas) + "\n", encoding="utf-8", newline="\n")


def ler_linhas(caminho) -> list[tuple[float, str]]:
    """Lê .vtt ou .txt ('hh:mm:ss texto')."""
    texto = Path(caminho).read_text(encoding="utf-8", errors="replace")
    if Path(caminho).suffix.lower() == ".vtt" or texto.startswith("WEBVTT"):
        return vtt_para_linhas(texto)
    out = []
    for l in texto.splitlines():
        m = re.match(r"^\[?(\d{1,2}:\d{2}(?::\d{2})?(?:\.\d+)?)\]?\s+(.*)$", l.strip())
        if m:
            out.append((float(segundos(m.group(1))), m.group(2)))
        elif re.match(r"^\[?\d+(\.\d+)?\]?\s", l.strip()):
            n, resto = l.strip().split(None, 1)
            out.append((float(n.strip("[]")), resto))
        elif l.strip():
            out.append((out[-1][0] if out else 0.0, l.strip()))
    return out


_LINK = re.compile(r"(?:youtube\.com/(?:watch\?(?:\S*?&)?v=|live/)|youtu\.be/)([A-Za-z0-9_-]{11})(?![A-Za-z0-9_-])"
                   r"|(?:completo|original)\s*:\s*([A-Za-z0-9_-]{11})(?![A-Za-z0-9_-])", re.I)
_PALAVRA = re.compile(r"[A-Za-z][a-z]{10}|[A-Z]{11}")  # "original: Inteligente" não é id


def links_da_descricao(texto, ignorar: str | None = None) -> list[str]:
    """Links e ids do YouTube na descrição ("vídeo completo: ..."), na ordem, sem repetir e sem o próprio vídeo."""
    out = []
    for m in _LINK.finditer(texto or ""):
        vid = m.group(1) or m.group(2)
        if m.group(2) and _PALAVRA.fullmatch(vid):
            continue
        url = f"https://www.youtube.com/watch?v={vid}"
        if vid != ignorar and url not in out:
            out.append(url)
    return out


def escolher_legenda(info: dict, idioma: str):
    """Uma legenda só (baixar várias dá 429): manual no idioma, automática original, automática no idioma."""
    manuais = info.get("subtitles") or {}
    autos = info.get("automatic_captions") or {}

    def vtt(lista):
        return next((f.get("url") for f in lista or [] if f.get("ext") == "vtt" and f.get("url")), None)

    ordem = [(manuais, idioma), (manuais, f"{idioma}-BR"), (autos, f"{idioma}-orig"), (autos, idioma)]
    ordem += [(manuais, k) for k in manuais if k.startswith(idioma)]
    ordem += [(autos, k) for k in autos if k.endswith("-orig")]
    for fonte, chave in ordem:
        u = vtt(fonte.get(chave))
        if u:
            return chave, u
    return None


def _tem_fala(corpo: bytes) -> bool:
    return bool(vtt_para_linhas(corpo.decode("utf-8", errors="replace")))


def _baixar_texto(url: str, esperas=(3, 6, 12), valido=None) -> bytes:
    """HTTP 429 e corpo vazio (o YouTube às vezes devolve 200 sem nada) são recusas: espera e tenta de novo.
    Se continuar vazio, devolve b"" e quem chamou decide."""
    import urllib.error
    import urllib.request
    valido = valido or (lambda b: bool(b.strip()))
    for i in range(len(esperas) + 1):
        if i:
            _esperar(esperas[i - 1])
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                corpo = r.read()
        except urllib.error.HTTPError as e:
            if e.code != 429 or i == len(esperas):
                raise util.ErroComando(f"o YouTube recusou a legenda (HTTP {e.code}). Espere 1 minuto e tente de novo.")
            continue
        if valido(corpo):
            return corpo
    return b""


def _vtts_com_fala(pasta: Path, vid: str) -> list[Path]:
    """Legendas já baixadas; uma sem nenhuma fala conta como inexistente e é apagada."""
    bons = []
    for p in sorted(pasta.glob(f"{vid}*.vtt")):
        if vtt_para_linhas(p.read_text(encoding="utf-8", errors="replace")):
            bons.append(p)
        else:
            p.unlink(missing_ok=True)
    return bons


def legenda(url: str, pasta, idioma: str = "pt", transcrever_se_faltar: bool = False) -> dict:
    """Baixa a legenda (manual ou automática) e grava <id>.txt. Devolve título, canal e o começo da descrição."""
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    with _ydl(opcoes_ydl(idioma, skip_download=True)) as y:
        info = y.extract_info(url, download=False)
    vid = info.get("id", "video")
    vtts = _vtts_com_fala(pasta, vid)
    transcrito = util.ler_json(pasta / f"{vid}.words.json", [])  # de um `legenda --transcrever` anterior
    vazia = False
    if not vtts and not transcrito:
        escolha = escolher_legenda(info, idioma)
        if escolha:
            chave, sub_url = escolha
            corpo = _baixar_texto(sub_url, esperas=ESPERAS_LEGENDA, valido=_tem_fala)
            if corpo:
                destino = pasta / f"{vid}.{chave}.vtt"
                destino.write_bytes(corpo)
                vtts = [destino]
            else:
                vazia = True
    dados = {"id": vid, "titulo": info.get("title"), "canal": info.get("channel") or info.get("uploader"),
             "duracao": info.get("duration"), "views": info.get("view_count"), "data": info.get("upload_date"),
             "descricao": (info.get("description") or "")[:600]}
    links = links_da_descricao(info.get("description"), ignorar=vid)
    if links:
        dados["links_na_descricao"] = links
    txt = pasta / f"{vid}.txt"
    if vtts:
        gravar_txt(vtt_para_linhas(vtts[0].read_text(encoding="utf-8", errors="replace")), txt)
        dados.update(vtt=str(vtts[0]), txt=str(txt))
    elif transcrito:
        from . import transcricao
        gravar_txt(transcricao.linhas(transcrito), txt)
        dados.update(txt=str(txt), transcrito=True)
    elif transcrever_se_faltar:
        from . import transcricao
        audio = pasta / f"{vid}.m4a"
        with _ydl(opcoes_ydl(idioma, format="bestaudio[ext=m4a]/bestaudio",
                             outtmpl={"default": str(pasta / "%(id)s.%(ext)s")})) as y:
            y.extract_info(url, download=True)
        achados = sorted(pasta.glob(f"{vid}.*"), key=lambda p: p.stat().st_mtime)
        audio = next((p for p in reversed(achados) if p.suffix not in (".txt", ".json", ".vtt")), audio)
        palavras = transcricao.transcrever(audio, pasta / f"{vid}.words.json", modelo="small", idioma=idioma)
        gravar_txt(transcricao.linhas(palavras), txt)
        dados.update(txt=str(txt), transcrito=True)
    else:
        dados.update(txt=None, aviso=_aviso_sem_legenda(url, vazia))
    return dados


# ---------- localizar o trecho no episódio ----------
def _palavras_com_tempo(linhas):
    out = []
    for i, (t, texto) in enumerate(linhas):
        ws = [util.normalizar(w) for w in texto.split()]
        ws = [w for w in ws if w]
        t2 = linhas[i + 1][0] if i + 1 < len(linhas) else t + 2.5
        passo = max(t2 - t, 0.3) / max(len(ws), 1)
        out += [(t + k * passo, w) for k, w in enumerate(ws)]
    return out


def localizar(ref_palavras: list[str], ep_linhas, folga: float = 2.0, max_vao: float = 25.0) -> list[dict]:
    """Acha onde o texto do corte aparece no episódio (pode ser mais de um trecho). Melhores primeiro."""
    ep = _palavras_com_tempo(ep_linhas)
    indice = defaultdict(list)
    for i in range(len(ep) - 2):
        indice[(ep[i][1], ep[i + 1][1], ep[i + 2][1])].append(ep[i][0])
    ref = [w for w in (util.normalizar(x) for x in ref_palavras) if w]
    votos = []
    for i in range(len(ref) - 2):
        tempos = indice.get((ref[i], ref[i + 1], ref[i + 2]), [])
        if 0 < len(tempos) <= 20:
            votos += tempos
    if not votos:
        return []
    votos.sort()
    grupos, atual = [], [votos[0]]
    for v in votos[1:]:
        if v - atual[-1] <= max_vao:
            atual.append(v)
        else:
            grupos.append(atual)
            atual = [v]
    grupos.append(atual)
    total = max(len(ref) - 2, 1)
    out = [{"inicio": round(max(0, g[0] - folga), 1), "fim": round(g[-1] + folga + 3, 1), "acertos": len(g),
            "cobertura": round(len(g) / total, 2), "inicio_hms": hms(max(0, g[0] - folga)), "fim_hms": hms(g[-1] + folga + 3)}
           for g in grupos if len(g) >= 3]
    return sorted(out, key=lambda r: -r["acertos"])[:3]


def buscar(termo: str, limite: int = 10, longos: bool = False, idioma: str = "pt") -> list[dict]:
    with _ydl(opcoes_ydl(idioma, extract_flat=True, skip_download=True)) as y:
        info = y.extract_info(f"ytsearch{limite * (3 if longos else 1)}:{termo}", download=False)
    out = []
    for e in info.get("entries") or []:
        d = e.get("duration") or 0
        if longos and d and d < 20 * 60:
            continue
        out.append({"titulo": e.get("title"), "canal": e.get("channel") or e.get("uploader"),
                    "duracao": hms(d) if d else "?", "views": e.get("view_count"),
                    "url": f"https://www.youtube.com/watch?v={e.get('id')}"})
    return out[:limite]


def achar(modelo_url: str, pasta, idioma: str = "pt", busca: str | None = None, candidatos=None) -> dict:
    """Legenda do corte modelo → busca (ou candidatos) → legenda de cada episódio → onde o trecho está."""
    pasta = Path(pasta)
    ref = legenda(modelo_url, pasta, idioma, transcrever_se_faltar=True)
    if not ref.get("txt"):
        raise util.ErroUsuario("não consegui o texto do corte modelo")
    ref_palavras = " ".join(x for _, x in ler_linhas(ref["txt"])).split()
    lista = list(candidatos or [])
    if not lista:  # o "vídeo completo: <link>" da descrição do Short vem antes da busca
        lista = list(ref.get("links_na_descricao") or [])
        if busca:
            lista += [u for u in (c["url"] for c in buscar(busca, limite=4, longos=True, idioma=idioma)) if u not in lista]
    resultados = []
    for url in lista[:5]:
        try:
            ep = legenda(url, pasta, idioma)
        except util.ErroComando as e:
            resultados.append({"url": url, "erro": str(e)[:200]})
            continue
        except Exception as e:  # vídeo privado, removido etc.
            resultados.append({"url": url, "erro": f"{type(e).__name__}: {str(e)[:200]}"})
            continue
        dados = {"url": url, "titulo": ep.get("titulo"), "canal": ep.get("canal"), "duracao": ep.get("duracao")}
        texto = ep.get("vtt") or ep.get("txt")  # txt sem vtt = transcrição de um `legenda --transcrever`
        if not texto:  # sem legenda: diz o que fazer, em vez de "regioes: []" mudo
            resultados.append({**dados, "erro": _erro_achar_sem_legenda(url, modelo_url)})
            continue
        resultados.append({**dados, "regioes": localizar(ref_palavras, ler_linhas(texto))})
    resultados.sort(key=lambda r: -(r.get("regioes") or [{"acertos": 0}])[0]["acertos"])
    return {"modelo": {k: ref.get(k) for k in ("titulo", "canal", "views", "data", "descricao", "links_na_descricao", "txt")},
            "episodios": resultados}


# ---------- baixar só o trecho ----------
def baixar(url: str, inicio, fim, pasta_corte, margem: float = 4) -> dict:
    pasta = Path(pasta_corte)
    pasta.mkdir(parents=True, exist_ok=True)
    bruto = pasta / "bruto.mp4"
    if bruto.exists():  # nunca baixa por cima de um bruto
        return {"ok": True, "bruto": str(bruto), "ja_existia": True, "duracao": util.sondar(bruto)["duracao"]}
    ini = max(0, segundos(inicio) - margem)
    fi = segundos(fim) + margem

    def faixa(info, ydl):
        yield {"start_time": ini, "end_time": fi}

    opts = opcoes_ydl("pt", format="bv*[height<=1080][vcodec^=avc1]+ba[ext=m4a]/bv*[height<=1080]+ba/b[height<=1080]/b",
                      merge_output_format="mp4", download_ranges=faixa,
                      outtmpl={"default": str(pasta / "bruto.%(ext)s")})
    antes = set(pasta.glob("bruto*"))

    def limpar_restos():
        for p in set(pasta.glob("bruto*")) - antes | {p for p in antes if p.suffix in (".part", ".ytdl")}:
            p.unlink(missing_ok=True)

    for tentativa in (1, 2):  # o ffmpeg do yt-dlp às vezes sai com erro no meio do trecho
        try:
            with _ydl(opts) as y:
                info = y.extract_info(url, download=True)
            break
        except Exception as e:
            limpar_restos()
            if tentativa == 2:
                linhas = [x for x in re.sub(r"\x1b\[[0-9;]*m", "", str(e)).replace("ERROR:", "").splitlines() if x.strip()]
                motivo = (linhas[-1].strip() if linhas else type(e).__name__)[:160]
                raise util.ErroComando(f"não consegui baixar o trecho (2 tentativas): {motivo}. "
                                       "Espere 1 minuto e rode o baixar de novo.") from None
    if not bruto.exists():
        achados = sorted(pasta.glob("bruto*.mp4"), key=lambda p: p.stat().st_mtime)
        if not achados:
            raise util.ErroUsuario("o download terminou mas não achei o bruto.mp4")
        achados[-1].rename(bruto)
    dur = util.sondar(bruto)["duracao"]
    util.gravar_json(pasta / "origem.json", {
        "url": url, "inicio_pedido": segundos(inicio), "fim_pedido": segundos(fim), "margem": margem,
        "inicio_real": ini, "fim_real": fi, "titulo": info.get("title"), "canal": info.get("channel") or info.get("uploader"),
        "duracao_episodio": info.get("duration"), "duracao_bruto": dur})
    return {"ok": True, "bruto": str(bruto), "duracao": dur, "inicio_no_episodio": hms(ini)}


# ---------- comandos ----------
def _idioma():
    try:
        from . import config
        return config.carregar_canal(".")["idioma"]
    except util.ErroUsuario:
        return "pt"


def registrar(sub):
    p = sub.add_parser("buscar", help="busca vídeos no YouTube (use --longos para episódios)")
    p.add_argument("termo"); p.add_argument("--limite", type=int, default=8); p.add_argument("--longos", action="store_true")
    p.set_defaults(func=lambda a: {"ok": True, "resultados": buscar(a.termo, a.limite, a.longos, _idioma())})

    p = sub.add_parser("legenda", help="baixa a legenda de um vídeo e grava <id>.txt")
    p.add_argument("url"); p.add_argument("--pasta", default="mineracao"); p.add_argument("--transcrever", action="store_true")
    p.set_defaults(func=lambda a: {"ok": True, **legenda(a.url, a.pasta, _idioma(), a.transcrever)})

    p = sub.add_parser("localizar", help="acha onde o texto do corte está no episódio")
    p.add_argument("--ref", required=True, help="txt/vtt do corte modelo")
    p.add_argument("--episodio", required=True, help="vtt/txt do episódio")
    p.set_defaults(func=lambda a: {"ok": True, "regioes": localizar(
        " ".join(x for _, x in ler_linhas(a.ref)).split(), ler_linhas(a.episodio))})

    p = sub.add_parser("achar", help="corte modelo → episódio original e minuto (legenda + busca + localizar)")
    p.add_argument("modelo"); p.add_argument("--busca"); p.add_argument("--candidatos", nargs="*")
    p.add_argument("--pasta", default="mineracao")
    p.set_defaults(func=lambda a: {"ok": True, **achar(a.modelo, a.pasta, _idioma(), a.busca, a.candidatos)})

    p = sub.add_parser("baixar", help="baixa só o trecho do episódio (com margem) para cortes/NNN/bruto.mp4")
    p.add_argument("url"); p.add_argument("inicio"); p.add_argument("fim")
    p.add_argument("--corte", required=True); p.add_argument("--margem", type=float, default=4)
    p.set_defaults(func=lambda a: baixar(a.url, a.inicio, a.fim, a.corte, a.margem))
