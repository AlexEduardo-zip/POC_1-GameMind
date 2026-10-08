# Gabarito (ground truth)

## O que é
A **resposta certa feita à mão** para um subconjunto do conjunto de teste: para cada screenshot ou clipe, as entidades e relações que um sistema perfeito extrairia. `eval/avaliar.py` compara a saída do GameMind com ele e calcula precisão, revocação e F1.

```
screenshot/clipe ──► GameMind ──► previsão (JSON) ─┐
                                                    ├─► avaliar.py ─► precisão, revocação, F1
screenshot/clipe ──► anotação à mão ─► gabarito ────┘
```

## Formato
Um JSON por item, com o nome do arquivo de mídia (`img_004_dialogo.jpg` → `img_004_dialogo.json`): `entidades` (nome, tipo, `subtipo` e `estado` opcionais, evidência visível na tela), `relacoes` (sujeito, predicado, objeto, `rotulo` opcional, evidência), `tipo_tela` e `observacoes`. O esquema é `src/schema.py`, o mesmo que a extração produz; exemplo em `data/gabarito/exemplo/`. Nomes canônicos e aliases ficam em `data/gabarito/entidades.json`.

Tipos e predicados: ontologia 1.1 (`docs/ontologia.md`). Valide com `python scripts/validar_gabarito.py data/gabarito` (formato, nomes, tipos, domínio e alcance dos predicados).

## Regras de anotação
1. **Só o que está explícito na tela** (legenda, título de missão, nome em item, mapa). Não anote o que sabe por ter jogado.
2. **Vocabulário fechado:** só tipos e predicados da ontologia; se faltar um, registre em `observacoes`.
3. **Nome canônico** único por entidade (com aliases em `entidades.json`); na avaliação, "Geralt" vale por "Geralt de Rívia".
4. **Um idioma só:** português do Brasil (os arquivos de `exemplo/` estão em inglês só para demonstração).
5. **Ignore ruído:** barras de vida, ícones, textos decorativos.
6. **Vídeo:** anote o clipe inteiro, não quadro a quadro; o instante pode ir em `evidencia` ("0:12 legenda ...").
7. **Relação só se a tela a mostra.** Dois personagens juntos não são aliados sem que algo diga.
8. **Nome igual para tipos diferentes:** a chave é o nome, então a missão que tem o nome de um local leva sufixo: "Kaer Morhen (missão)".
9. **Personagem sem nome escrito não se anota,** mesmo reconhecido pelo rosto. Vale o nome na legenda ("Geralt: ..."), no objetivo ("Siga o Vesemir"), na lista ou no texto de glossário. (Exceção confirmada: `vid_033`.)
10. **Menção conta:** nome próprio citado em legenda, objetivo ou texto é entidade, mesmo que a pessoa não apareça.
11. **Decisão:** anota-se a opção escolhida, deduzida da fala seguinte; as outras ficam em `observacoes`. O nome é o texto da opção, sem reticências.
12. **Fora de escopo:** Gwent e cartas, categorias do bestiário, rótulos de espaços e equipamento em uso no inventário.
13. **HUD:** o título amarelo é o nome da missão; o texto abaixo é o objetivo.
14. **Facção:** `faccao` para o grupo com nome escrito (Nilfgaard, Caçada Selvagem, Exército Imperial, Escola do Lobo, Cavaleiros Negros). `membro_de` só se o texto afirma o pertencimento; relações entre facções não se anotam.

## Como a comparação funciona
- Entidade acerta se o **nome canônico** (após aliases, sem acento nem maiúsculas) e o **tipo** coincidem (`--sem-tipo` ignora o tipo). Relação acerta se sujeito, predicado e objeto coincidem; `relacionado_a` é simétrica.
- **Precisão** = acertos entre o previsto; **revocação** = acertos entre o esperado; **F1** = média harmônica. O total é micro; o avaliador também imprime a quebra por tipo de entidade, por predicado e por tipo de tela, com a **média simples entre tipos**, e relata `evento` e `gera` (em reserva) à parte. Reporte sempre o micro junto com a média simples: o glossário repete muitas anotações de personagem e domina o micro.
- `--csv-quebras arquivo.csv` grava as quebras; `--sem-quebras` imprime só o total. `eval/cobertura_ocr.py` mede o OCR sem dicionário: quantos nomes do gabarito aparecem no texto lido.

## O que há no gabarito
63 arquivos: **50 imagens** (glossário, bestiário, diálogo, escolhas, diário, mapa, item, quadro de avisos, HUD, cutscene) e **13 clipes**; 243 entidades, 46 relações, 61 nomes canônicos. Verificado pelo autor em duas rodadas (24 itens em 2026-10-07; os 39 acrescentados em 2026-10-08).

Escolhas de anotação a conhecer:
- A regra 9 é a que mais pesa: cenas em que só o rosto identifica o personagem rendem poucas entidades.
- Algumas relações são inferidas (`img_008`, `img_054`, `img_073`, `img_094`, `vid_023`); as demais vêm de texto ou objetivo explícito.
- Contratos de quadro de avisos são `missao` com `estado: disponivel` (`tipo_tela: outro`). `img_080` é o único caso de `obtido_em` e de missão concluída.
- `img_024` e `vid_035` são controles sem entidades; `img_016` é tutorial classificado como diálogo.
- Cutscene e escolhas de diálogo em imagem vêm de quadros de clipe (`img_084` a `img_097`).

## Correções posteriores (2026-10-08)
- **`img_088` e `img_094`:** a B3a mostrou duas omissões (a lista do diário e o painel do mapa também traziam "O Monstro de Pomar Branco"); acrescentadas, com a relação `ocorre_em` Pomar Branco.
- **Auditoria dos clipes:** os clipes tinham sido anotados com 6 quadros cada. Com 1 quadro por segundo, o OCR confirmou 9 entidades que faltavam: `vid_008` decisão "Aí nós treinamos Ciri"; `vid_023` Nilfgaard; `vid_030` e `vid_031` Cavaleiros Negros; `vid_031` Grifo; `vid_032` O Monstro de Pomar Branco; `vid_034` Carniçal e Geralt de Rívia; `vid_037` Uma frigideira nos trinques. Só entraram as que o extrator achou, com evidência no texto lido; o que ele deixou passar pode continuar faltando (a revocação em vídeo é limite superior).
- **Ontologia 1.1:** facções reanotadas em 11 itens.

## Como anotar um item novo
1. Escolha o item (cobrir todos os tipos de tela) e anote seguindo as regras; atualize `entidades.json` com nomes novos.
2. Rode `python scripts/validar_gabarito.py data/gabarito`.
3. No dia seguinte, revise 5 itens sorteados sem olhar as anotações e compare; diferenças mostram regra ambígua.
4. Se a ontologia mudar, ajuste os arquivos e valide de novo. Evite mudar regras no meio do caminho sem reanotar os itens antigos.

Testar o avaliador com os exemplos: `python eval/avaliar.py --gab data/gabarito/exemplo --pred eval/exemplo_pred`.
