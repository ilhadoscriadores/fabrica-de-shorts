"""Acha o rosto de quem fala e calcula uma câmera suave para o recorte 9:16 (sem pulos, qualquer resolução)."""
from __future__ import annotations

import math
from pathlib import Path

from . import util

PASSO = 0.2          # amostra de rosto a cada 0,2 s (5 por segundo)
ZONA = 0.035         # a câmera só anda se o rosto sair mais que isso do centro (fração da largura da base)
PARA = 0.008         # e para quando chega perto assim
PASSO_MAX = 0.04     # nunca anda mais que isso por amostra
TAU = 0.8            # aproximação suave (~0,8 s)
JANELA = 0.15        # o mesmo rosto fica a menos disso do centro do grupo


def _planos(cortes, duracao):
    marcas = [0.0] + sorted(c for c in cortes if 0 < c < duracao) + [duracao + 1e-6]
    return list(zip(marcas[:-1], marcas[1:]))


def _grupo_principal(faces):
    """O rosto mais presente e maior do plano: centro do grupo com mais 'peso' (tamanho × aparições)."""
    melhor, peso = None, -1.0
    for f in faces:
        p = sum(g["w"] for g in faces if abs(g["cx"] - f["cx"]) <= 0.12)
        if p > peso:
            melhor, peso = f["cx"], p
    perto = sorted(g["cx"] for g in faces if abs(g["cx"] - melhor) <= JANELA)
    return perto[len(perto) // 2]


def principais(amostras, cortes, duracao):
    """Para cada amostra, o rosto principal do plano (ou None)."""
    out = []
    for a, b in _planos(cortes, duracao):
        doplano = [x for x in amostras if a <= x["t"] < b]
        faces = [f for x in doplano for f in x["rostos"]]
        centro = _grupo_principal(faces) if faces else None
        for x in doplano:
            cand = [f for f in x["rostos"] if centro is not None and abs(f["cx"] - centro) <= JANELA]
            out.append(max(cand, key=lambda f: f["w"]) if cand else None)
    return out


def suavizar(amostras, cortes, duracao):
    """Caminho da câmera [{t, cx, cy}]. No corte de câmera, dois pontos no mesmo t (corte seco)."""
    princ = principais(amostras, cortes, duracao)
    alpha = 1 - math.exp(-PASSO / TAU)
    camera, ultimo = [], (0.5, 0.4)
    i = 0
    for a, b in _planos(cortes, duracao):
        doplano = [x for x in amostras if a <= x["t"] < b]
        alvos = princ[i:i + len(doplano)]
        i += len(doplano)
        validos = [f for f in alvos if f]
        if not validos:
            cx, cy = 0.5, 0.4
            camera += [{"t": round(a, 3), "cx": cx, "cy": cy}, {"t": round(min(b, duracao), 3), "cx": cx, "cy": cy}]
            ultimo = (cx, cy)
            continue
        cx, cy = validos[0]["cx"], validos[0]["cy"]
        camera.append({"t": round(a, 3), "cx": round(cx, 4), "cy": round(cy, 4)})
        hist = []
        andando = [False, False]
        for x, f in zip(doplano, alvos):
            if f:
                hist.append((f["cx"], f["cy"]))
                hist = hist[-3:]
            if not hist:
                continue
            tx = sorted(h[0] for h in hist)[len(hist) // 2]
            ty = sorted(h[1] for h in hist)[len(hist) // 2]
            novo = []
            for k, (cam, alvo) in enumerate(((cx, tx), (cy, ty))):
                d = alvo - cam
                if abs(d) > ZONA:
                    andando[k] = True
                elif abs(d) < PARA:
                    andando[k] = False
                if andando[k]:
                    cam += max(-PASSO_MAX, min(PASSO_MAX, d * alpha if abs(d * alpha) > 0.002 else d))
                novo.append(cam)
            cx, cy = novo
            if x["t"] > a:
                camera.append({"t": round(x["t"], 3), "cx": round(cx, 4), "cy": round(cy, 4)})
        fim = round(min(b, duracao), 3)
        camera.append({"t": fim, "cx": round(cx, 4), "cy": round(cy, 4)})
        ultimo = (cx, cy)
    # tira pontos repetidos (mesmo t e mesma posição), mantendo os pares do corte seco
    limpo = []
    for p in camera:
        if limpo and limpo[-1]["t"] == p["t"] and limpo[-1]["cx"] == p["cx"] and limpo[-1]["cy"] == p["cy"]:
            continue
        limpo.append({"t": p["t"], "cx": min(1.0, max(0.0, p["cx"])), "cy": min(1.0, max(0.0, p["cy"]))})
    return limpo


MODELO = util.raiz_plugin() / "assets" / "modelos" / "face_detection_yunet_2023mar.onnx"


def _detector(cv2, pw, ph):
    """YuNet (rede do OpenCV, MIT) quando dá; senão os Haar antigos (só existem no OpenCV 4)."""
    try:
        cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
    except Exception:
        pass
    if hasattr(cv2, "FaceDetectorYN") and MODELO.exists():
        import numpy as np
        # pelo buffer: com acento no caminho (C:\Users\João\...) o OpenCV não abre o arquivo
        buf = np.fromfile(str(MODELO), dtype=np.uint8)
        yn = cv2.FaceDetectorYN.create("onnx", buf, np.array([], np.uint8), (pw, ph), 0.75, 0.3, 50)

        def yunet(img):
            _, faces = yn.detect(img)
            return [] if faces is None else [tuple(int(v) for v in f[:4]) for f in faces]
        return yunet
    if hasattr(cv2, "CascadeClassifier"):
        frontal = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        perfil = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")

        def haar(img):
            g = cv2.equalizeHist(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
            fs = list(frontal.detectMultiScale(g, 1.1, 5, minSize=(24, 24)))
            if not fs:
                fs = list(perfil.detectMultiScale(g, 1.1, 5, minSize=(24, 24)))
                fs += [(pw - x - w, y, w, h) for x, y, w, h in perfil.detectMultiScale(cv2.flip(g, 1), 1.1, 5, minSize=(24, 24))]
            return fs
        return haar
    raise util.ErroUsuario("o OpenCV instalado não tem detector de rosto; reinstale com: pip install -r requirements.txt")


def rastrear(video, saida_json=None) -> dict:
    import cv2
    import numpy as np

    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise util.ErroUsuario(f"não consegui abrir {video}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    escala = 640 / max(W, H)
    pw, ph = max(1, int(W * escala)), max(1, int(H * escala))
    detectar = _detector(cv2, pw, ph)
    passo_rosto = max(1, round(fps * PASSO))
    passo_corte = max(1, round(fps / 10))
    amostras, cortes, hist_ant = [], [], None
    n = 0
    minimo = max(20, int(min(pw, ph) * 0.06))
    while True:
        ok = cap.grab()
        if not ok:
            break
        if n % passo_corte == 0 or n % passo_rosto == 0:
            ok, fr = cap.retrieve()
            if not ok:
                break
            t = n / fps
            peq = cv2.resize(fr, (pw, ph))
            if n % passo_corte == 0:
                hsv = cv2.cvtColor(cv2.resize(peq, (160, max(1, int(160 * ph / pw)))), cv2.COLOR_BGR2HSV)
                h = cv2.calcHist([hsv], [0, 1], None, [32, 32], [0, 180, 0, 256])
                cv2.normalize(h, h)
                if hist_ant is not None and cv2.compareHist(hist_ant, h, cv2.HISTCMP_CORREL) < 0.6:
                    if not cortes or t - cortes[-1] > 0.5:
                        cortes.append(round(t, 3))
                hist_ant = h
            if n % passo_rosto == 0:
                fs = [(x, y, w, h) for x, y, w, h in detectar(peq) if w >= minimo]
                amostras.append({"t": round(t, 3), "rostos": [
                    {"cx": round((x + w / 2) / pw, 4), "cy": round((y + h / 2) / ph, 4),
                     "w": round(w / pw, 4), "h": round(h / ph, 4)} for x, y, w, h in fs]})
        n += 1
    cap.release()
    duracao = n / fps
    camera = suavizar(amostras, cortes, duracao)
    princ = principais(amostras, cortes, duracao)
    dados = {"largura": W, "altura": H, "fps": fps, "duracao": round(duracao, 3), "cortes": cortes,
             "amostras": amostras, "principal": [{"t": a["t"], **p} if p else {"t": a["t"]} for a, p in zip(amostras, princ)],
             "camera": camera, "com_rosto": sum(1 for p in princ if p)}
    if saida_json:
        util.gravar_json(saida_json, dados, indent=None)
    return dados


def registrar(sub):
    p = sub.add_parser("rosto", help="rastreia o rosto da base.mp4 e grava rostos.json")
    p.add_argument("corte")
    p.set_defaults(func=lambda a: {k: v for k, v in rastrear(Path(a.corte) / "base.mp4", Path(a.corte) / "rostos.json").items()
                                    if k in ("largura", "altura", "cortes", "com_rosto")} | {"ok": True})
