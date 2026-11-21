# Teste de aceitação · Fábrica de Shorts v1.0

**Data:** 21/11/2026, das 05h52 às 07h39.
**Máquina:** Windows 10, Ryzen 5 4600G, GTX 1060 6 GB. O driver é antigo para o NVENC, então o vídeo saiu pelo processador (libx264).
**Modelo:** Claude Opus 5.5, plano Max (R$ 550/mês).

## Como foi feito
1. **Pasta vazia** (`Shorts automático`), com o plugin instalado pelo marketplace (`claude plugin marketplace add` + `claude plugin install`, escopo local).
2. **Setup:** `/fabrica-de-shorts:comecar`, já com as respostas no pedido (nicho podcast policial, @, canais admirados). Ele criou o venv novo e o editor recém-copiado (`npm install`), instalou o pacote da placa e baixou o kit Mixkit.
3. **Estilo marcado como aprovado.** A aprovação do estilo no 1º corte é do dono do canal, por isso ficou de fora do teste.
4. **Missão automática:** `/fabrica-de-shorts:cortes`, sem nenhuma conversa, cada rodada num contexto novo. A revisão automática achou defeitos na 1ª rodada; o plugin foi corrigido e a missão rodou de novo.

Cada etapa rodou num **subagente de contexto limpo** que lia a skill instalada. O custo vem da soma dos tokens do registro (JSONL) de cada subagente, a preço de API do Opus 5.5:
- US$ 4/M de entrada;
- US$ 20/M de saída;
- US$ 0,20/M de leitura de cache;
- US$ 8/M de gravação de cache.

O `claude -p --output-format json` não deu para usar: o login do Claude de terminal desta máquina estava vencido.

## Resultados

| | Rodada | Tempo | Chamadas | Tokens (saída / cache lido / cache gravado) | US$ (API) | % da semana do Max* | R$ no Max* |
|---|---|---|---|---|---|---|---|
| Setup (`comecar`) | única | 7 min | 24 | 11,7 mil / 1,78 M / 51 mil | 1,00 | ~0,07% | ~R$ 0,09 |
| Corte automático | 1ª (com defeitos) | 53 min 24 s | 95 | 98 mil / 14,4 M / 217 mil | 6,59 | ~0,44% | ~R$ 0,56 |
| **Corte automático** | **2ª (corrigida)** | **21 min 21 s** (11 min 41 s de máquina) | **52** | 51 mil / 5,83 M / 116 mil | **3,11** | **~0,21%** | **~R$ 0,27** |

\* A conversão usa a relação medida na página de Uso: 1% da semana do Max ≈ US$ 15. Em reais, R$ 550 ÷ 4,33 semanas ≈ R$ 127 por semana.
- **Na página de Uso:** a semana andou 23% → 26% na 1ª rodada e 26% → 27% na 2ª. A janela de 5 h andou 16% → 39% e 42% → 44%.
- **Os números da página de Uso estão inflados:** foram medidos com outras sessões do Claude rodando ao mesmo tempo. Por isso o número principal é o dos tokens de cada missão.
- **Referência:** o corte 002 do BO 24 Horas (vídeo BPP 7) custou US$ 4,96, ≈0,33% da semana. A meta do desenho era 0,10–0,13%: a 2ª rodada ficou em ~0,21%, 37% mais barata que a referência, mas ainda acima da meta.

**Estimativa para o Pro** (limite ~5 vezes menor que o Max 5x):
- ~1% da semana por corte;
- ~12 cortes por janela de 5 h;
- o preço por corte fica parecido (~R$ 0,27).

## Os cortes
- **1ª rodada:** Fala Glauber #241 (Sgt. Nei, o Batata), 75 s.
  - O 1º episódio escolhido não teve legenda (o YouTube devolveu legenda vazia) e foi trocado.
  - A v1 reprovou: 2 legendas sem voz, 1 adiantada e uma etiqueta em cima do rosto. O Claude corrigiu.
  - A v2 reprovou só na 2ª conferência, que se mostrou instável: o áudio estava alinhado e um Whisper maior apontava outros blocos.
- **2ª rodada:** Cap. Hércules, policial do BOPE sequestrado (Fala Glauber #144), 81 s, 7 imagens do Codex.
  - A v1 reprovou: uma palavra "Ó" com duração zero ficou sem voz. O Claude apagou a palavra com uma correção.
  - A v2 foi aprovada, com 0 erros e 5 avisos isolados da 2ª conferência.
  - −14,2 LUFS, legenda nunca em cima do rosto, capa e POSTAGEM.txt prontos.

## Defeitos que a revisão e o teste acharam, e o que mudou

| Defeito | Correção |
|---|---|
| O YouTube devolvia legenda vazia (HTTP 200), que contava como sucesso e ficava em cache | Legenda sem fala conta como inexistente, com nova tentativa em 5 s e 15 s e aviso claro |
| `baixar` falhava às vezes (ffmpeg) e mostrava o traceback | Nova tentativa automática; mensagem curta |
| Palavra "fantasma" no fim do pedaço (arredondamento do quadro) | O fim do pedaço não passa do começo da palavra seguinte |
| O Whisper esticava palavras por cima de ~1 s de silêncio (legenda "sem voz") | A base corta também os silêncios medidos no áudio, não só as pausas entre palavras |
| A 2ª conferência (Whisper no vídeo com música) reprovava blocos ao acaso | Agora reprova só deslocamento geral; casos isolados viram aviso |
| O `minerar` escondia os vídeos recentes | Mostra uma seção "Recentes (novo)" |
| O cronômetro não contava a mineração | O tempo começa no `minerar` |
| O link do episódio caía ~50 s antes do trecho | Aponta para o começo do 1º trecho |
| As legendas `.txt` vinham com `&nbsp;` | Entidades HTML decodificadas |
| A skill não dizia o que fazer quando a revisão reprova | Seção "Quando a revisão reprova" no `plano-do-corte.md` |
| A skill `comecar` não perguntava o nome nem explicava o NVENC desligado | Pergunta o nome; mostra o motivo e manda atualizar o driver |

## Defeitos da 2ª rodada (corrigidos antes da publicação)
- O `achar` mandava usar um parâmetro que não existe quando o episódio não tinha legenda.
- O `achar` não usava o link do vídeo completo que vem na descrição do Short.
- A postagem rotulava errado o vídeo original (agora: "Vídeo original: título · link").
- O `transcricao.txt` não mostrava onde cada frase termina (agora `[início–fim] frase`).
- Palavrinhas ("na", "e", "o") sumiam da legenda quando o Whisper as esticava por cima de um silêncio.
- A skill não avisava que mudar o plano muda os tempos da edição.
- O relatório da revisão se contradizia: aprovava com avisos e dizia "sem deslocamento".

## Revisão final (antes de publicar)
- O detector de rosto quebrava com acento no caminho (ex.: `C:\Users\João`): o modelo agora é lido pelo buffer.
- FFmpeg, Node e npm instalados pelo winget só eram achados reabrindo o Claude Code: a Fábrica procura nas pastas do winget e do Node, e o winget roda sem perguntas.
- O feedback que mudava trecho, correção ou censura gerava uma versão igual: o render recusa e pede o `base` antes.
- O `editor/public/` crescia a cada corte (o Remotion copia tudo a cada render): a pasta do corte sai depois do render.
- Pedido de permissão a cada comando: as skills liberam só o Python do `.venv`.
- A imagem do README mostrava o QR code de doação do podcast: borrado, e as legendas ANTES e DEPOIS ficaram embaixo de cada imagem.
- O exemplo do `corte.json` usava uma pessoa real e uma palavra ofensiva: trocado por dados fictícios.
- Dependências sem teto de versão: teto na próxima versão maior (menos o yt-dlp).
- O selo não era conferido nem testado de ponta a ponta: o `corte.json` é conferido, a revisão roda antes do selo e há um teste do render com selo.
- Nomes reais nos testes: trocados por fictícios.
- Python 3.15 recém-lançado pode não ter os pacotes prontos: a skill instala o 3.12 e o `ambiente` avisa.

## Ficam para a v1.1
- **Anúncio do vídeo original** (selo de patrocinador no canto, em plano aberto): a revisão ainda não detecta, e o `corte.json` não tem como recortar ou borrar uma área.
- **macOS:** experimental, sem teste do zero.
- **NVENC:** com o driver 581 da GTX 1060, o ffmpeg 9 não abre o NVENC; o vídeo sai pelo processador. Atualizar o driver deve resolver.
