# Gabarito (ground truth)

## O que é e para que serve
O gabarito é a **resposta certa feita por você**, à mão, para um subconjunto do conjunto de teste: para cada screenshot ou clipe, a lista de entidades e relações que um sistema perfeito extrairia. Depois, o programa `eval/avaliar.py` compara a saída do GameMind com ele e calcula precisão, revocação e F1. Sem gabarito não há como dizer qual estratégia (screenshot, vídeo, combinação) ou qual IA (local, pública) é melhor.

```
screenshot/clipe ──► GameMind ──► previsão (JSON) ─┐
                                                    ├─► avaliar.py ─► precisão, revocação, F1
screenshot/clipe ──► você, à mão ─► gabarito (JSON) ┘
```

## O que anotar em cada item
Um arquivo JSON por screenshot ou clipe, com o mesmo nome do arquivo de mídia (`img_001_dialogo.png` → `img_001_dialogo.json`):

- **Entidades:** nome, tipo (personagem, criatura, local, missão, item, evento, decisão) e a evidência (trecho visível na tela).
- **Relações:** sujeito, predicado (lista fechada, ver abaixo), objeto e evidência.
- **tipo_tela** e **observações** (opcional).

O formato está em `src/schema.py` (é o mesmo que a extração vai produzir depois). Exemplo em `data/gabarito/exemplo/exemplo_img.json`.

Predicados (ontologia v0.1, ver `docs/ontologia.md`): `participa_de`, `ocorre_em`, `localizado_em`, `parte_de`, `concede`, `obtido_em`, `gera`, `relacionado_a` (com `rotulo` opcional, como aliado ou inimigo). Se a ontologia mudar, ajuste os arquivos já anotados com busca e substituição e rode a validação.

## Regras de anotação
1. **Só o que está explícito na tela** (legenda, título de missão, nome em item, mapa). Não anote o que você sabe por ter jogado. Isso mede a extração de forma justa e preserva a ideia de memória sem spoiler.
2. **Vocabulário fechado:** só os tipos e predicados da ontologia. Se faltar um, anote em `observacoes` e revise a ontologia.
3. **Nome canônico:** cada entidade tem um nome único, com aliases, em `data/gabarito/entidades.json` (ex.: "Geralt of Rivia", aliases "Geralt", "White Wolf"). No gabarito, use sempre o nome canônico. Na avaliação, a previsão com "Geralt" é aceita pelo alias.
4. **Um idioma só** para os nomes: português do Brasil, o idioma do jogo usado no projeto (os arquivos em `exemplo/` estão em inglês só para demonstração).
5. **Ignore ruído:** barras de vida, ícones e textos decorativos sem entidade.
6. **Vídeo:** anote o clipe inteiro, não quadro a quadro. Se ajudar, anote o instante em `evidencia` (ex.: "0:12 legenda ...").
7. **Relação só se a tela a mostra.** Se dois personagens aparecem juntos mas nada diz que são aliados, não anote `aliado_de`.

## Como a comparação funciona
- Uma entidade da previsão acerta se o **nome canônico** (após aliases, sem acento e sem maiúsculas) e o **tipo** coincidem com o gabarito. O modo brando (`--sem-tipo`) ignora o tipo.
- Uma relação acerta se sujeito, predicado e objeto coincidem.
- **Precisão** = acertos entre o que o sistema extraiu. **Revocação** = acertos entre o que deveria ter extraído. **F1** = média harmônica das duas.
- Os totais somam todos os itens (micro). Acompanhe também o tempo e a memória usada, que não vêm do gabarito.

## Quanto anotar
- **Subconjunto:** cerca de 20 screenshots e 3 a 4 clipes, escolhidos para cobrir todos os tipos de tela (diálogo, escolhas, diário, item, mapa, glossário, HUD, cutscene).
- **Tempo:** de 5 a 10 minutos por screenshot e de 15 a 20 por clipe. Total de 3 a 5 horas, em duas ou três sessões.
- O restante do conjunto serve para olhar a qualidade na prática, sem métrica.

## Passo a passo
1. Colete o material (ver `docs/semana2.md`) e escolha o subconjunto a anotar, com todos os tipos de tela.
2. Anote 5 itens e veja se as regras funcionam; ajuste as regras antes de continuar.
3. Crie e mantenha `data/gabarito/entidades.json` à medida que surgirem entidades novas.
4. Anote o restante do subconjunto.
5. Rode `python scripts/validar_gabarito.py` (formato, nomes, tipos e domínio e alcance dos predicados).
6. No dia seguinte, revise 5 itens sorteados sem olhar as anotações antigas e compare. Diferenças mostram regras ambíguas.
7. Faça commit. Quando a ontologia mudar, atualize os arquivos e rode a validação de novo.

## Armadilhas comuns
- Anotar o que você sabe do jogo, e não o que a tela mostra.
- Nomes diferentes para a mesma entidade, que viram "erro" falso na avaliação.
- Anotar demais em telas de HUD.
- Mudar as regras no meio do caminho sem reanotar os itens antigos.

## Testar o avaliador
```bash
python scripts/validar_gabarito.py data/gabarito/exemplo
python eval/avaliar.py --gab data/gabarito/exemplo --pred eval/exemplo_pred
```
Na avaliação real, as previsões ficam em `eval/predicoes/` (um JSON por item) e o comando é `python eval/avaliar.py`.
