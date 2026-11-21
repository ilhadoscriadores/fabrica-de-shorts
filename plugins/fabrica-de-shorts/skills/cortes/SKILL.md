---
name: cortes
description: Faz um corte de podcast (Short, TikTok, Reels) de ponta a ponta com a Fábrica de Shorts — minera os virais do nicho, acha o episódio original, baixa só o trecho, edita em 9:16, revisa sozinho e entrega com capa e texto de postagem. Use quando pedirem um corte, um Short, "o próximo corte", "missão automática" ou quando mandarem feedback de um corte ("assisti, achei X").
argument-hint: "[link de um corte viral] [quantos cortes]"
allowed-tools:
  - Bash(.venv/Scripts/python.exe:*)
  - Bash(.venv/bin/python:*)
  - PowerShell(.venv/Scripts/python.exe:*)
  - PowerShell(& .venv/Scripts/python.exe:*)
---

# Fábrica de Shorts · cortes

**Caminhos:** PLUGIN = `${CLAUDE_PLUGIN_ROOT}` (vazio? dois níveis acima do "Base directory" desta skill). PY = `.venv/Scripts/python.exe` (Windows) ou `.venv/bin/python` (Mac). FAB = `PY "PLUGIN/scripts/fabrica.py"`. Todo comando termina com `RESULTADO: {json}`; `"ok": false` → leia o `erro`, corrija e rode de novo.

## Antes de tudo
- Sem `canal.json` aqui → mande rodar /fabrica-de-shorts:comecar.
- Leia o `canal.json` e o `GUIA-DE-EDICAO.md` inteiros. O GUIA manda no estilo.
- **Um corte por contexto limpo.** Se esta conversa já fez um corte, ou pediram vários, rode cada corte num subagente (ferramenta Agent) com: "Siga a skill fabrica-de-shorts:cortes em modo automático na pasta <pasta>. Responda só com o resumo final." Repasse só o resumo.
- **Modo:** `estilo_aprovado: false` → 1º corte, com aprovação do estilo. `true` → missão automática: não pergunte nada, decida e siga até o fim.
- **Economize:** nunca leia arquivo grande (vtt, palavras.json, a planilha inteira, dados.json). Os comandos já resumem.

## Regras fixas
- Nunca prejudicar a imagem das pessoas: nada de tirar fala do contexto, humilhar ou expor alguém. Na dúvida, escolha outro corte.
- Sempre o crédito do podcast e o link do episódio na descrição. A autorização para cortar é pesquisa do usuário.
- Não poste nada. Não apague brutos. O render nunca sobrescreve (gera `final_v2.mp4`...).

## Passos
1. **Minerar:** `FAB minerar` (pule se mandaram o link do corte). Escolha um corte: história com virada, 60–90 s, de preferência `novo` e nunca `FEITO`; diga em 3 linhas por quê. No 1º corte, mostre 2 ou 3 opções e deixe escolher.
2. **Origem:** `FAB achar <url do corte> --busca "<convidado ou podcast>"`. Confira o episódio e as `regioes` (onde a fala aparece). Não achou? Leia `referencias/achar-origem.md`.
3. **Pasta:** `FAB novo-corte "<nome curto>"` → CORTE (cronômetro desde o minerar).
4. **Baixar:** `FAB baixar <url do episódio> <início> <fim> --corte CORTE` cobrindo as regiões (até ~6 min).
5. **Transcrever:** `FAB transcrever --corte CORTE`; leia `CORTE/transcricao.txt`.
6. **Plano:** escreva `CORTE/corte.json` seguindo `referencias/plano-do-corte.md` (trechos no tempo do bruto, começa no gancho, termina na virada, 60–90 s; corrija nomes e gírias que o Whisper errou).
7. **Base:** `FAB base CORTE` → leia `CORTE/timeline.txt` (tempos do corte final).
8. **Só no 1º corte:** ache 4 referências de edição com muita view (2 do nicho + 2 de fora do nicho ou do país; `FAB buscar "<termo>"`), link + 1 linha do que copiar (legenda, ritmo, zoom, efeitos, capa), junto com os canais admirados. Proponha cor, legenda e efeitos e **espere o OK**. Grave o que ficou no `canal.json` e no GUIA e marque `estilo_aprovado: true`. Ofereça o espelhar (desligado).
9. **Edição:** complete `edicao` e `postagem` no corte.json (`FAB biblioteca` mostra efeitos e trilhas e marca os usados nos últimos cortes: varie). Imagens: escreva `CORTE/imagens/prompts.txt` (`nome|cena`, sem pessoa real, sem texto) e rode `FAB imagens --corte CORTE`; as que faltarem ficam fora e o FALTANDO.md explica.
10. **Render + revisão:** `FAB render CORTE` (já revisa: `revisao.md`). Reprovou? Veja a seção "Quando a revisão reprova" em `referencias/plano-do-corte.md`, corrija e rode de novo, no máximo 2 vezes. Ainda reprovado? Entregue dizendo o que ficou.
11. **Capa e tempo:** `FAB capa --corte CORTE --frase "<3 a 6 palavras fortes>"` e `FAB tempo fim --corte CORTE`.
12. **Texto:** `FAB postagem --corte CORTE` (por último: leva o tempo final).
13. **Mensagem final, curta:** caminho do vídeo, título, origem (corte modelado + views + episódio + minutos), tempo total e o que a revisão achou. No 1º corte, 1 linha lembrando do selo (opção de divulgar a Fábrica).

## Feedback do usuário
"Assisti, achei X": corrija (corte.json ou canal.json) e rode `FAB render CORTE` (sai uma versão nova). Mudou trecho, correção ou censura → `FAB base CORTE` e depois `FAB render CORTE` (sem o base, o render recusa). Escreva a regra no fim do GUIA-DE-EDICAO.md (`- (dd/mm) ...`), para valer nos próximos cortes.
