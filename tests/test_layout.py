"""Corte de live: webcam em cima, jogo embaixo (layout empilhado)."""
import numpy as np

from fabrica import config, montagem, rosto, util


def _quadros_live(n=14, W=960, H=540, cam=(0, 0, 220, 120), seed=0):
    """Jogo mudando a cada quadro; webcam parada num canto, com moldura clara."""
    rng = np.random.default_rng(seed)
    x, y, w, h = cam
    fundo_cam = rng.integers(40, 90, (h, w, 3), dtype=np.uint8)
    qs = []
    for _ in range(n):
        q = rng.integers(0, 255, (H, W, 3), dtype=np.uint8)
        q[y:y + h, x:x + w] = fundo_cam
        q[y:y + h, x + w - 3:x + w] = 250  # moldura
        q[y + h - 3:y + h, x:x + w] = 250
        qs.append(q)
    return qs


def test_caixa_da_webcam_pela_borda_de_movimento():
    qs = _quadros_live()
    caixa, metodo = rosto._caixa_canto_se(qs, (70, 40, 20, 26))
    assert metodo == "bordas"
    x, y, w, h = caixa
    assert x <= 8 and y <= 8 and abs((x + w) - 220) <= 10 and abs((y + h) - 120) <= 10


def test_sem_borda_clara_usa_caixa_em_volta_do_rosto():
    rng = np.random.default_rng(1)
    qs = [np.full((540, 960, 3), 80, np.uint8) + rng.integers(0, 3, (540, 960, 3), dtype=np.uint8) for _ in range(10)]
    caixa, metodo = rosto._caixa_canto_se(qs, (70, 40, 20, 26))
    assert metodo == "rosto" and caixa[2] > 20 * 4


def test_layout_com_webcam_informada_no_corte(tmp_path):
    lay = montagem.layout_empilhado(tmp_path, {"layout": "empilhado", "webcam": [6, 6, 434, 234]}, 1920, 1080)
    assert lay["tipo"] == "empilhado" and lay["cam"] == {"x": 6, "y": 6, "w": 434, "h": 234}
    assert 0.28 <= lay["divisao"] <= 0.42
    j = lay["jogo"]
    assert j["h"] == 1080 and j["x"] >= 6 + 434  # o jogo não pega a webcam
    # o painel de baixo tem o formato do pedaço do jogo
    assert abs(j["w"] / j["h"] - 1080 / (1920 * (1 - lay["divisao"]))) < 0.01


def test_layout_le_o_webcam_json_e_sem_pedido_fica_normal(tmp_path):
    util.gravar_json(tmp_path / "webcam.json", {"caixa": [1500, 10, 400, 225], "largura": 1920, "altura": 1080,
                                                "rosto": {"cx": 0.6, "cy": 0.5}})
    lay = montagem.layout_empilhado(tmp_path, {"layout": "empilhado"}, 1920, 1080)
    assert lay["foco_cam"] == 0.6 and lay["jogo"]["x"] + lay["jogo"]["w"] <= 1500
    assert montagem.layout_empilhado(tmp_path, {}, 1920, 1080) is None


def test_validacao_do_layout_e_da_webcam(tmp_path):
    erros = config.validar_corte({"trechos": [[0, 1]], "layout": "lado-a-lado", "webcam": [1, 2, 3]}, tmp_path)
    assert any("layout" in e for e in erros) and any("webcam" in e for e in erros)


def test_capa_empilhada_tem_webcam_em_cima_e_jogo_embaixo():
    from PIL import Image

    from fabrica import entrega
    img = Image.new("RGB", (1920, 1080), (0, 0, 255))  # jogo azul
    img.paste(Image.new("RGB", (434, 234), (255, 0, 0)), (6, 6))  # webcam vermelha
    lay = montagem.layout_empilhado(".", {"layout": "empilhado", "webcam": [6, 6, 434, 234]}, 1920, 1080)
    tela = entrega._empilhar(img, lay, round(lay["divisao"] * 1920), Image)
    assert tela.size == (1080, 1920)
    assert tela.getpixel((540, 100)) == (255, 0, 0) and tela.getpixel((540, 1500)) == (0, 0, 255)
