import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PLUGIN = RAIZ / "plugins" / "fabrica-de-shorts"
sys.path.insert(0, str(PLUGIN / "scripts"))

import pytest  # noqa: E402


def pytest_configure(config):
    config.addinivalue_line("markers", "lento: teste de integração (render, rede ou Whisper)")


@pytest.fixture
def plugin_dir():
    return PLUGIN


def _junction(alvo, link):
    """node_modules do editor do plugin dentro da pasta de teste (sem npm install)."""
    import _winapi
    _winapi.CreateJunction(str(alvo), str(link))


@pytest.fixture
def corte_sintetico(tmp_path):
    """Pasta de trabalho com um corte de ~6 s pronto para a edição (base, voz, timeline, rostos)."""
    from fabrica import base, preparar, util
    preparar.preparar(tmp_path, sem_npm=True, respostas={"nome": "Teste", "arroba": "@teste", "nicho": "podcast"})
    c = tmp_path / "cortes" / "001-teste"
    (c / "imagens").mkdir(parents=True)
    rajadas = [(1.0, 1.8), (2.3, 3.1), (3.6, 4.4), (5.0, 5.8)]
    expr = "+".join(f"between(t,{a},{b})" for a, b in rajadas)
    util.rodar([util.ffmpeg(), "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=1280x720:r=30:d=7",
                "-f", "lavfi", "-i", "sine=f=220:d=7", "-filter_complex", f"[1:a]volume='if({expr},0.4,0.0003)':eval=frame[a]",
                "-map", "0:v", "-map", "[a]", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", str(c / "bruto.mp4")])
    textos = ["olha só,", "a polícia chegou.", "e o cara correu", "pro mato."]
    ws = []
    for (a, b), frase in zip(rajadas, textos):
        ps = frase.split()
        for k, p in enumerate(ps):
            ws.append({"w": p, "s": round(a + k * (b - a) / len(ps), 3), "e": round(a + (k + 1) * (b - a) / len(ps), 3)})
    util.gravar_json(c / "palavras.json", ws)
    util.rodar([util.ffmpeg(), "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x334455:s=1024x1536:d=1", "-frames:v", "1", str(c / "imagens" / "01.png")])
    util.gravar_json(c / "corte.json", {"trechos": [[0.9, 5.9]], "edicao": {}})
    base.base(c, rosto=True)
    return tmp_path, c
