import random

import pytest

from fabrica import rosto, util


def _amostras(fn, dur=10.0, passo=0.2):
    out, t = [], 0.0
    while t < dur:
        out.append({"t": round(t, 2), "rostos": fn(t)})
        t += passo
    return out


def R(cx, cy=0.4, w=0.18):
    return {"cx": cx, "cy": cy, "w": w, "h": w * 1.2}


def test_sem_pulos_dentro_do_plano():
    rnd = random.Random(3)

    def fn(t):
        faces = [R(0.5 + rnd.uniform(-0.08, 0.08))]
        if abs(t - 4.0) < 0.01:  # falso positivo isolado lá no canto
            faces.append(R(0.12, w=0.25))
        return faces

    cam = rosto.suavizar(_amostras(fn), cortes=[], duracao=10.0)
    xs = [p["cx"] for p in cam]
    assert max(abs(a - b) for a, b in zip(xs, xs[1:])) <= 0.04 + 1e-9
    assert min(xs) > 0.38 and max(xs) < 0.62


def test_nao_pula_para_o_outro_entrevistado():
    # entrevistado principal (grande, sempre) em 0.3; o outro aparece às vezes em 0.75
    cam = rosto.suavizar(_amostras(lambda t: [R(0.3, w=0.2)] + ([R(0.75, w=0.12)] if int(t) % 3 == 0 else [])),
                         cortes=[], duracao=10.0)
    assert all(abs(p["cx"] - 0.3) < 0.05 for p in cam)


def test_corte_vira_ponto_repetido():
    cam = rosto.suavizar(_amostras(lambda t: [R(0.3 if t < 5 else 0.7)]), cortes=[5.0], duracao=10.0)
    no_corte = [p for p in cam if abs(p["t"] - 5.0) < 1e-6]
    assert len(no_corte) == 2
    assert no_corte[0]["cx"] == pytest.approx(0.3, abs=0.03) and no_corte[1]["cx"] == pytest.approx(0.7, abs=0.03)


def test_plano_sem_rosto_usa_o_centro():
    cam = rosto.suavizar(_amostras(lambda t: []), cortes=[], duracao=4.0)
    assert all(p["cx"] == 0.5 for p in cam)


def test_principal_por_amostra():
    am = _amostras(lambda t: [R(0.3, w=0.2), R(0.8, w=0.1)], dur=2.0)
    princ = rosto.principais(am, cortes=[], duracao=2.0)
    assert all(p and p["cx"] == 0.3 for p in princ)


@pytest.mark.parametrize("tam", ["1280x720", "1080x1350"])
def test_resolucao_qualquer(tmp_path, tam):
    v = tmp_path / "base.mp4"
    util.rodar([util.ffmpeg(), "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=s={tam}:r=30:d=3",
                "-c:v", "libx264", "-preset", "ultrafast", str(v)])
    r = rosto.rastrear(v, tmp_path / "rostos.json")
    larg, alt = map(int, tam.split("x"))
    assert r["largura"] == larg and r["altura"] == alt
    assert r["camera"] and all(0 <= p["cx"] <= 1 and 0 <= p["cy"] <= 1 for p in r["camera"])
    assert (tmp_path / "rostos.json").exists()
