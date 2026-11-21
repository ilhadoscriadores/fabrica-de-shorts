"""Transcrição com tempo por palavra (faster-whisper): medium na placa NVIDIA, small no processador."""
from __future__ import annotations

import re
from pathlib import Path

from . import ambiente, config, util


CERTEZA_MIN = 0.5    # abaixo disso a detecção de idioma é chute: usa o idioma do canal
DENSIDADE_MIN = 0.5  # menos que isso de palavras por segundo = o VAD provavelmente comeu a fala (jogo/música por baixo)


def arquivo_idioma(saida_json) -> Path:
    """Onde fica o idioma da fala do corte: CORTE/idioma.txt (ao lado do palavras.json)."""
    return Path(saida_json).with_name("idioma.txt")


def idioma_do_corte(pasta) -> str | None:
    """Idioma detectado na fala do corte (gravado pelo transcrever), ou None."""
    arq = Path(pasta) / "idioma.txt"
    return arq.read_text(encoding="utf-8").strip() or None if arq.exists() else None


def transcrever(video, saida_json, modelo: str = "auto", idioma: str | None = None, prompt: str | None = None,
                idioma_padrao: str | None = None) -> list[dict]:
    """Tempo por palavra. `idioma` força o idioma; sem ele, detecta pela fala (nunca traduz para o idioma do canal).
    `idioma_padrao` (o do canal) só entra quando a detecção não tem certeza."""
    dispositivo, tipo, padrao = ambiente.whisper_dispositivo()
    nome = padrao if modelo == "auto" else modelo
    if dispositivo == "cuda":
        ambiente.carregar_dlls_cuda()
    from faster_whisper import WhisperModel
    # o áudio vai decodificado pelo ffmpeg: o leitor do faster-whisper (PyAV) quebra com versões novas do PyAV
    som = util.ler_audio(video, sr=16000)
    duracao = len(som) / 16000
    modelos = {}

    def rodar(dev, ct, mod, lang, vad=True):
        if (dev, ct, mod) not in modelos:
            modelos[(dev, ct, mod)] = WhisperModel(mod, device=dev, compute_type=ct)
        segs, info = modelos[(dev, ct, mod)].transcribe(
            som, language=lang, word_timestamps=True, vad_filter=vad,
            condition_on_previous_text=False, initial_prompt=prompt)
        ws = [{"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3)}
              for s in segs for w in (s.words or []) if w.word.strip()]
        return ws, info

    def completo(dev, ct, mod):
        ws, info = rodar(dev, ct, mod, idioma)
        lang = idioma or getattr(info, "language", None)
        if not idioma and idioma_padrao and info is not None and getattr(info, "language_probability", 1) < CERTEZA_MIN:
            lang = idioma_padrao
            ws, _ = rodar(dev, ct, mod, lang)
        if duracao > 5 and len(ws) < DENSIDADE_MIN * duracao:  # fala por baixo de jogo/música: tenta sem o VAD
            sem_vad, _ = rodar(dev, ct, mod, lang, vad=False)
            if len(sem_vad) > 2 * len(ws):
                print(f"[aviso] quase nada com o filtro de voz ({len(ws)} palavras); usei sem o filtro ({len(sem_vad)})", flush=True)
                ws = sem_vad
        return ws, lang

    try:
        palavras, lang = completo(dispositivo, tipo, nome)
    except Exception as e:  # placa sem memória, DLL faltando: cai para o processador
        if dispositivo != "cuda":
            raise
        print(f"[aviso] a placa falhou ({type(e).__name__}); transcrevendo no processador", flush=True)
        palavras, lang = completo("cpu", "int8", "small" if modelo == "auto" else nome)
    saida_json = Path(saida_json)
    util.gravar_json(saida_json, palavras, indent=None)
    if lang and saida_json.name == "palavras.json":  # só o corte guarda (a censura usa); revisão e achar não sujam a pasta
        arquivo_idioma(saida_json).write_text(str(lang) + "\n", encoding="utf-8", newline="\n")
    txt = saida_json.with_name("transcricao.txt") if saida_json.name == "palavras.json" else saida_json.with_suffix(".txt")
    txt.write_text("\n".join(linhas_txt(palavras)) + "\n", encoding="utf-8", newline="\n")
    return palavras


def frases(palavras: list[dict], pausa: float = 0.6, maximo: int = 14) -> list[tuple[float, float, str]]:
    """Agrupa as palavras em frases curtas (pontuação, pausa ou 14 palavras): (início, fim, texto)."""
    out, atual = [], []

    def fecha():
        out.append((atual[0]["s"], atual[-1]["e"], " ".join(x["w"] for x in atual)))
        atual.clear()
    for i, w in enumerate(palavras):
        if atual and (w["s"] - palavras[i - 1]["e"] > pausa or len(atual) >= maximo):
            fecha()
        atual.append(w)
        if re.search(r"[.?!…]$", w["w"]):
            fecha()
    if atual:
        fecha()
    return out


def linhas(palavras: list[dict], pausa: float = 0.6, maximo: int = 14) -> list[tuple[float, str]]:
    """Frases como (início, texto)."""
    return [(s, x) for s, _, x in frases(palavras, pausa, maximo)]


def linhas_txt(palavras: list[dict]) -> list[str]:
    """'[início–fim] texto' para ler rápido e cortar no fim certo da frase (transcricao.txt e timeline.txt)."""
    return [f"[{s:.1f}–{e:.1f}] {x}" for s, e, x in frases(palavras)]


def _cmd(args):
    idioma = None
    try:
        idioma = config.carregar_canal(".")["idioma"]
    except util.ErroUsuario:
        pass
    if args.corte:
        pasta = Path(args.corte)
        video, saida = pasta / "bruto.mp4", pasta / "palavras.json"
    else:
        video, saida = Path(args.video), Path(args.saida or Path(args.video).with_suffix(".words.json"))
    if not video.exists():
        raise util.ErroUsuario(f"não achei {video}")
    ws = transcrever(video, saida, args.modelo, args.idioma, idioma_padrao=idioma)
    if not ws:
        raise util.ErroUsuario("a transcrição saiu vazia: o trecho tem fala? confira o bruto.mp4")
    txt = saida.with_name("transcricao.txt") if saida.name == "palavras.json" else saida.with_suffix(".txt")
    return {"ok": True, "palavras": len(ws), "duracao_fala": round(ws[-1]["e"] - ws[0]["s"], 1),
            "json": str(saida), "texto": str(txt), "modelo": args.modelo, "dispositivo": ambiente.whisper_dispositivo()[0],
            "idioma_da_fala": idioma_do_corte(saida.parent) if saida.name == "palavras.json" else None}


def registrar(sub):
    p = sub.add_parser("transcrever", help="transcreve com tempo por palavra (--corte usa o bruto.mp4)")
    p.add_argument("video", nargs="?"); p.add_argument("--corte"); p.add_argument("--saida")
    p.add_argument("--modelo", default="auto"); p.add_argument("--idioma", help="força o idioma (padrão: detecta pela fala)")
    p.set_defaults(func=_cmd)
