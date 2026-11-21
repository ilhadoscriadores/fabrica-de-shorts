---
name: comecar
description: Prepara o computador e a pasta para a Fábrica de Shorts (confere e instala Python, FFmpeg e Node, cria a pasta de trabalho, pergunta nicho, @ e canais de referência). Use na primeira vez, quando pedirem para instalar/configurar a Fábrica de Shorts, ou depois de atualizar o plugin.
argument-hint: "[nicho] [@ do canal] [canais que você admira]"
---

# Fábrica de Shorts · começar

Fale em português do dia a dia, curto, como para quem nunca abriu um terminal. Trabalhe só nesta pasta.

## Caminhos
- **PLUGIN** = `${CLAUDE_PLUGIN_ROOT}`. Se vier vazio, é a pasta dois níveis acima do "Base directory" desta skill.
- **PY** = `.venv/Scripts/python.exe` no Windows, `.venv/bin/python` no Mac.
- **FAB** = `PY "PLUGIN/scripts/fabrica.py"`. Todo comando termina com `RESULTADO: {json}`; se vier `"ok": false`, leia o `erro`, corrija e rode de novo.

## Passos
1. **Pasta.** Se a pasta tiver outras coisas (a `.claude/` da instalação não conta) e nenhum `canal.json`, pergunte se é aqui mesmo (o ideal é uma pasta nova, ex.: `Shorts automático`).
2. **Python 3.10+.** Confira (`python --version`, `py -3 --version` ou `python3 --version`). Faltando: Windows `winget install -e --id Python.Python.3.12 --source winget --accept-package-agreements --accept-source-agreements`, Mac `brew install python`. Instalou agora? Use o caminho completo do python novo.
3. **Ambiente próprio:** `<python> -m venv .venv` e depois `PY -m pip install -r "PLUGIN/scripts/requirements.txt"` (uns minutos).
4. **`FAB ambiente`.** Instale cada item de `faltando` com o comando que vem pronto (winget/brew) e diga numa linha o que instalou. Antes, avise: "o Windows pode abrir uma janela pedindo permissão; se depois de instalar o comando ainda não for achado, feche e abra o Claude Code de novo". Se `gpu` mostrar NVIDIA: `PY -m pip install -r "PLUGIN/scripts/requirements-gpu.txt"` (transcrição na placa, bem mais rápida) e `FAB ambiente` de novo para confirmar `whisper: placa (CUDA)`. Veio `nvenc_motivo`? Diga em 1 linha: "o vídeo sai pelo processador; atualizar o driver da NVIDIA deixa mais rápido".
5. **Perguntas** (pule o que já veio no pedido): o nicho, o nome e o @ do canal (sem nome, use o @ sem "@"), 2 ou 3 canais ou cortes que a pessoa admira (link ou nome) e o idioma (pt, en ou es; padrão pt).
6. **`FAB preparar --nome "<canal>" --arroba "<@>" --nicho "<nicho>" --idioma <pt|en|es>`** (cria pastas, biblioteca inicial, editor e GUIA; o `npm install` leva uns minutos). Depois edite o `canal.json`:
   - `termos_busca`: 8 buscas variadas do nicho, do jeito que as pessoas pesquisam no YouTube (ex. para podcast policial: "policial conta história podcast", "bope podcast corte", "delegado conta caso podcast");
   - `admirados`: os canais que a pessoa citou.
7. **Trilhas e efeitos.** Pergunte se pode baixar o kit grátis do Mixkit (26 trilhas por clima + 35 efeitos, ~140 MB, licença do Mixkit, sem crédito). Sim: `FAB baixar-kit`. Diga em 1 linha que dá para ampliar com Pixabay, Freesound (filtro CC0) e a Biblioteca de Áudio do YouTube, sempre anotando a licença em `biblioteca/LICENCAS.md`.
8. **Avisos, uma vez, em poucas linhas:**
   - **Selo** "Fábrica de Shorts · Ilha dos Criadores": vem desligado. Ligando (`opcoes.selo: true` no canal.json), cada corte sai em duas versões, com e sem a faixa que divulga a Fábrica.
   - **Espelhar** o vídeo: desligado (`opcoes.espelhar`).
   - **Custo:** cada corte automático leva ~20 min e usa ~0,2% da semana no plano Max (~1% no Pro), medido em 21/11; o 1º corte gasta mais, porque aprende o estilo.
   - **Convite** (só se `convite_mostrado` for false; depois marque true): "Quer receber as atualizações e os modos novos? Entre nos Avisos da Ilha: https://ilhadoscriadores.tech/comunidade/zap?o=plugin".
9. **Fim:** "Pronto! Para o primeiro corte, digite /fabrica-de-shorts:cortes".

## Plugin atualizado
`FAB estado` com `editor_desatualizado: true` → ofereça `FAB preparar --ressincronizar` (atualiza o editor e não mexe no canal.json nem no GUIA).
