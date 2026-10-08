# Decisão 002 · Fechamento da ontologia (versão 1.0)

- Data: 2026-10-08
- Decisão: **congelar a ontologia como 1.0 com os 7 tipos e 8 predicados da 0.1**, com cinco ajustes de definição (abaixo) e sem criar nem remover tipos
- Base: análise do gabarito (53 arquivos, 190 anotações de entidade, 37 de relação, 52 nós no grafo), em 2026-10-08

## Análise

### 1. Cobertura dos tipos (critério da ontologia: revisar se mais de 10% não couber)
| Tipo | Anotações | Nós únicos | Observação |
|---|---|---|---|
| personagem | 98 | 13 | 87% são repetições (a lista lateral do glossário aparece em cada página) |
| local | 41 | 18 | |
| missão | 19 | 6 | estados usados: ativa, concluída, disponível |
| criatura | 13 | 3 | |
| item | 13 | 8 | subtipos usados: arma, carta, comestível, ingrediente, livro, poção |
| decisão | 6 | 4 | todas "opção de diálogo" |
| evento | 0 | 0 | sem uso |

Conteúdo que **não coube** em nenhum tipo, contado nas `observacoes` do gabarito: Caçada Selvagem, Nilfgaard, Exército Imperial (facções), Gwent e cartas, categorias do bestiário (Necrófagos, Híbridos). São cerca de 9 menções contra 190 anotações, **menos de 5%**: o critério de revisão não foi atingido.

### 2. Uso dos predicados
| Predicado | Usos | Leitura |
|---|---|---|
| participa_de | 10 | exercitado |
| ocorre_em | 7 | exercitado (2 inferidas pelo mapa) |
| relacionado_a | 7 | exercitado, o `rotulo` resolve aliado, mentor, irmão de armas |
| localizado_em | 6 | exercitado |
| parte_de | 3 | exercitado pouco |
| obtido_em | 3 | exercitado só por uma tela de recompensa (`img_080`) |
| concede | 1 | exercitado só por inferência da assinatura de um cartaz |
| gera | 0 | **sem evidência** |

### 3. Grafo
- 28 de 51 nós estavam isolados antes do `img_080` (55%). Causa: o gabarito só anota relação que a tela afirma (regra 7), e a maioria das telas mostra um nome sozinho.
- 4 das 6 decisões estavam sem ligação, porque a tela de diálogo não mostra a missão ativa. Isso é limite do pipeline (falta de contexto de sessão), não da ontologia.

### 4. Perguntas que o grafo deve responder (ontologia.md)
| Pergunta | Veredito com o corpus |
|---|---|
| Quem é X e onde o vi? | responde (nota com fontes, `localizado_em` em parte) |
| Que missões estão em andamento e onde? | responde (`estado` e `ocorre_em`) |
| Quem me deu essa missão? | responde pouco (1 `concede`) |
| Quem participou da missão? | responde |
| O que decidi e o que isso gerou? | **só a primeira parte**: não há consequência na tela, e mostrá-la depois já seria conteúdo futuro |
| Onde achei este item? | responde (`obtido_em` e `localizado_em`) |
| Como X e Y se relacionam? | responde |

### 5. Inconsistências achadas
- A ontologia dizia "chave = nome + tipo; mesmo nome com tipos diferentes não se funde", mas `grafo.py` e `validar_gabarito.py` resolvem nomes **sem olhar o tipo**; a convenção de fato (regra 8 do gabarito) é desambiguar com sufixo, como "Kaer Morhen (missão)".
- O estado `disponivel` (contrato visto em quadro de avisos, ainda não aceito) é usado no corpus e não estava definido.
- As métricas micro ficam dominadas pelo glossário (muitas anotações repetidas de personagem); ver recomendação 6.

## Decisões

| # | Questão | Decisão | Por quê |
|---|---|---|---|
| 1 | Criar tipo `faccao`? | **Não na 1.0**; candidato à 1.1 | Menos de 5% de conteúdo fora de escopo; exigiria novo predicado (`membro_de`) e mais anotação sem ter como medir ganho agora. Facções continuam fora e ficam citadas na descrição |
| 2 | Manter `evento` e `gera`, sem nenhum uso? | **Manter, marcados como "reserva"** | Remover não ganha nada (o validador já os suporta) e a análise de vídeo de cutscene é onde eventos podem aparecer. Ficam fora das métricas principais (relatar à parte) e são reavaliados na avaliação comparativa (Semana 15): sem uso real até lá, saem na 1.1 |
| 3 | Manter `obtido_em` e `concede` com 1 a 3 usos? | **Manter** | Têm evidência (recompensa de missão, assinatura de cartaz) e respondem a perguntas do jogador |
| 4 | Chave de identidade | **Nome canônico normalizado; tipo não entra na chave**, e nomes iguais de tipos diferentes levam sufixo "(missão)" etc. | É o que o código e o gabarito já fazem; corrige o texto da ontologia |
| 5 | Estados de missão | **ativa, disponivel, concluida, falhou** | `disponivel` é usado no corpus |
| 6 | Regra 9 do gabarito (personagem só com nome escrito) | **Manter** | Mede o OCR de forma justa; o reconhecimento por rosto é capacidade do modelo de visão e deve entrar como comparação à parte, não como regra do gabarito |
| 7 | Conceitos do glossário, Gwent, categorias do bestiário | **Continuam fora** | Menos de 5% e sem pergunta do jogador associada |

## Recomendações derivadas (fora da ontologia)
1. Na avaliação, relatar o F1 por tipo de tela e por tipo de entidade, além do micro, para o glossário não dominar o número.
2. Guardar a missão ativa do HUD como contexto de sessão para ligar decisões e itens a missões (`parte_de`, `obtido_em`) no pipeline.
3. Reavaliar `evento` e `gera` na Semana 15 com os resultados do vídeo; remover na 1.1 se continuarem sem uso.
4. Estender o gabarito com telas de recompensa, notificação de missão atualizada e cenas com consequência visível, para exercitar o que falta.

## Efeito nos arquivos
`docs/ontologia.md` (versão 1.0, identidade, estados, reserva, histórico), `src/ontologia.json` e `src/schema.py` (versão e estados), `docs/gabarito.md` (nova anotação `img_080`), `README.md` e `docs/proximos-passos.md`.
