---
name: revisar
description: Revisão automática de um vídeo da Fábrica de Shorts (ou de qualquer vídeo) — áudio e vídeo do mesmo tamanho, volume −14 LUFS, pico, quadro preto ou congelado e, num corte da fábrica, legenda fora da voz, legenda em cima do rosto, rosto cortado e palavrão com som. Use quando pedirem para revisar, conferir ou checar um vídeo antes de postar.
argument-hint: "[caminho do vídeo ou da pasta do corte]"
---

# Fábrica de Shorts · revisar

**Caminhos:** PLUGIN = `${CLAUDE_PLUGIN_ROOT}` (vazio? dois níveis acima do "Base directory" desta skill). PY = `.venv/Scripts/python.exe` (Windows) ou `.venv/bin/python` (Mac); sem `.venv` aqui, use o python que tiver os pacotes de `PLUGIN/scripts/requirements.txt`. FAB = `PY "PLUGIN/scripts/fabrica.py"`.

1. Vídeo de um corte da fábrica (`cortes/NNN-nome/final_vN.mp4`): `FAB revisar <vídeo> --corte <pasta do corte>`. Qualquer outro vídeo: `FAB revisar <vídeo>` (confere só som e imagem).
2. Leia o `revisao.md` gerado e explique em poucas linhas: o que reprovou (com o segundo do vídeo), os avisos e o que passou.
3. Se o vídeo é da fábrica e o usuário quiser corrigir: ajuste o `corte.json` e rode `FAB render <pasta do corte>` (mudou trecho, correção ou censura? `FAB base <pasta do corte>` antes) (gera uma versão nova; nunca sobrescreve).
