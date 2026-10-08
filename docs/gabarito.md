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

Predicados (ontologia 1.1, ver `docs/ontologia.md`): `participa_de`, `ocorre_em`, `localizado_em`, `parte_de`, `concede`, `obtido_em`, `gera`, `membro_de`, `relacionado_a` (com `rotulo` opcional, como aliado ou inimigo). Se a ontologia mudar, ajuste os arquivos já anotados com busca e substituição e rode a validação.

## Regras de anotação
1. **Só o que está explícito na tela** (legenda, título de missão, nome em item, mapa). Não anote o que você sabe por ter jogado. Isso mede a extração de forma justa e preserva a ideia de memória sem spoiler.
2. **Vocabulário fechado:** só os tipos e predicados da ontologia. Se faltar um, anote em `observacoes` e revise a ontologia.
3. **Nome canônico:** cada entidade tem um nome único, com aliases, em `data/gabarito/entidades.json` (ex.: "Geralt of Rivia", aliases "Geralt", "White Wolf"). No gabarito, use sempre o nome canônico. Na avaliação, a previsão com "Geralt" é aceita pelo alias.
4. **Um idioma só** para os nomes: português do Brasil, o idioma do jogo usado no projeto (os arquivos em `exemplo/` estão em inglês só para demonstração).
5. **Ignore ruído:** barras de vida, ícones e textos decorativos sem entidade.
6. **Vídeo:** anote o clipe inteiro, não quadro a quadro. Se ajudar, anote o instante em `evidencia` (ex.: "0:12 legenda ...").
7. **Relação só se a tela a mostra.** Se dois personagens aparecem juntos mas nada diz que são aliados, não anote `aliado_de`.
8. **Nome igual para tipos diferentes:** `entidades.json` resolve nomes sem olhar o tipo, então o mesmo nome não pode ser local e missão. A missão inicial do jogo se chama "Kaer Morhen", como a fortaleza: a missão leva o sufixo, "Kaer Morhen (missão)".
9. **Personagem sem nome na tela não se anota**, mesmo que você o reconheça (o rosto de Geralt, Vesemir ou Ciri em cutscene). Vale o nome escrito: rótulo da legenda ("Geralt: ..."), objetivo ("Siga o Vesemir"), lista do glossário ou texto da entrada.
10. **Menção conta:** um nome próprio citado em legenda, objetivo ou texto de entrada é entidade, mesmo que o personagem não apareça. Relações só entram quando o texto as afirma.
11. **Decisão:** anota-se só a opção escolhida, deduzida da fala seguinte; as outras opções ficam em `observacoes`. O nome da decisão é o texto da opção.
12. **Fora de escopo (ver ontologia):** Gwent e cartas, categorias do bestiário e rótulos de espaços do inventário.
13. **HUD:** o título amarelo do HUD de missão é o nome da missão, e o texto abaixo é o objetivo.
14. **Facção (ontologia 1.1):** anota-se como `faccao` o grupo com nome escrito na tela (Nilfgaard, Caçada Selvagem, Exército Imperial, Escola do Lobo). `membro_de` só quando o texto afirma que o personagem pertence ao grupo; "comandante das tropas de Nilfgaard" sem nome do comandante não gera relação. Relações entre facções não se anotam.

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

## Gabarito do subconjunto (anotado e verificado em 2026-10-07)
Rascunho feito por Claude a partir das imagens e dos clipes, **verificado pelo autor em 2026-10-07 (gabarito confirmado como correto, com 5 itens já revisados)**. Os 24 arquivos estão em `data/gabarito/` e passam em `python scripts/validar_gabarito.py` (0 problemas). Total: 85 entidades e 24 relações; `entidades.json` tem 32 nomes canônicos em pt-BR.

| Tipo de tela | Itens |
|---|---|
| Diálogo com legenda (e HUD de missão) | `img_004`, `img_016`, `img_018`, `img_021`, `img_042`, `img_048`, `vid_014` |
| Exploração / HUD | `img_005`, `img_019`, `vid_023` |
| Glossário | `img_010`, `img_011`, `img_012`, `img_022` |
| Diário de missões | `img_009`, `img_047`, `img_054` |
| Mapa | `img_008`, `img_053` |
| Item e inventário | `img_045`, `img_055` |
| Cutscene (sem entidades de propósito) | `img_024` |
| Escolhas de diálogo | `vid_008`, `vid_025` |

As dúvidas abaixo foram resolvidas na verificação (as regras 8 a 13 ficam como estão); permanecem aqui como registro das escolhas e ficam também em `observacoes` de cada JSON:
1. **Regra 9 (nome na tela):** é a decisão que mais pesa. Com ela, cenas em que só o rosto identifica o personagem (`img_018`, `img_005`, os clipes) rendem poucas entidades. Se preferir contar o personagem reconhecível, muda o gabarito de vários itens.
2. **Missão com nome de local:** "Kaer Morhen (missão)" (regra 8) em `img_004`, `img_005`, `img_008`, `img_009`, `img_016`.
3. **Relações inferidas:** `img_008` (missão ocorre_em Kaer Morhen), `vid_023` (Peter Saar Gwynleve localizado_em Guarnição Nilfgaardiana) e `img_054` (Grifo participa_de O Monstro de Pomar Branco). As demais vêm de texto ou objetivo explícito.
4. **Rótulos pequenos:** em `img_053` (mapa), os marcadores Moinho, Ponte da Canção do Desalento e Travessia de rio foram lidos em miniatura; confira a grafia na imagem original.
5. **Tempos dos clipes:** vêm de quadros a cada 2 s e são aproximados (±2 s).
6. **Decisões de clipe:** a opção escolhida foi deduzida da fala seguinte; nenhum quadro mostra o botão sendo apertado.
7. **`img_016`:** é tela de tutorial com legenda e HUD; foi classificada como diálogo.
8. **Cobertura:** não há escolhas em screenshot (só nos clipes), item e mapa têm 2 imagens cada e o `img_024` é um controle sem entidades.

## Ampliação do gabarito (2026-10-07, rascunho a verificar)
Para alimentar o grafo e testar mais tipos de tela, foram anotados 28 itens do material novo, seguindo as regras 1 a 13. São **rascunho de IA e não foram verificados pelo autor**; os 24 itens anteriores continuam verificados. A relação "Odolan concede Contrato: O Demônio do Poço" (`img_073`) e as de mapa (`img_094`) são inferidas, e os contratos de quadro de avisos foram anotados como `missao` com `estado: disponivel`.

| Tipo de tela | Itens |
|---|---|
| Glossário de personagens | `img_057` a `img_063` |
| Bestiário | `img_076`, `img_077` |
| Quadro de avisos (`tipo_tela: outro`) | `img_070`, `img_072`, `img_073`, `img_074`, `img_075` |
| Item, inventário e cartas | `img_064`, `img_065`, `img_066`, `img_079`, `img_081`, `img_082`, `img_083` |
| Escolhas de diálogo (quadros de clipe) | `img_084`, `img_085`, `img_086` |
| Diário | `img_088` |
| Mapa | `img_092`, `img_094` |
| Cutscene | `img_096` |

Total do gabarito: 63 arquivos (com `img_080`, `img_071` e 9 clipes novos), 232 entidades, 44 relações, 60 nomes canônicos em `entidades.json`; `validar_gabarito.py` com 0 problemas. Facções reanotadas em 11 itens (ontologia 1.1, regra 14).

`img_080_exploracao` (2026-10-08, rascunho a verificar): tela de missão completada com recompensas; é o único item que exercita `obtido_em` e `estado: concluida`. Total: 53 arquivos, 190 entidades, 37 relações.

**Clipes novos (2026-10-08, rascunho a verificar):** `vid_029` (mapa), `vid_030`, `vid_031`, `vid_032`, `vid_033`, `vid_037` (diálogo), `vid_034` (diário), `vid_035` (diálogo sem entidade nomeada, controle) e `vid_036` (missão atualizada). Atenção: em `vid_033` Geralt aparece sem nome escrito, o que viola a regra 9 se aplicada à risca; está marcado nas observações.
O roteiro de verificação por sorteio está em `docs/verificacao-gabarito.md`.

## Relatório da avaliação (eval/avaliar.py)
Além do total (micro, sem elementos em reserva), o avaliador imprime a quebra por tipo de entidade, por predicado e por tipo de tela, com a média simples entre tipos, e relata `evento` e `gera` à parte. `--csv-quebras arquivo.csv` grava as quebras e `--sem-quebras` imprime só o total. Sempre reporte o micro junto com a média simples: o glossário tem muitas anotações repetidas de personagem e domina o micro.
