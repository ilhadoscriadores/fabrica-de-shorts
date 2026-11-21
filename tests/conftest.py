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
