# O corte.json

Um arquivo por corte, em `cortes/NNN-nome/corte.json`. Escreva em duas etapas: o **plano** (antes do `base`) e a **edição** e a **postagem** (depois, olhando o `timeline.txt`).

## 1. Plano (tempos no bruto.mp4, os do transcricao.txt)
```json
{
  "modelo": {"url": "https://www.youtube.com/shorts/XXXXXXXXXXX", "titulo": "SARGENTO CONTA O DIA EM QUE A VIATURA FICOU SEM FREIO", "canal": "Cortes Exemplo", "views": 1250000},
  "origem": {"url": "https://www.youtube.com/watch?v=XXXXXXXXXXX", "podcast": "Podcast Exemplo #100", "convidado": "Sgt. Fulano"},
  "trechos": [[20.8, 61.9], [228.4, 241.4], [246.5, 301.9]],
  "pausa_max": 0.35,
  "correcoes": [{"t": 51.8, "de": "beltrão", "para": "Beltrano."}, {"t": 240.8, "de": "cap", "para": "QAP"}],
  "censurar": [{"t": 255.7, "palavra": "droga"}]
}
```
- **trechos:** em ordem; pode juntar 2 a 4 pedaços do mesmo episódio. O primeiro já começa forte (o gancho); o último termina na virada ou na frase de efeito. Total de 60 a 90 s depois de tirar as pausas. Cada linha do `transcricao.txt` é `[início–fim] frase`: o trecho começa no início de uma frase e termina no fim de outra.
- **pausa_max:** pausas maiores que isso são encurtadas (0.35 é o padrão).
- **correcoes:** `t` é o segundo aproximado (±1,5 s) e `de` é a palavra errada como o Whisper escreveu (pode ter várias palavras). `para` vazio apaga a palavra; com espaço, vira várias.
- **censurar:** palavrões comuns já são cortados sozinhos (`opcoes.censurar_palavroes`). Aqui vão os extras.
- Opcionais: `"espelhar": true` (só neste corte) e `"revisao": {"ignorar": [[a, b]]}` para um trecho preto ou parado de propósito.

## 2. Edição (tempos do corte final, os do timeline.txt)
```json
"edicao": {
  "clima": "tensao",
  "cor": "#ff3b3b",
  "gancho": {"texto": "A VIATURA FICOU SEM FREIO", "emoji": "😨", "ate": 3.2},
  "credito": "Sgt. Fulano • Podcast Exemplo #100",
  "destaques": ["FREIO", "LADEIRA", "VIATURA"],
  "imagens": [
    {"arquivo": "01_ladeira.png", "s": 3.2, "e": 7.7, "entrada": "flash", "movimento": "in-right", "tremidas": [3.4]},
    {"arquivo": "02_jornal.png", "s": 28.7, "e": 33.6, "entrada": "zoom", "movimento": "out", "carimbo": "1998", "sepia": true}
  ],
  "etiquetas": [{"s": 63.3, "e": 66.6, "texto": "QAP = NA ESCUTA (RÁDIO)", "emoji": "⚠️"}],
  "efeitos": [{"t": 0.0, "arquivo": "impacto/boom-curto.mp3", "vol": 0.45}, {"t": 82.4, "arquivo": "suspense/riser-pulsando.mp3", "vol": 0.4}],
  "trilha": {"arquivo": "tensao/mixkit-epical-drums-02.mp3"},
  "selo": {"inicio": 23.6, "lado": "esq"}
}
```
- **gancho:** frase curta em maiúsculas que resume a história, na tela de 0 até `ate` (3 s).
- **crédito:** quem fala + podcast, aparece nos primeiros 4,6 s.
- **destaques:** palavras-chave que ficam sempre na cor.
- **imagens:** 3 a 5 s cada, entrando na palavra que a pessoa fala, uma a cada 8–12 s, nunca no gancho. `entrada`: zoom, flash, slide-esq, slide-dir. `movimento`: in-left, in-right, out, up. Extras: `tremidas` (segundos), `carimbo` (texto grande), `sepia`, `sirene`. Cada entrada ganha um whoosh sozinha.
- **etiquetas:** só para explicar (gíria, número, sigla). Poucas. `top` opcional (padrão 300, acima da cabeça).
- **efeitos:** `arquivo` relativo a `biblioteca/efeitos`. Impacto na virada, suspense antes da revelação, comédia no engraçado. Nunca em cima de palavra importante. Troque os do corte anterior.
- **trilha:** relativo a `biblioteca/trilhas`, no clima do corte. A Fábrica faz o loop, deixa baixinha e abaixa quando a pessoa fala. Sem trilha na biblioteca, o corte sai sem.
- **selo:** só vale com `opcoes.selo: true` no canal.json; entra num trecho calmo, nunca no fim (`inicio` em segundos do corte; `lado`: esq ou dir; `cor` opcional, `#rrggbb`).

## 3. Postagem
```json
"postagem": {
  "titulo": "A viatura ficou SEM FREIO no meio da ladeira 😨",
  "legenda_tiktok": "Ele pisou no freio e nada aconteceu 😨 O que você faria?",
  "descricao": "Sgt. Fulano conta o dia em que a viatura perdeu o freio numa ladeira.",
  "hashtags": ["#policia", "#podcast", "#cortes", "#historia"]
}
```
Título curto com 1 palavra quente. O `FAB postagem` junta o crédito do podcast, o link do vídeo original com o minuto, o aviso de imagem por IA, o crédito da música quando a licença pede, a duração e a origem.

## 4. Quando a revisão reprova
- **"sem voz nos 300 ms"**: a palavra caiu em silêncio (o Whisper inventou ou esticou). Apague com uma correção `"para": ""` ou divida o trecho para tirar o silêncio.
- **"X ms ANTES/DEPOIS da voz"**: corrija a palavra. Se sobrar 1 ou 2 blocos depois de 1 correção, entregue: o relatório registra.
- **"legenda/etiqueta em cima do rosto"**: mude o `top` da etiqueta ou o trecho.
- **Mudou trecho, correção ou censura?** Os tempos do corte final mudam: rode `FAB base CORTE` e releia o `timeline.txt` antes de ajustar os tempos da edição (imagens, etiquetas, efeitos).
- Avisos da 2ª conferência não reprovam.
