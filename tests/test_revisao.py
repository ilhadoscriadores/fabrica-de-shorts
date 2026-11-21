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


def _bloco(texto, f0):
    return {"f0": f0, "f1": f0 + 20, "tam": 92,
            "palavras": [{"w": w, "f0": f0, "f1": f0 + 5, "destaque": False, "censura": False} for w in texto.split()]}


def test_segunda_conferencia_ignora_palavra_solta():
    blocos = [_bloco("EU ACENHEI", 335)]
    hip = [{"w": "eu", "s": 11.42, "e": 11.5}, {"w": "a", "s": 11.6, "e": 11.7}, {"w": "senha", "s": 11.8, "e": 12.1}]
    assert revisao.segunda_conferencia(blocos, hip) == ([], [])


def test_segunda_conferencia_acusa_quando_duas_palavras_batem():
    blocos = [_bloco("GRITEI ASSIM", 300)]
    hip = [{"w": "gritei", "s": 10.4, "e": 10.6}, {"w": "assim", "s": 10.7, "e": 10.9}]
    erros, avisos = revisao.segunda_conferencia(blocos, hip)
    assert len(erros) == 1 and "400 ms" in erros[0] and avisos == []


def _conferencia(desvios):
    """Um bloco de 2 palavras por desvio (s); a voz do vídeo pronto fica `desvio` antes da legenda."""
    blocos, hip = [], []
    for i, d in enumerate(desvios):
        f0 = 30 + i * 45
        blocos.append(_bloco(f"PALAVRA{i} OUTRA{i}", f0))
        hip += [{"w": f"palavra{i}", "s": f0 / 30 - d, "e": f0 / 30 - d + 0.3},
                {"w": f"outra{i}", "s": f0 / 30 - d + 0.35, "e": f0 / 30 - d + 0.7}]
    return revisao.segunda_conferencia(blocos, hip)


def test_segunda_conferencia_casos_isolados_viram_aviso():
    erros, avisos = _conferencia([0.02] * 10 + [0.5, -0.9])
    assert erros == []
    assert len(avisos) == 2 and all("pode ser alarme falso do Whisper" in a for a in avisos)


def test_segunda_conferencia_no_maximo_5_avisos():
    erros, avisos = _conferencia([0.0] * 20 + [0.4] * 6)
    assert erros == [] and len(avisos) == 5


def test_segunda_conferencia_legenda_inteira_deslocada():
    erros, _ = _conferencia([0.3] * 8)
    assert len(erros) == 1 and "legenda inteira deslocada 300 ms" in erros[0]


def test_segunda_conferencia_muitos_blocos_fora_reprova():
    erros, _ = _conferencia([0.0] * 6 + [0.5] * 4)  # 40% fora, mediana no lugar
    assert len(erros) == 1 and "4 de 10" in erros[0]
