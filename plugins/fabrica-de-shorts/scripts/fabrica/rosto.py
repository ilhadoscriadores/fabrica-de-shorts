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


# ---------- live com webcam: acha a caixa da webcam (para o layout empilhado) ----------
CANTO_L, CANTO_A = 0.45, 0.5   # área de cada canto onde a webcam é procurada (fração da largura/altura)
ROSTO_MAX = 0.09               # rosto maior que isso (fração da largura) não é webcam de canto: é podcast
PRESENCA_MIN = 0.5             # o rosto aparece em pelo menos metade das amostras
DEGRAU_MIN = 12.0              # salto de "movimento" (desvio no tempo) entre a webcam parada e o jogo


def _amostras(video, n=16):
    import cv2
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise util.ErroUsuario(f"não consegui abrir {video}")
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    quadros = []
    for i in [int(x) for x in __import__("numpy").linspace(0, total - 1, n + 2)[1:-1]]:
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, fr = cap.read()
        if ok:
            quadros.append(fr)
    cap.release()
    return quadros


def _degrau(perfil, a, b, k=12):
    """Posição onde o perfil mais sobe (média dos k depois − média dos k antes), entre a e b."""
    melhor = (0.0, None)
    for x in range(max(a, k), min(b, len(perfil) - k)):
        d = float(perfil[x:x + k].mean() - perfil[x - k:x].mean())
        if d > melhor[0]:
            melhor = (d, x)
    return melhor


def _caixa_canto_se(quadros, rosto):
    """Caixa da webcam com o canto em cima à esquerda (os outros cantos chegam espelhados)."""
    import cv2
    import numpy as np
    H, W = quadros[0].shape[:2]
    fx, fy, fw, fh = rosto
    g = np.stack([cv2.cvtColor(q, cv2.COLOR_BGR2GRAY).astype(np.float32) for q in quadros])
    mov = g.std(0)  # a webcam (quarto parado) mexe pouco; o jogo mexe muito
    y1, y2 = int(max(0, fy - fh)), int(min(H, fy + 2 * fh))
    d_dir, dir_ = _degrau(mov[y1:y2].mean(0), int(fx + fw * 1.3), int(W * 0.6))
    x1, x2 = int(max(0, fx - fw)), int(min(W, fx + 2 * fw))
    d_bai, bai = _degrau(mov[:, x1:x2].mean(1), int(fy + fh * 1.3), int(H * 0.65))
    if d_dir < DEGRAU_MIN or d_bai < DEGRAU_MIN or dir_ is None or bai is None:
        # sem borda clara: uma caixa em volta do rosto, no formato 16:9
        w = min(W * 0.4, fw * 6.0)
        h = w * 9 / 16
        x = max(0.0, min(fx + fw / 2 - w / 2, W - w))
        y = max(0.0, min(fy + fh / 2 - h * 0.45, H - h))
        return [x, y, w, h], "rosto"
    # a moldura costuma ter uma linha forte por dentro do degrau: ela é a borda de verdade
    gx = np.mean([np.abs(cv2.Sobel(a, cv2.CV_32F, 1, 0, ksize=3)) for a in g], 0)
    gy = np.mean([np.abs(cv2.Sobel(a, cv2.CV_32F, 0, 1, ksize=3)) for a in g], 0)
    lin = gy[:, :dir_].mean(1)
    a = int(fy + fh * 1.5)
    if bai + 4 > a and lin[a:bai + 4].max() > 4 * np.median(lin[a:bai + 4]):
        bai = a + int(np.argmax(lin[a:bai + 4]))
    col = gx[:bai, :].mean(0)
    a = int(fx + fw * 1.5)
    if dir_ + 4 > a and col[a:dir_ + 4].max() > 4 * np.median(col[a:dir_ + 4]):
        dir_ = a + int(np.argmax(col[a:dir_ + 4]))
    # borda de dentro (webcam que não encosta no canto): o movimento cai ao entrar na webcam
    d_esq, esq = _degrau(-mov[y1:y2].mean(0), 0, int(max(1, fx - fw * 0.3)))
    d_cim, cim = _degrau(-mov[:, x1:x2].mean(1), 0, int(max(1, fy - fh * 0.3)))
    esq = esq if (esq is not None and d_esq >= DEGRAU_MIN) else 0
    cim = cim if (cim is not None and d_cim >= DEGRAU_MIN) else 0
    m = 6  # tira a moldura
    return [esq + m, cim + m, max(10, dir_ - esq - 2 * m), max(10, bai - cim - 2 * m)], "bordas"


def achar_webcam(video) -> dict | None:
    """Live com webcam num canto: {"caixa": [x, y, w, h] em px, "canto", "rosto": {cx, cy} na caixa (0 a 1), "metodo"}.
    None quando não tem webcam de canto (podcast, vídeo de tela cheia)."""
    import cv2
    import numpy as np
    quadros = _amostras(video)
    if not quadros:
        return None
    H, W = quadros[0].shape[:2]
    cw, ch = int(W * CANTO_L), int(H * CANTO_A)
    esc = 640 / cw
    detectar = _detector(cv2, 640, int(ch * esc))
    melhor = None
    for canto, (inv_x, inv_y) in {"se": (False, False), "sd": (True, False), "ie": (False, True), "id": (True, True)}.items():
        vistos = []
        for q in quadros:
            fq = q[:, ::-1] if inv_x else q
            fq = fq[::-1] if inv_y else fq
            c = cv2.resize(np.ascontiguousarray(fq[:ch, :cw]), (640, int(ch * esc)))
            fs = [(x / esc, y / esc, w / esc, h / esc) for x, y, w, h in detectar(c)]
            if fs:
                vistos.append(max(fs, key=lambda b: b[2]))
        if len(vistos) >= PRESENCA_MIN * len(quadros) and (melhor is None or len(vistos) > len(melhor[2])):
            melhor = (canto, (inv_x, inv_y), vistos)
    if not melhor:
        return None
    canto, (inv_x, inv_y), vistos = melhor
    rosto = [float(np.median([b[i] for b in vistos])) for i in range(4)]
    if rosto[2] > ROSTO_MAX * W:
        return None
    espelhados = [np.ascontiguousarray((q[:, ::-1] if inv_x else q)[::-1] if inv_y else (q[:, ::-1] if inv_x else q))
                  for q in quadros]
    (x, y, w, h), metodo = _caixa_canto_se(espelhados, rosto)
    if inv_x:
        x = W - x - w
    if inv_y:
        y = H - y - h
    rx = (W - rosto[0] - rosto[2] / 2) if inv_x else rosto[0] + rosto[2] / 2
    ry = (H - rosto[1] - rosto[3] / 2) if inv_y else rosto[1] + rosto[3] / 2
    caixa = [round(x), round(y), round(w), round(h)]
    return {"caixa": caixa, "canto": canto, "metodo": metodo, "largura": W, "altura": H,
            "rosto": {"cx": round(min(1, max(0, (rx - x) / w)), 3), "cy": round(min(1, max(0, (ry - y) / h)), 3)}}


def registrar(sub):
    p = sub.add_parser("rosto", help="rastreia o rosto da base.mp4 e grava rostos.json")
    p.add_argument("corte")
    p.set_defaults(func=lambda a: {k: v for k, v in rastrear(Path(a.corte) / "base.mp4", Path(a.corte) / "rostos.json").items()
                                    if k in ("largura", "altura", "cortes", "com_rosto")} | {"ok": True})

    p = sub.add_parser("webcam", help="acha a webcam da live (canto) na base.mp4 e grava webcam.json + previa_webcam.jpg")
    p.add_argument("corte")
    p.set_defaults(func=lambda a: _cmd_webcam(Path(a.corte)))


def _cmd_webcam(pasta: Path) -> dict:
    w = achar_webcam(pasta / "base.mp4")
    if not w:
        return {"ok": True, "webcam": None, "dica": "não achei webcam de canto: o corte fica no recorte normal (layout de podcast)"}
    util.gravar_json(pasta / "webcam.json", w)
    x, y, cw, ch = w["caixa"]
    util.rodar([util.ffmpeg(), "-v", "error", "-y", "-ss", "1", "-i", str(pasta / "base.mp4"), "-frames:v", "1",
                "-vf", f"drawbox=x={x}:y={y}:w={cw}:h={ch}:color=yellow:t=6,scale=960:-1", str(pasta / "previa_webcam.jpg")])
    return {"ok": True, "webcam": w, "previa": str(pasta / "previa_webcam.jpg")}
