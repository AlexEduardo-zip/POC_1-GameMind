# Estudo de viabilidade: registro das rodadas

Registro vivo das estratégias testadas (Semanas 5–7). Cada rodada usa `scripts/rodar_extracao.py`, `eval/avaliar.py` e, para medir o OCR sem dicionário, `eval/cobertura_ocr.py` sobre o gabarito verificado (63 arquivos: 50 imagens e 13 clipes). Máquina: Ryzen 5 5500, 16 GB, sem GPU no OCR (`docs/hardware.md`). Formato e fonte do material são só guia (ver `docs/semana2.md`).

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

## B2: pré-processamento (2026-10-08)
Recortes ampliados onde o jogo põe texto pequeno (`src/extracao/preprocessamento.py`): **legenda** (x 0,10–0,80, y 0,72–0,86), **HUD da missão** (x 0,72–1,00, y 0,26–0,50) e **avisos à esquerda** (x 0,00–0,50, y 0,18–0,66), ampliados 2,5x. O OCR de cada recorte é somado ao da imagem inteira. Filtros testados: `cinza`, `otsu` (binarização global) e `brilho` (fica só o que é bem claro, porque o texto do jogo é branco ou amarelo com contorno escuro). Os modos estão em `src/extracao/ocr.py` (`--modo` do `rodar_extracao.py`).

Como o dicionário esconde a qualidade do OCR (missões e decisões nem estão nele), a B2 foi medida também com `eval/cobertura_ocr.py`: **fração das 188 entidades do gabarito cujo nome aparece no texto lido**, sem dicionário.

| Modo | Cobertura exata | Com aproximação | F1 (micro) com dicionário | Média entre tipos | OCR por imagem* |
|---|---|---|---|---|---|
| `completo` (B1) | 0,81 | 0,84 | 0,76 | 0,49 | 0,95 s |
| `inteira_cinza` (imagem inteira ampliada) | 0,79 | 0,80 | 0,74 | 0,48 | 1,47 s |
| `rois_cinza` | 0,88 | 0,90 | 0,78 | 0,50 | 2,77 s |
| `rois_otsu` | 0,87 | 0,90 | 0,79 | 0,50 | 2,44 s |
| **`rois_brilho`** (escolhido) | **0,89** | 0,91 | 0,78 | 0,50 | **2,13 s (sequencial)** |
| `rois_mix` (cinza + brilho) | 0,89 | 0,92 | 0,78 | 0,50 | 4,15 s |

\* tempos dos 5 primeiros modos medidos com 4 processos em paralelo (inflam um pouco); `rois_brilho` foi medido também em sequência: **50 imagens em 106,8 s, 2,13 s por imagem**, só CPU. Os modos `rois_cinza` e `rois_otsu` foram rodados antes de o HUD passar a usar o modo de página 11 do Tesseract, que só afeta o HUD.

### Cobertura por tipo de tela (exata, `completo` → `rois_brilho`)
diálogo 0,53 → **0,87** · HUD 0,00 → 0,22 (0,56 com aproximação) · mapa 0,33 → 0,47 · item 0,80 → 0,93 · diário 0,96 → 0,96 · escolhas 0,67 → 0,67. Por tipo de entidade: local 0,74 → 0,82 · missão 0,39 → **0,61** (0,72 com aproximação).

### Leituras
1. **O ganho é real, mas moderado:** cobertura 0,81 → 0,89 (+8 pontos) e F1 micro 0,76 → 0,78/0,79. O maior efeito é na **legenda**: 0,53 → 0,87 de cobertura em diálogo. O recorte e o filtro de brilho tiram o texto da cena; ampliar a imagem inteira sozinho **piora** (`inteira_cinza`).
2. **O gargalo agora é o dicionário, não o OCR:** o texto lido contém 89% dos nomes, mas a revocação com dicionário é 0,70. Missão (cobertura 0,61, revocação 0,00), item (0,11) e local fora do dicionário não são recuperados por casamento de nomes. É o objetivo da B3.
3. **HUD continua o ponto fraco:** o título da missão tem cerca de 10 px de altura a 1080p e ampliar não inventa detalhe. Um teste à parte, só nos 7 casos de missão lida do HUD, deu no máximo 4 de 7 (filtro de brilho, modo de página 11, nos recortes testados); amostra pequena. Para o HUD, usar o **texto aproximado** (0,56 a 0,67 contra 0,22 exato) e a repetição ao longo do vídeo, que dá várias chances por clipe (B4).
4. **Aproximação serve para nomes longos:** na B1 ela piorou a precisão (nomes curtos de local viravam falso positivo); na cobertura de nomes de missão (várias palavras) ela dá +0,11. Regra para a B3: casamento aproximado só para nomes com 2 ou mais palavras.
5. **Escolhido: `rois_brilho`.** Melhor cobertura exata (0,89) com 2,1 s por imagem; `rois_mix` ganha só 0,01 na cobertura aproximada e custa quase o dobro.
6. **Mapa (0,47) e escolhas (0,67) não melhoraram:** rótulos de mapa sobre o terreno e opções de diálogo pequenas pedem recorte próprio, que só vale a pena se a B4 mostrar que o vídeo não resolve.

## B3a: extração estruturada por tipo de tela (2026-10-08)
`src/extracao/estruturada.py` lê regiões fixas da interface e converte a estrutura em entidades que dicionário nenhum alcança, sem consultar o gabarito:
- **Missão:** título em maiúsculas do HUD, banner "Missão completada/atualizada" (com o estado), lista de missões do diário (a linha com o nome da região logo abaixo é legenda, não missão), painel de missão rastreada do mapa e "Procurado:/Contrato:" do quadro de avisos (contrato ainda não aceito, estado `disponivel`).
- **Decisão:** primeira opção de diálogo, só em tela de jogo (fora de menu, quadro e telas com "Voltar"), com checagem de que o texto é frase de verdade e correção de grafia pelo dicionário (ex.: "Kaey Morhen" vira "Kaer Morhen").
- **Consolidação no lote:** junta variações de leitura do mesmo título (ex.: "KAERIMORHEN" e "Kaer Morhen"), prefere a grafia de banner e diário, recupera o artigo perdido ("O Monstro de...") quando uma fonte confiável o tem, aplica o sufixo "(missão)" quando o título coincide com um local (regra de identidade da ontologia) e **só aceita título vindo apenas do HUD se ele aparecer em 2 ou mais imagens** (texto de tutorial também sai em maiúsculas e gerava "Passando" e "Joias de Vida").
- Roda por `python scripts/rodar_extracao.py --estrategia estruturado --modo estruturado`; soma o dicionário sobre o `rois_brilho` da B2.

| Rodada | Precisão | Revocação | F1 micro | F1 média entre tipos | Missão | Decisão | Tempo por imagem |
|---|---|---|---|---|---|---|---|
| B1 `ocr_gazetteer` | 0,89 | 0,66 | 0,76 | 0,49 | 0,00 | 0,00 | 0,87 s |
| B2 `rois_brilho` | 0,88 | 0,70 | 0,78 | 0,50 | 0,00 | 0,00 | 2,13 s |
| **B3a `estruturado`** | **0,88** | **0,81** | **0,84** | **0,77** | **0,89** (P 0,85, R 0,94) | **1,00** (3 de 3) | **3,08 s** (50 imagens em 154,4 s, sequencial) |

F1 por tipo de entidade (B3a): personagem 0,94 · criatura 0,96 · facção 0,80 · local 0,70 · missão 0,89 · decisão 1,00 · item 0,11. Por tipo de tela: glossário 0,98 · diário 0,89 · escolhas 0,91 · diálogo 0,83 · mapa 0,55 · HUD 0,53 · quadro de avisos (`outro`) 0,69 · item 0,44. Relações: 0.

### Leituras
1. **Missão e decisão saíram de 0,00:** missão 0,89 e decisão 1,00; a média entre tipos foi de 0,50 para 0,77 e o F1 micro de 0,78 para 0,84. O custo é 1 s a mais por imagem (3,08 s, só CPU).
2. **Cuidado com o otimismo:** as regras foram calibradas olhando **estas mesmas 50 imagens**, sem conjunto separado, então os números são de desenvolvimento e provavelmente superestimam. A decisão tem **n = 3** (e usa a primeira opção, porque o cursor começa nela; nos 3 casos do gabarito a decisão também é a primeira, então isso não prova que generaliza). Como checagem leve, rodei o extrator nas 47 imagens **fora do gabarito**: as missões achadas fazem sentido (Kaer Morhen, Lilás e Groselha, O Monstro de Pomar Branco em HUD, diário e mapa; "Está combinado" no `img_087`), e as duas falhas vistas foram um prefixo "A" em "A Lilás e Groselha" (artigo inventado pelo OCR, que na rodada principal é corrigido pela consolidação) e os falsos positivos de tutorial, tratados pela regra de 2 imagens. Precisão em material novo continua sem medida; para medir, é preciso anotar telas novas.
3. **Dois falsos positivos aparentes são omissões do gabarito:** `img_088` (diário com as duas missões na lista, anotada só a aberta) e `img_094` (mapa com a missão rastreada no painel, anotada só a de `img_092`). Se fossem anotadas, a precisão de missão subiria de 0,85 para 0,95. Ficam como estão até decisão do autor, já que o gabarito foi verificado.
4. **Erro que sobra em missão:** "Uma Frigideira Nos Trinquese" (banner lido com um "e" a mais; o nome só aparece uma vez, então não há como corrigir por consolidação).
5. **Ainda fraco:** item (0,11), local fora do dicionário (0,70), HUD (0,53) e mapa (0,55). Itens aparecem em tooltips de inventário e comida/ingredientes, sem dicionário; é o alvo natural da B3b (LLM sobre o texto) junto com as relações.
6. **Limites declarados:** só imagens (os 13 clipes ficam para a B4), sem relações, e dependente da geometria 1920x1080 do jogo em pt-BR.

## Próximas rodadas
| Etapa | O que testar | Esperado |
|---|---|---|
| ~~B2~~ | ~~Pré-processamento~~ (feito, ver acima) | cobertura 0,81 → 0,89; diálogo 0,53 → 0,87 |
| ~~B3a~~ | ~~Extração estruturada por tipo de tela~~ (feito, ver acima) | missão 0,00 → 0,89; decisão 0,00 → 1,00 |
| **B3b (próximo)** | LLM local (Ollama, 7–8B) sobre o texto do OCR, saída no formato de `src/schema.py` | relações (hoje 0) e itens (0,11); medir tempo e VRAM |
| B4 | Vídeo: quadros a cada 1–2 s com o mesmo extrator, unindo por clipe | comparar com screenshot; cobrir os 13 clipes |
| B5 | Combinação screenshot + vídeo | etapa final do estudo |
