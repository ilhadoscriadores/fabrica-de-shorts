"""Confere o computador: ffmpeg (e se a placa NVIDIA codifica), Node, yt-dlp, Codex e o Whisper na placa."""
from __future__ import annotations

import glob
import os
import platform
import re
import shutil
import site
import sys
from pathlib import Path

from . import util

NVENC = ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", "19", "-b:v", "0"]
X264 = ["-c:v", "libx264", "-preset", "medium", "-crf", "18"]

WINGET = "--source winget --accept-package-agreements --accept-source-agreements"
INSTALAR = {
    "Python": {"windows": f"winget install -e --id Python.Python.3.12 {WINGET}", "mac": "brew install python"},
    "FFmpeg": {"windows": f"winget install -e --id Gyan.FFmpeg {WINGET}", "mac": "brew install ffmpeg"},
    "Node.js": {"windows": f"winget install -e --id OpenJS.NodeJS.LTS {WINGET}", "mac": "brew install node"},
}


def achar_ffmpeg() -> str | None:
    return os.environ.get("FABRICA_FFMPEG") or util.achar("ffmpeg")


def erro_nvenc(ffmpeg: str) -> str | None:
    """Encode de verdade de 1 quadro: o ffmpeg pode listar h264_nvenc e falhar com driver antigo.
    None se a placa codifica; senão as últimas linhas do erro."""
    try:
        util.rodar([ffmpeg, "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=256x256:d=0.1",
                    "-frames:v", "1", "-c:v", "h264_nvenc", "-f", "null", "-"], timeout=60)
        return None
    except Exception as e:
        linhas = [x.strip() for x in str(e).splitlines() if x.strip()]
        return "\n".join(linhas[1:][-3:] or linhas[-1:])[-400:] or type(e).__name__


def testar_nvenc(ffmpeg: str) -> bool:
    return erro_nvenc(ffmpeg) is None


def encoder_video(ffmpeg: str | None = None, pasta=None) -> list[str]:
    """Argumentos do encoder de vídeo: NVENC se a placa funcionar, senão libx264. Guarda em .fabrica/ambiente.json."""
    ffmpeg = ffmpeg or util.ffmpeg()
    cache = Path(pasta or ".") / ".fabrica" / "ambiente.json"
    dados = util.ler_json(cache, {}) if cache.exists() else {}
    if dados.get("ffmpeg") == ffmpeg and "nvenc" in dados:
        return list(NVENC if dados["nvenc"] else X264)
    ok = testar_nvenc(ffmpeg)
    dados.update(ffmpeg=ffmpeg, nvenc=ok)
    try:
        util.gravar_json(cache, dados)
    except OSError:
        pass
    return list(NVENC if ok else X264)


def _dirs_nvidia() -> list[str]:
    dirs = []
    for p in site.getsitepackages() + [site.getusersitepackages()]:
        dirs += glob.glob(os.path.join(p, "nvidia", "*", "bin"))
    return dirs


def carregar_dlls_cuda():
    """Faz o Windows achar cuBLAS/cuDNN instalados pelo pip (pacotes nvidia-*)."""
    for d in _dirs_nvidia():
        os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
        try:
            os.add_dll_directory(d)
        except (OSError, AttributeError):
            pass


def cuda_pronto() -> bool:
    """Só usa a placa se ela existe e as bibliotecas do CUDA (cuBLAS 12 e cuDNN 9) estão presentes.
    Sem o cuDNN o Whisper pode fechar o programa sem aviso, então a conferência é pelos arquivos."""
    if sys.platform == "darwin":
        return False
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() < 1:
            return False
    except Exception:
        return False
    if os.name != "nt":
        return True
    carregar_dlls_cuda()
    caminhos = os.environ.get("PATH", "").split(os.pathsep)
    def tem(padrao):
        return any(glob.glob(os.path.join(d, padrao)) for d in caminhos if d)
    return tem("cublas64_12.dll") and tem("cudnn*64_9.dll")


def whisper_dispositivo() -> tuple[str, str, str]:
    """(device, compute_type, modelo): medium na placa; small no processador."""
    if cuda_pronto():
        return ("cuda", "int8", "medium")
    return ("cpu", "int8", "small")


def _versao(args) -> str | None:
    try:
        r = util.rodar(args, timeout=30)
        return (r.stdout or r.stderr).strip().splitlines()[0]
    except Exception:
        return None


def _versao_node() -> str | None:
    node = util.achar("node")
    return _versao([node, "--version"]) if node else None


def _gpu() -> str | None:
    if not shutil.which("nvidia-smi"):
        return None
    v = _versao(["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"])
    return v


def relatorio(pasta=".") -> dict:
    faltando = []
    ff = achar_ffmpeg()
    ffv = _versao([ff, "-version"]) if ff else None
    if not ff:
        faltando.append({"nome": "FFmpeg", **INSTALAR["FFmpeg"]})
    node = _versao_node()
    node_ok = False
    if node:
        m = re.match(r"v?(\d+)", node)
        node_ok = bool(m and int(m.group(1)) >= 20)
    npm_exe = util.achar("npm")
    npm = _versao([npm_exe, "--version"]) if npm_exe else None
    if not node_ok or not npm:
        faltando.append({"nome": "Node.js", **INSTALAR["Node.js"]})
    py_ok = sys.version_info >= (3, 10)
    if not py_ok:
        faltando.append({"nome": "Python", **INSTALAR["Python"]})
    try:
        import yt_dlp.version
        ytv = yt_dlp.version.__version__
    except Exception:
        ytv = None
    try:
        import faster_whisper
        fw = faster_whisper.__version__
    except Exception:
        fw = None
    pip_falta = [n for n, v in (("yt-dlp", ytv), ("faster-whisper", fw)) if not v]
    try:
        livre = shutil.disk_usage(Path(pasta).resolve()).free / 1e9
    except OSError:
        livre = None
    gpu = _gpu()
    motivo = erro_nvenc(ff) if (ff and gpu) else None
    rel = {
        "sistema": f"{platform.system()} {platform.release()}",
        "python": {"versao": sys.version.split()[0], "ok": py_ok, "exe": sys.executable},
        "ffmpeg": {"ok": bool(ff), "caminho": ff, "versao": ffv,
                   "nvenc": bool(ff and gpu) and motivo is None},
        "node": {"ok": node_ok, "versao": node, "npm": npm},
        "yt_dlp": ytv, "faster_whisper": fw,
        "pip_faltando": pip_falta,
        "codex": shutil.which("codex"),
        "gpu": gpu,
        "whisper": "placa (CUDA)" if (gpu and fw and cuda_pronto()) else "processador",
        "disco_livre_gb": round(livre, 1) if livre is not None else None,
        "faltando": faltando,
    }
    if motivo:  # placa NVIDIA que não codifica: quase sempre driver antigo
        rel["nvenc_motivo"] = motivo
    return rel


def _cmd_ambiente(args):
    rel = relatorio(".")
    rel["ok"] = not rel["faltando"] and not rel["pip_faltando"]
    return rel


def registrar(sub):
    p = sub.add_parser("ambiente", help="confere o que está instalado e o que falta")
    p.set_defaults(func=_cmd_ambiente)
