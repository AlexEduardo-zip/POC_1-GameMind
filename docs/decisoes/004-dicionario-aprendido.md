# Decisão 004 · O dicionário de nomes é aprendido, não escrito à mão

- Data: 2026-10-10
- **Decisão: o aplicativo não depende de nenhuma lista de nomes pronta. O dicionário do jogo é aprendido do texto lido nas capturas (`src/gamemind/nucleo/dicionario.py`), e a IA, quando ligada, o amplia.**

## Contexto
O estudo de viabilidade usou uma lista de nomes de um jogo escrita à mão. Servia para medir o método, mas um aplicativo que exige uma lista por jogo não escala, e a lista não era estritamente cega ao gabarito (`docs/estudo-viabilidade.md`).

## O que mudou
- O dicionário é refeito a cada rodada com o texto de todas as mídias do jogo e fica em `jogos/<jogo>/dicionario.json`. Um `dicionario_manual.json` opcional é somado, mas nunca é necessário.
- **Indícios usados:** quem aparece antes de dois-pontos numa legenda (personagem), o contexto ("para X", "tropas de X", "Fale com X"), palavras que indicam o tipo ("Escola", "Cavaleiros", "Ponte") e repetição em duas ou mais mídias. Uma palavra é nome próprio se aparece com inicial maiúscula e nunca em minúsculas no resto do texto. Sem indício suficiente de tipo, o nome não entra. Nenhum texto de interface de um jogo é usado.
- **Apelidos:** "Aldric" e "Aldric Voss" se unem pelo prefixo; a forma vista em mais mídias é o nome.
- **Com IA:** os nomes que o LLM acha (e a validação aceita) em duas ou mais mídias entram no dicionário e passam a ser reconhecidos nas outras capturas. Nomes de criaturas em minúsculas ("lobo") passam a valer quando o LLM os propõe e estão no texto.

## Consequências
- O app funciona em qualquer jogo sem lista pronta.
- Sem IA, o aprendizado perde para a lista escrita à mão sobretudo em **criaturas** (aparecem em minúsculas e nada no texto indica o tipo) e em personagens que só aparecem em listas.
- Com a IA local, o aprendizado recupera quase tudo, e a IA ainda ensina nomes ao dicionário.
- As regras de aprendizado foram ajustadas olhando o mesmo material usado para medir; falta medir em telas novas e em outro jogo.
