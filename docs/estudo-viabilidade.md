# Estudo de viabilidade: registro das rodadas

Registro vivo das estratégias testadas (Semanas 5–7). Cada rodada usa `scripts/rodar_extracao.py` e `eval/avaliar.py` sobre o gabarito verificado (63 arquivos: 50 imagens e 13 clipes). Máquina: Ryzen 5 5500, 16 GB, sem GPU no OCR (`docs/hardware.md`). Formato e fonte do material são só guia (ver `docs/semana2.md`).

## Como repetir
```bash
python scripts/rodar_extracao.py --estrategia ocr_gazetteer [--fuzzy 0.88]
python eval/avaliar.py --pred eval/predicoes/ocr_gazetteer --csv-quebras eval/quebras_ocr_gazetteer.csv
```
O dicionário é `data/gazetteer/witcher3_ptbr.json` (90 nomes de personagens, criaturas, locais, facções e itens, com distratores que não aparecem no teste). Foi escrito à parte do gabarito, mas **não é estritamente cego**: quem o escreveu conhecia o gabarito. Falta de propósito o que um dicionário real não teria: nomes de missões, decisões e muitos locais menores.

## Rodadas (50 screenshots; clipes sem previsão ainda)
| # | Estratégia | Dicionário | Precisão | Revocação | F1 (micro) | F1 (média entre tipos) | Tempo (50 imagens) |
|---|---|---|---|---|---|---|---|
| 0 | `baseline_ocr` | do próprio gabarito (**vazamento**) | 0,94 | 0,81 | 0,87 | 0,82 | 43,5 s |
| 1 | `ocr_gazetteer` | independente | 0,89 | 0,66 | **0,76** | 0,49 | 43,9 s (0,87 s de OCR por imagem) |
| 2 | `ocr_gazetteer_fuzzy` (similaridade ≥ 0,88) | independente | 0,83 | 0,66 | 0,74 | 0,48 | 47,0 s |

Relações: 0 em todas (nenhuma estratégia extrai relações ainda).

## Leituras (rodada 1, a referência)
1. **O vazamento valia 0,11 de F1** (0,87 contra 0,76). A rodada 0 não deve mais ser citada como resultado.
2. **Tolerância a erro de OCR (fuzzy) não ajudou:** nenhum acerto novo e 10 falsos positivos a mais, quase todos em locais. Fica desligada; o ganho esperado vem do pré-processamento da imagem, não de afrouxar o casamento de nomes.
3. **Por tipo de entidade (rodada 1):** personagem 0,91, criatura 0,92, facção 0,80, local 0,70, item 0,11, **missão 0,00 e decisão 0,00**. Missões e decisões não estão em dicionário nenhum: vêm do título do HUD, do diário e das opções de diálogo, que exigem leitura estruturada da tela (etapa B3).
4. **Por tipo de tela:** glossário 0,96 e diário 0,80 são viáveis só com OCR e dicionário; diálogo 0,61, escolhas 0,50, mapa 0,24 e item 0,32 ficam abaixo; **HUD 0,00** (nenhum nome achado, a fonte pequena sobre cena clara não sai no OCR de imagem inteira).
5. **Falsos positivos:** 6 dos 11 são "Espada de Prata de Bruxo" lida do equipamento do inventário, que o gabarito deliberadamente não anota (regra 12, rótulos de espaços do inventário). É uma convenção a explicitar para o extrator: nome de equipamento em uso não é entidade.
6. **Falsos negativos mais comuns:** as missões (Lilás e Groselha 6, Kaer Morhen (missão) 5, O Monstro de Pomar Branco 4), locais fora do dicionário (Arbusteira, Vila Saqueada, Encruzilhada, Taverna de Pomar Branco), Exército Imperial e itens comuns (Pão, Suco de maçã, Maçã assada, Carta de Yennefer).
7. **Custo:** 0,87 s por imagem só de CPU; 50 imagens em 44 s. Cabe com folga no processamento assíncrono previsto.

## Próximas rodadas
| Etapa | O que testar | Esperado |
|---|---|---|
| B2 | Pré-processamento: recorte da legenda e do HUD, ampliação, binarização | subir HUD, diálogo e mapa |
| B3a | Extração estruturada por tipo de tela (título do HUD e do diário = missão, opções de diálogo = decisão) | tirar missão e decisão de 0,00 |
| B3b | LLM local (Ollama, 7–8B) sobre o texto do OCR, saída no formato de `src/schema.py` | relações e itens; medir tempo e VRAM |
| B4 | Vídeo: quadros a cada 1–2 s com o mesmo extrator, unindo por clipe | comparar com screenshot; cobrir os 13 clipes |
| B5 | Combinação screenshot + vídeo | etapa final do estudo |
