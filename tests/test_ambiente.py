import subprocess

from fabrica import ambiente, util


def _falso_rodar(falhar_com):
    def rodar(args, **kw):
        if any(falhar_com in str(a) for a in args):
            raise util.ErroComando("h264_nvenc falhou: Driver does not support the required nvenc API version")
        return subprocess.CompletedProcess(args, 0, "", "")
    return rodar


def test_encoder_cai_para_x264_quando_nvenc_falha(monkeypatch, tmp_path):
    monkeypatch.setattr(ambiente.util, "rodar", _falso_rodar("h264_nvenc"))
    enc = ambiente.encoder_video("ffmpeg", pasta=tmp_path)
    assert enc[:2] == ["-c:v", "libx264"]
    assert "-crf" in enc


def test_encoder_usa_nvenc_quando_teste_passa(monkeypatch, tmp_path):
    monkeypatch.setattr(ambiente.util, "rodar", _falso_rodar("nada-falha"))
    enc = ambiente.encoder_video("ffmpeg", pasta=tmp_path)
    assert enc == ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", "19", "-b:v", "0"]


def test_encoder_fica_em_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(ambiente.util, "rodar", _falso_rodar("nada-falha"))
    ambiente.encoder_video("ffmpeg", pasta=tmp_path)
    monkeypatch.setattr(ambiente.util, "rodar", _falso_rodar("h264_nvenc"))
    assert ambiente.encoder_video("ffmpeg", pasta=tmp_path)[1] == "h264_nvenc"
    assert (tmp_path / ".fabrica" / "ambiente.json").exists()


def test_relatorio_lista_comando_winget_do_que_falta(monkeypatch, tmp_path):
    real = ambiente.shutil.which
    monkeypatch.setattr(ambiente.shutil, "which", lambda n: None if n in ("node", "npm") else real(n))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))  # nem nas pastas do winget
    monkeypatch.setenv("ProgramFiles", str(tmp_path))
    rel = ambiente.relatorio(tmp_path)
    nomes = {f["nome"]: f for f in rel["faltando"]}
    assert "Node.js" in nomes
    assert "winget install" in nomes["Node.js"]["windows"] and "OpenJS.NodeJS.LTS" in nomes["Node.js"]["windows"]
    for item in ambiente.INSTALAR.values():  # sem pergunta de licença nem de fonte (msstore) no meio
        assert "--source winget --accept-package-agreements --accept-source-agreements" in item["windows"]
    assert "brew install node" in nomes["Node.js"]["mac"]
    assert rel["ffmpeg"]["ok"] is True


def test_relatorio_acha_node_e_ffmpeg_instalados_agora(monkeypatch, tmp_path):
    """O winget acabou de instalar: o PATH da sessão não tem, mas a pasta do winget e a do Node têm."""
    real = ambiente.util.achar
    monkeypatch.setattr(ambiente.util, "achar", lambda n: f"C:/novo/{n}.exe" if n in ("ffmpeg", "node", "npm") else real(n))
    monkeypatch.delenv("FABRICA_FFMPEG", raising=False)
    monkeypatch.setattr(ambiente, "_versao", lambda args: {"node": "v22.11.0", "npm": "10.9.0"}.get(
        str(args[0]).rsplit("/", 1)[-1].removesuffix(".exe"), "ffmpeg version 8.0"))
    monkeypatch.setattr(ambiente, "_gpu", lambda: None)
    rel = ambiente.relatorio(tmp_path)
    assert rel["ffmpeg"]["caminho"] == "C:/novo/ffmpeg.exe" and rel["node"]["ok"] is True
    assert not any(f["nome"] in ("FFmpeg", "Node.js") for f in rel["faltando"])


def test_python_novo_demais_ganha_aviso(monkeypatch, tmp_path):
    monkeypatch.setattr(ambiente, "_versao_python", lambda: (3, 15))
    rel = ambiente.relatorio(tmp_path)
    assert "3.12" in rel["aviso_python"] and "3.15" in rel["aviso_python"]
    monkeypatch.setattr(ambiente, "_versao_python", lambda: (3, 14))
    assert "aviso_python" not in ambiente.relatorio(tmp_path)


def test_node_antigo_conta_como_faltando(monkeypatch, tmp_path):
    monkeypatch.setattr(ambiente, "_versao_node", lambda: "v18.19.0")
    rel = ambiente.relatorio(tmp_path)
    assert any(f["nome"] == "Node.js" for f in rel["faltando"])


def test_whisper_sem_dlls_cuda_usa_cpu_small(monkeypatch):
    monkeypatch.setattr(ambiente, "cuda_pronto", lambda: False)
    assert ambiente.whisper_dispositivo() == ("cpu", "int8", "small")


ERRO_DRIVER = ("ffmpeg falhou (código 4294967274): -v error -f lavfi ...\n"
               "[h264_nvenc @ 000001] Driver does not support the required nvenc API version. Required: 12.1 Found: 9.1\n"
               "[h264_nvenc @ 000001] The minimum required Nvidia driver for nvenc is 531.61 or newer\n"
               "Error while opening encoder - maybe incorrect parameters such as bit_rate, rate, width or height")


def _nvenc_falha(monkeypatch, gpu="NVIDIA GeForce GTX 1060 6GB, 391.35"):
    real = ambiente.util.rodar

    def rodar(args, **kw):
        if "h264_nvenc" in args:
            raise util.ErroComando(ERRO_DRIVER)
        return real(args, **kw)
    monkeypatch.setattr(ambiente.util, "rodar", rodar)
    monkeypatch.setattr(ambiente, "_gpu", lambda: gpu)
    monkeypatch.setattr(ambiente, "cuda_pronto", lambda: False)


def test_relatorio_diz_por_que_o_nvenc_falhou(monkeypatch, tmp_path):
    _nvenc_falha(monkeypatch)
    rel = ambiente.relatorio(tmp_path)
    assert rel["ffmpeg"]["nvenc"] is False
    assert "531.61" in rel["nvenc_motivo"] and "Driver does not support" in rel["nvenc_motivo"]
    assert "-v error" not in rel["nvenc_motivo"] and len(rel["nvenc_motivo"]) <= 400


def test_relatorio_sem_placa_nao_tem_motivo(monkeypatch, tmp_path):
    _nvenc_falha(monkeypatch, gpu=None)
    assert "nvenc_motivo" not in ambiente.relatorio(tmp_path)
