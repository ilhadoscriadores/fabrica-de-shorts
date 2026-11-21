import pytest

from fabrica import revisao, util


def _video(tmp_path, nome="v.mp4", dur=5, vf="null", af="anull", adur=None):
    p = tmp_path / nome
    util.rodar([util.ffmpeg(), "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=s=216x384:r=30:d={dur}",
                "-f", "lavfi", "-i", f"sine=f=330:d={adur or dur}", "-vf", vf, "-af", af,
                "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", str(p)])
    return p


def _textos(r):
    return " | ".join(r["erros"])


def test_acusa_quadro_preto(tmp_path):
    v = _video(tmp_path, vf="drawbox=c=black:t=fill:enable='between(t,2,3)'")
    r = revisao.revisar(v, None, transcrever_de_novo=False)
    assert "preto" in _textos(r)
    assert r["aprovado"] is False


def test_acusa_congelado(tmp_path):
    v = _video(tmp_path, vf="loop=loop=35:size=1:start=45,setpts=N/30/TB")
    r = revisao.revisar(v, None, transcrever_de_novo=False)
    assert "congelad" in _textos(r)


def test_acusa_audio_estourado(tmp_path):
    v = _video(tmp_path, af="volume=12")
    r = revisao.revisar(v, None, transcrever_de_novo=False)
    assert "pico" in _textos(r)


def test_acusa_av_diferente(tmp_path):
    v = _video(tmp_path, dur=5, adur=4.5)
    r = revisao.revisar(v, None, transcrever_de_novo=False)
    assert "tamanho" in _textos(r)


def test_relatorio_markdown_tem_veredito(tmp_path):
    v = _video(tmp_path, af="volume=4")
    r = revisao.revisar(v, None, transcrever_de_novo=False)
    md = (tmp_path / "revisao.md").read_text(encoding="utf-8")
    assert md.startswith("# Revisão automática")
    assert ("APROVADO" in md) or ("REPROVADO" in md)
    assert r["relatorio"].endswith("revisao.md")


def test_legenda_atrasada_reprova(corte_sintetico):
    from fabrica import montagem
    _, c = corte_sintetico
    montagem.montar_dados(c)
    ok = revisao.revisar(c / "base.mp4", c, transcrever_de_novo=False)
    assert not [e for e in ok["erros"] if "legenda" in e.lower()], ok["erros"]
    bs = util.ler_json(c / "legendas.json")
    for b in bs:
        b["f0"] += 5  # 167 ms atrasada
        b["palavras"][0]["f0"] = b["f0"]
    util.gravar_json(c / "legendas.json", bs)
    r = revisao.revisar(c / "base.mp4", c, transcrever_de_novo=False)
    assert any("DEPOIS da voz" in e for e in r["erros"]), r["erros"]


def test_palavrao_que_vaza_reprova(corte_sintetico):
    from fabrica import montagem
    _, c = corte_sintetico
    montagem.montar_dados(c)
    tl = util.ler_json(c / "timeline.json")
    tl["censuras"] = [[0.2, 0.5]]  # trecho com voz que deveria estar mudo
    util.gravar_json(c / "timeline.json", tl)
    r = revisao.revisar(c / "base.mp4", c, transcrever_de_novo=False)
    assert any("palavrão" in e for e in r["erros"]), r["erros"]
