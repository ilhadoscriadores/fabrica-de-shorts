"""Peças comuns: rodar programas sem shell, ler/gravar JSON, ler áudio e o envelope da voz."""
from __future__ import annotations

import glob
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

import numpy as np

SR = 48000


class ErroUsuario(Exception):
    """Erro que o usuário resolve (arquivo faltando, dado errado). Sai com código 1, sem traceback."""


class ErroComando(Exception):
    """Um programa externo (ffmpeg, yt-dlp, npx...) falhou."""


def _utf8():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def achar(nome: str) -> str | None:
    """Caminho do programa. No Windows, se o PATH não acha, procura onde o winget e o Node instalam:
    o PATH desta sessão é de antes da instalação e só atualiza abrindo o Claude Code de novo."""
    p = shutil.which(nome)
    if p or os.name != "nt" or os.sep in nome or "/" in nome:
        return p
    exts = [""] if Path(nome).suffix else [".exe", ".cmd", ".bat"]
    local, pf = os.environ.get("LOCALAPPDATA"), os.environ.get("ProgramFiles")
    pastas = ([Path(local) / "Microsoft" / "WinGet" / "Links"] if local else []) + ([Path(pf) / "nodejs"] if pf else [])
    for d in pastas:
        for ext in exts:
            if (d / (nome + ext)).is_file():
                return str(d / (nome + ext))
    if local and nome.lower() in ("ffmpeg", "ffprobe"):
        achados = glob.glob(os.path.join(local, "Microsoft", "WinGet", "Packages", "Gyan.FFmpeg*", "**", "bin", nome + ".exe"),
                            recursive=True)
        if achados:
            return sorted(achados)[-1]
    return None


def _resolver(exe: str) -> str:
    """No Windows, npm/npx/codex são .cmd e só rodam pelo caminho completo."""
    if os.name == "nt" and not exe.lower().endswith((".exe", ".com")):
        achado = achar(exe)
        if achado:
            return achado
    return exe


def _env_com_pasta(exe: str, env):
    """Programa achado fora do PATH: a pasta dele entra no PATH do filho (o npm install chama `node`)."""
    pasta = os.path.dirname(exe)
    base = os.environ if env is None else env
    caminhos = base.get("PATH", "")
    if os.name != "nt" or not pasta or os.path.normcase(pasta) in {os.path.normcase(c.rstrip("\\/")) for c in caminhos.split(os.pathsep)}:
        return env
    return {**base, "PATH": pasta + os.pathsep + caminhos}


def rodar(args, cwd=None, env=None, capturar=True, timeout=None) -> subprocess.CompletedProcess:
    """Roda um programa com lista de argumentos (nunca shell). Levanta ErroComando se falhar."""
    args = [str(a) for a in args]
    exe = args[0]
    args[0] = _resolver(exe)
    if args[0] != exe:
        env = _env_com_pasta(args[0], env)
    try:
        r = subprocess.run(args, cwd=cwd, env=env, capture_output=capturar, timeout=timeout,
                           text=True, encoding="utf-8", errors="replace")
    except FileNotFoundError as e:
        raise ErroComando(f"programa não encontrado: {exe}") from e
    if r.returncode != 0:
        cauda = ((r.stderr or "") + (r.stdout or "")).strip()[-1500:] if capturar else ""
        raise ErroComando(f"{Path(exe).name} falhou (código {r.returncode}): {' '.join(args[1:8])} ...\n{cauda}")
    return r


def rodar_bytes(args, cwd=None) -> bytes:
    """Roda e devolve a saída binária (áudio cru, quadros)."""
    args = [str(a) for a in args]
    args[0] = _resolver(args[0])
    r = subprocess.run(args, cwd=cwd, capture_output=True)
    if r.returncode != 0:
        raise ErroComando(f"{Path(args[0]).name} falhou: {r.stderr.decode('utf-8', 'replace')[-800:]}")
    return r.stdout


def resultado(dados: dict, codigo: int = 0):
    """Última linha de todo comando: RESULTADO: {json}. Sai com o código."""
    _utf8()
    print("RESULTADO: " + json.dumps(dados, ensure_ascii=False))
    sys.stdout.flush()
    raise SystemExit(codigo)


def ler_json(p, padrao=None):
    p = Path(p)
    if not p.exists():
        if padrao is not None:
            return padrao
        raise ErroUsuario(f"não achei o arquivo {p}")
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as e:
        raise ErroUsuario(f"o arquivo {p.name} não é um JSON válido (linha {e.lineno}, coluna {e.colno}): {e.msg}")


def gravar_json(p, obj, indent=1):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=indent), encoding="utf-8", newline="\n")


def ffmpeg() -> str:
    """O ffmpeg a usar: FABRICA_FFMPEG, senão o do PATH (ou o que o winget instalou)."""
    f = os.environ.get("FABRICA_FFMPEG") or achar("ffmpeg")
    if not f:
        raise ErroUsuario("o ffmpeg não está instalado. Rode /fabrica-de-shorts:comecar para instalar.")
    return f


def ffprobe() -> str:
    f = Path(ffmpeg())
    irmao = f.with_name("ffprobe" + f.suffix)
    if irmao.exists():
        return str(irmao)
    p = achar("ffprobe")
    if not p:
        raise ErroUsuario("o ffprobe (vem junto com o ffmpeg) não foi encontrado.")
    return p


def sondar(video) -> dict:
    """Largura, altura, fps e durações de um vídeo."""
    r = rodar([ffprobe(), "-v", "error", "-show_streams", "-show_format", "-of", "json", str(video)])
    info = json.loads(r.stdout)
    v = next((s for s in info["streams"] if s.get("codec_type") == "video"), None)
    a = next((s for s in info["streams"] if s.get("codec_type") == "audio"), None)
    out = {"duracao": float(info["format"].get("duration", 0) or 0), "tem_audio": a is not None}
    if v:
        num, den = (v.get("avg_frame_rate") or v.get("r_frame_rate") or "30/1").split("/")
        fps = float(num) / float(den) if float(den or 0) else 30.0
        out.update(largura=int(v["width"]), altura=int(v["height"]), fps=fps,
                   duracao_video=float(v.get("duration", out["duracao"]) or out["duracao"]),
                   quadros=int(v.get("nb_frames", 0) or 0))
        rot = 0
        for sd in v.get("side_data_list", []) or []:
            rot = int(sd.get("rotation", 0) or 0)
        if abs(rot) in (90, 270):
            out["largura"], out["altura"] = out["altura"], out["largura"]
    if a:
        out["duracao_audio"] = float(a.get("duration", out["duracao"]) or out["duracao"])
    return out


def ler_audio(caminho, sr: int = SR) -> np.ndarray:
    """Áudio mono float32 de qualquer arquivo."""
    args = [ffmpeg(), "-v", "error", "-i", str(caminho), "-vn", "-f", "f32le", "-ac", "1", "-ar", str(sr), "-"]
    return np.frombuffer(rodar_bytes(args), np.float32)


def envelope_db(wav=None, passo: float = 0.01, sr: int = SR, x: np.ndarray | None = None) -> np.ndarray:
    """Volume (dB RMS) a cada `passo` segundos."""
    if x is None:
        x = ler_audio(wav, sr)
    h = int(sr * passo)
    n = len(x) // h
    if n == 0:
        return np.zeros(0)
    blocos = x[: n * h].reshape(n, h).astype(np.float64)
    return 20 * np.log10(np.sqrt((blocos ** 2).mean(axis=1)) + 1e-9)


def normalizar(s: str) -> str:
    """Minúsculas, sem acento e sem pontuação (para comparar palavras)."""
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", s)


def slug(s: str, maximo: int = 40) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:maximo].strip("-") or "corte"


def raiz_plugin() -> Path:
    """Pasta do plugin (onde ficam scripts/, editor/, assets/)."""
    return Path(__file__).resolve().parents[2]
