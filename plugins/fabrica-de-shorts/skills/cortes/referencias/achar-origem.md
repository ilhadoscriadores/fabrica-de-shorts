# Achar o episódio original

Sempre corte do **episódio original**, nunca do corte de outro canal. O corte viral só prova que o assunto funciona.

1. `FAB achar <url do corte> --busca "<termo>"` baixa a legenda do corte, procura episódios longos com o termo e mostra onde a fala aparece em cada um (`regioes`, melhores primeiro, com `acertos` e `cobertura`). Link do YouTube na descrição do corte ("vídeo completo: ...") entra como 1º candidato.
   - Bom termo: nome do convidado + nome do podcast ("sargento fulano podcast exemplo"). Olhe o título, a descrição (`modelo.descricao`) e a legenda do corte: quase sempre o podcast aparece lá.
   - Já sabe o episódio? `FAB achar <url do corte> --candidatos <url1> <url2>`.
2. **Achou** quando a 1ª região tem muitos acertos (dezenas) e cobertura alta. Duas regiões fortes no mesmo episódio = o corte juntou dois trechos: baixe de antes da primeira até depois da segunda (até ~6 min) ou baixe em dois cortes de ensaio.
3. **Não achou:** tente outro termo (o apelido do convidado, o número do episódio, o nome do canal do podcast) ou `FAB buscar "<termo>" --longos` para ver os episódios e passar como `--candidatos`. Episódio sem legenda? Tente o vídeo do próprio canal do podcast ou `FAB legenda <url> --transcrever` (mais lento) e depois `FAB achar <url do corte> --candidatos <url>`.
4. **Corte de live (Twitch, Kick) ou do Instagram/TikTok:** a busca e a legenda são só do YouTube. Passe a VOD ou a página de vídeos do canal: `FAB achar <url do corte> --candidatos https://www.twitch.tv/<canal>/videos`. A Fábrica pega as 4 últimas lives, baixa só o som (~90 MB por hora) e compara com o som do corte (~1,5 min por live de 8 h). Achou = `"por": "audio"` com 2 ou 3 `acertos`. Vídeo do YouTube sem legenda: o mesmo com `--audio`. O `baixar` funciona com VOD da Twitch.
5. Depois de 3 tentativas sem achar, troque de corte na planilha.
