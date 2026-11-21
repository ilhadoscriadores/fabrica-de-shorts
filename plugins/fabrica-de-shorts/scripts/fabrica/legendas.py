"""Legendas em blocos curtos, presas no começo REAL da voz (o Whisper erra até 0,5 s), e a conferência.

Porta do sistema de legendas do canal de GTA 6 (legendas_v8.py e checar_legendas.py), adaptado para podcast."""
from __future__ import annotations

import re
from functools import lru_cache

import numpy as np

from . import util

FPS = 30
MAX_PALAVRAS, MAX_CHARS = 3, 16
TAM_MAX, TAM_MIN = 92, 44
FUNCIONAIS = {
    "O", "A", "OS", "AS", "UM", "UMA", "DE", "DO", "DA", "DOS", "DAS", "EM", "NO", "NA", "NOS", "NAS", "NUM", "NUMA",
    "PRA", "PRO", "PARA", "POR", "PELO", "PELA", "COM", "E", "OU", "SE", "MAS", "QUE", "MEU", "MINHA", "SEU", "SUA",
    "THE", "AN", "OF", "TO", "IN", "ON", "AT", "FOR", "WITH", "AND", "OR", "BUT", "MY", "YOUR",
    "EL", "LA", "LOS", "LAS", "UNA", "DEL", "CON", "Y", "MI", "TU"}
PONTUACAO_FIM = re.compile(r"[.,?!;:…]$")


def limpa(w: str) -> str:
    w = re.sub(r"^[\"'“”«(\[]+", "", w.strip())
    w = re.sub(r"[\"'“”»)\].,?!;:…]+$", "", w)
    return w.upper()


@lru_cache(maxsize=4)
def _fonte(tam: int):
    from PIL import ImageFont
    return ImageFont.truetype(str(util.raiz_plugin() / "assets" / "fontes" / "Montserrat-Black.ttf"), tam)


def _largura(palavras, tam: int) -> float:
    tot = 0.0
    for p in palavras:
        t = round(tam * (1.12 if (p["destaque"] or p["censura"]) else 1))
        tot += _fonte(t).getlength(p["w"]) + 14
    return tot + 0.54 * tam * (len(palavras) - 1)


def _tamanho(palavras, largura_max: int) -> int:
    for tam in range(TAM_MAX, TAM_MIN - 1, -2):
        if _largura(palavras, tam) <= largura_max:
            return tam
    return TAM_MIN


def _oracoes(ws):
    out, cur = [], []
    for i, w in enumerate(ws):
        if cur and (w["s"] - ws[i - 1]["e"] > 0.3 or PONTUACAO_FIM.search(ws[i - 1]["w"].strip())):
            out.append(cur)
            cur = []
        cur.append(w)
    if cur:
        out.append(cur)
    return out


def _dividir(o):
    n = len(o)
    txt = [limpa(w["w"]) for w in o]
    best = [(0.0, [])] + [(float("inf"), None)] * n
    for i in range(1, n + 1):
        for j in range(max(0, i - MAX_PALAVRAS), i):
            if best[j][1] is None:
                continue
            if i - j > 1 and len(" ".join(txt[j:i])) > MAX_CHARS:
                continue
            c = 100.0
            if i < n and txt[i - 1] in FUNCIONAIS:
                c += 120  # pior que um bloco a mais
            if i - j == 1 and n > 1:
                c += 45
            if best[j][0] + c < best[i][0]:
                best[i] = (best[j][0] + c, best[j][1] + [(j, i)])
    return [o[j:i] for j, i in best[n][1]]


def _fechar(bs, fps=FPS, duracao=None):
    """Quadros de cada bloco: fica até o próximo entrar (vão < 1,2 s); senão some 0,45 s depois da fala."""
    for i, b in enumerate(bs):
        b["f0"] = round(b["s"] * fps)
        b["palavras"][0]["f0"] = b["f0"]
        prox = bs[i + 1]["s"] if i + 1 < len(bs) else None
        if prox is not None and prox - b["e"] < 1.2:
            fim = prox
        elif prox is not None:
            fim = min(prox, b["e"] + 0.45)
        else:
            fim = b["e"] + 0.8 if duracao is None else min(duracao, b["e"] + 0.8)
        b["f1"] = max(b["f0"] + 1, round(fim * fps))
        for k, p in enumerate(b["palavras"]):
            p["f1"] = max(p["f0"] + 1, p["f1"])
    return bs


def blocos(palavras, fps: int = FPS, largura_max: int = 960, destaques=(), duracao=None) -> list[dict]:
    dest = {util.normalizar(d) for d in destaques}
    bs = []
    for o in _oracoes([w for w in palavras if limpa(w["w"])]):
        for parte in _dividir(o):
            ps = [{"w": limpa(w["w"]), "f0": round(w["s"] * fps), "f1": round(w["e"] * fps),
                   "destaque": util.normalizar(w["w"]) in dest and not w.get("censura"),
                   "censura": bool(w.get("censura")), "s": w["s"], "e": w["e"]} for w in parte]
            bs.append({"s": parte[0]["s"], "e": parte[-1]["e"], "palavras": ps,
                       "tam": _tamanho(ps, largura_max)})
    return _fechar(bs, fps, duracao)


# ---------- voz ----------
def limiar(env: np.ndarray) -> tuple[float, float]:
    """Nível de 'voz ligada' que se adapta ao ruído de fundo do podcast."""
    piso, alto = np.percentile(env, 10), np.percentile(env, 90)
    on = max(piso + 12, alto - 25)
    return float(on), float(on - 2)


def inicios_de_voz(env, on, off, silencio=4):
    out, run = [], 0
    for k, v in enumerate(env):
        if v < off:
            run += 1
        else:
            if v >= on and run >= silencio:
                out.append(k / 100)
            if v >= on:
                run = 0
    return np.array(out)


def ancorar(bs, voz_wav, fps: int = FPS, duracao=None, env=None):
    env = util.envelope_db(voz_wav) if env is None else env
    on, off = limiar(env)
    ons = inicios_de_voz(env, on, off)
    ant = -1.0
    for b in bs:
        a = b["s"]
        teto = min(a + 0.35, b["e"] - 0.05)
        ok = ons[(ons > a - 0.45) & (ons <= teto + 1e-9) & (ons > ant + 0.10)]
        if len(ok):
            novo = float(ok[np.argmin(np.abs(ok - a))])
            d = novo - a
            if d > 0:  # o Whisper adiantou a frase: as palavras do bloco andam junto
                for p in b["palavras"]:
                    p["s"] = min(p["s"] + d, b["e"] + d - 0.06)
                    p["e"] = p["e"] + d
                    p["f0"], p["f1"] = round(p["s"] * fps), round(p["e"] * fps)
                b["e"] += d
            b["s"] = novo
            b["palavras"][0]["s"] = novo
        ant = b["s"]
    return _fechar(bs, fps, duracao)


def conferir(bs, voz_wav, fps: int = FPS, env=None) -> list[dict]:
    """Começo de cada bloco contra a voz limpa: > 80 ms antes ou depois = problema."""
    env = util.envelope_db(voz_wav) if env is None else env
    on, off = limiar(env)
    inicios = [b["f0"] / fps for b in bs]
    probs = []
    for b, t in zip(bs, inicios):
        if b["palavras"][0]["censura"]:
            continue  # palavrão está mudo de propósito
        k = int(round(t * 100))
        texto = " ".join(p["w"] for p in b["palavras"])
        primeiro = next((j for j in range(30) if k + j < len(env) and env[k + j] > on), None)
        if primeiro is None:
            probs.append({"t": round(t, 2), "texto": texto, "problema": "sem voz nos 300 ms seguintes"})
            continue
        if primeiro > 8:
            probs.append({"t": round(t, 2), "texto": texto, "problema": f"legenda {primeiro * 10} ms ANTES da voz"})
            continue
        q = next((k - j for j in range(1, 40) if k - j >= 0 and env[k - j] < off), None)
        pausa = q is not None and all(env[max(0, q - r)] < off for r in range(5))
        if pausa and k - q - 1 > 8:
            pe = (q + 1) / 100
            if not any(pe - 0.05 <= t2 < t - 0.01 for t2 in inicios):
                probs.append({"t": round(t, 2), "texto": texto, "problema": f"legenda {(k - q - 1) * 10} ms DEPOIS da voz"})
    return probs
