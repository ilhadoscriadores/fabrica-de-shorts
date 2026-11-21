"""Transcrição com tempo por palavra (faster-whisper): medium na placa NVIDIA, small no processador."""
from __future__ import annotations

import re
from pathlib import Path

from . import ambiente, config, util


def transcrever(video, saida_json, modelo: str = "auto", idioma: str | None = None, prompt: str | None = None) -> list[dict]:
    dispositivo, tipo, padrao = ambiente.whisper_dispositivo()
    nome = padrao if modelo == "auto" else modelo
    if dispositivo == "cuda":
        ambiente.carregar_dlls_cuda()
    from faster_whisper import WhisperModel
    # o áudio vai decodificado pelo ffmpeg: o leitor do faster-whisper (PyAV) quebra com versões novas do PyAV
    som = util.ler_audio(video, sr=16000)

    def rodar(dev, ct, mod):
        m = WhisperModel(mod, device=dev, compute_type=ct)
        segs, _ = m.transcribe(som, language=idioma, word_timestamps=True, vad_filter=True,
                               condition_on_previous_text=False, initial_prompt=prompt)
        return [{"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3)}
                for s in segs for w in (s.words or []) if w.word.strip()]

    try:
        palavras = rodar(dispositivo, tipo, nome)
    except Exception as e:  # placa sem memória, DLL faltando: cai para o processador
        if dispositivo != "cuda":
            raise
        print(f"[aviso] a placa falhou ({type(e).__name__}); transcrevendo no processador", flush=True)
        palavras = rodar("cpu", "int8", "small" if modelo == "auto" else nome)
    saida_json = Path(saida_json)
    util.gravar_json(saida_json, palavras, indent=None)
    txt = saida_json.with_name("transcricao.txt") if saida_json.name == "palavras.json" else saida_json.with_suffix(".txt")
    txt.write_text("\n".join(f"[{t:.1f}] {x}" for t, x in linhas(palavras)) + "\n", encoding="utf-8", newline="\n")
    return palavras


def linhas(palavras: list[dict], pausa: float = 0.6, maximo: int = 14) -> list[tuple[float, str]]:
    """Agrupa as palavras em frases curtas (pontuação, pausa ou 14 palavras) para ler rápido."""
    out, atual = [], []
    for i, w in enumerate(palavras):
        if atual and (w["s"] - palavras[i - 1]["e"] > pausa or len(atual) >= maximo):
            out.append((atual[0]["s"], " ".join(x["w"] for x in atual)))
            atual = []
        atual.append(w)
        if re.search(r"[.?!…]$", w["w"]):
            out.append((atual[0]["s"], " ".join(x["w"] for x in atual)))
            atual = []
    if atual:
        out.append((atual[0]["s"], " ".join(x["w"] for x in atual)))
    return out


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
    ws = transcrever(video, saida, args.modelo, args.idioma or idioma)
    if not ws:
        raise util.ErroUsuario("a transcrição saiu vazia: o trecho tem fala? confira o bruto.mp4")
    txt = saida.with_name("transcricao.txt") if saida.name == "palavras.json" else saida.with_suffix(".txt")
    return {"ok": True, "palavras": len(ws), "duracao_fala": round(ws[-1]["e"] - ws[0]["s"], 1),
            "json": str(saida), "texto": str(txt), "modelo": args.modelo, "dispositivo": ambiente.whisper_dispositivo()[0]}


def registrar(sub):
    p = sub.add_parser("transcrever", help="transcreve com tempo por palavra (--corte usa o bruto.mp4)")
    p.add_argument("video", nargs="?"); p.add_argument("--corte"); p.add_argument("--saida")
    p.add_argument("--modelo", default="auto"); p.add_argument("--idioma")
    p.set_defaults(func=_cmd)
