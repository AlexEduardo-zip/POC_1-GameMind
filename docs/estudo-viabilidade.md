# Estudo de viabilidade: registro técnico das rodadas (B1 a B5)

Registro das estratégias testadas para transformar telas em entidades e relações. O resumo está em `docs/resumo-do-projeto.md`; aqui ficam métodos, tabelas e leituras. Tudo medido contra o gabarito verificado (`docs/gabarito.md`) com `eval/avaliar.py`, na máquina do projeto (Ryzen 5 5500, 16 GB, RX 7600 8 GB; `docs/hardware.md`). Formato e fonte do material são só guia (`docs/coleta.md`).

**Aviso geral:** regras, prompt e filtros foram ajustados sobre as mesmas imagens do gabarito, sem conjunto separado. São números de desenvolvimento, provavelmente otimistas.

## Como repetir
```bash
python scripts/rodar_extracao.py --estrategia <nome> --modo <completo|rois_brilho|estruturado> --workers 4   # imagens
python scripts/rodar_llm.py --estrategia <nome> --modelo qwen2.5:7b                                         # relações e itens (Ollama)
python scripts/rodar_video.py --estrategia <nome> --intervalo 2 [--llm qwen2.5:7b]                          # clipes
python eval/avaliar.py --pred eval/predicoes/<nome> [--csv-quebras eval/quebras_<nome>.csv]
python eval/cobertura_ocr.py --pred eval/predicoes/<nome>      # OCR sem dicionário
```
Dicionário: `data/gazetteer/witcher3_ptbr.json` (90 nomes de personagens, criaturas, locais, facções e itens, com distratores que não aparecem no teste). Foi escrito à parte do gabarito, mas **não é estritamente cego** (quem o escreveu conhecia o gabarito). Faltam de propósito nomes de missões, decisões e muitos locais.

## Visão geral (50 screenshots, medido em 2026-10-08)
| Etapa | O que entrou | Precisão | Revocação | F1 micro | F1 média entre tipos | Relações F1 | Tempo por imagem |
|---|---|---|---|---|---|---|---|
| B1 | OCR da imagem inteira + dicionário | 0,93 | 0,65 | 0,76 | 0,48 | 0 | 0,9 s |
| B2 | + recortes ampliados e filtro de brilho | 0,92 | 0,69 | 0,79 | 0,49 | 0 | 2,3 s |
| B3a | + regras por tela (missão, decisão, item) e relações estruturais | 0,92 | 0,83 | 0,87 | 0,84 | 0,29 | 3,3 s |
| B3b | + LLM local `qwen2.5:7b` | 0,91 | 0,87 | **0,89** | 0,85 | **0,44** | 11 s |
| B3b | + LLM local `qwen2.5:3b` | 0,92 | 0,84 | 0,88 | 0,84 | 0,30 | 9 s |

## B1: OCR e dicionário independente
- A linha de base inicial usava o dicionário **tirado do gabarito** e dava F1 0,87; com dicionário independente caiu para 0,76: **o vazamento valia 0,11**, e a primeira medida não deve ser citada.
- Tolerar erro de OCR no casamento de nomes (similaridade ≥ 0,88) **piorou** (sem acerto novo, 10 falsos positivos a mais, quase todos em locais): fica desligada para nomes curtos.
- Missão e decisão ficam em 0,00 (não estão em dicionário), item 0,00 (item do dicionário só vale em linha de título, ver B3a); HUD 0,00.
- Falsos positivos: 6 dos 11 eram a "Espada de Prata de Bruxo" lida do equipamento do inventário, que o gabarito não anota (regra 12).

## B2: pré-processamento
Recortes ampliados 2,5x das regiões de texto pequeno (`src/extracao/preprocessamento.py`): **legenda** (x 0,10–0,80, y 0,72–0,86), **HUD da missão** (x 0,72–1,00, y 0,26–0,50) e **avisos** (x 0,00–0,50, y 0,18–0,66); o OCR de cada recorte soma-se ao da imagem inteira. Medido também sem dicionário, com `eval/cobertura_ocr.py` (fração das 188 entidades das imagens cujo nome aparece no texto lido):

| Modo | Nomes no texto (exata / aprox.) | OCR por imagem |
|---|---|---|
| imagem inteira (B1) | 0,81 / 0,84 | 0,95 s |
| imagem inteira ampliada | 0,79 / 0,80 | 1,47 s |
| recortes + cinza | 0,88 / 0,90 | 2,77 s* |
| recortes + binarização global (otsu) | 0,87 / 0,90 | 2,44 s* |
| **recortes + brilho** (escolhido) | **0,89 / 0,91** | **2,13 s** (sequencial) |
| recortes + cinza e brilho | 0,89 / 0,92 | 4,15 s* |

\* medidos com 4 processos em paralelo (inflam um pouco).

- O maior ganho é na **legenda** (diálogo 0,53 → 0,87); missão 0,39 → 0,61 (0,72 com aproximação). Ampliar a imagem inteira sozinho piora; o ganho vem do recorte somado ao filtro de brilho.
- **HUD segue fraco:** o título da missão tem ~10 px de altura a 1080p. Num teste com 7 casos, o melhor chegou a 4 de 7. Para o HUD vale o texto aproximado e a repetição ao longo do vídeo.
- O gargalo passou do OCR (89% dos nomes lidos) para o dicionário (revocação 0,69).

## B3a: extração estruturada por tipo de tela
`src/extracao/estruturada.py` lê regiões fixas da interface e converte a estrutura em entidades, sem consultar o gabarito:
- **Missão:** título em maiúsculas do HUD; banner "Missão completada/atualizada" (com o estado); lista de missões do diário (a linha com o nome da região logo abaixo é legenda e vira `ocorre_em`); painel de missão rastreada do mapa; "Procurado:/Contrato:" do quadro de avisos (estado `disponivel`).
- **Decisão:** primeira opção de diálogo (o cursor começa nela), só em tela de jogo, com checagem de frase plausível e correção de grafia pelo dicionário ("Kaey Morhen" → "Kaer Morhen").
- **Item:** ficha do inventário (título em maiúsculas seguido do tipo, como "SUCO DE MAÇÃ" / "COMESTÍVEIS"); item do dicionário só em linha de título.
- **Relação:** personagem citado no objetivo do HUD `participa_de` a missão; legenda de região sob a missão no diário `ocorre_em`.
- **Consolidação no lote:** junta variações de leitura do mesmo título, prefere a grafia de banner e diário, recupera o artigo perdido ("O Monstro de..."), aplica o sufixo "(missão)" quando o título coincide com um local e **só aceita um título de missão que apareça em 2 ou mais imagens ou em banner** (texto de tutorial e ruído de OCR também saem em maiúsculas).

Resultado: missão 0,00 → 0,95, decisão 0,00 → 1,00 (3 casos), item 0,00 → 0,50, F1 micro 0,79 → 0,87 e média entre tipos 0,49 → 0,84; relações 0,29. Checagem leve em material novo: nas 47 imagens fora do gabarito as missões achadas fazem sentido, com a falha de um "A" inventado em "A Lilás e Groselha". A decisão usa sempre a primeira opção, o que nos 3 casos coincide com o gabarito mas não prova que generaliza. A B3a apontou duas omissões do gabarito (`img_088`, `img_094`), corrigidas.

## B3b: relações e itens com LLM local
Cascata (`src/extracao/llm.py`, `scripts/rodar_llm.py`): a base (B3a + dicionário) entra primeiro; o LLM recebe o texto lido (tela inteira, legenda, HUD e avisos separados) e a lista do que já foi detectado, e devolve entidades e relações em JSON de esquema fixo (saída estruturada do Ollama, temperatura 0). Back-end **plugável** (`Backend`, hoje `OllamaBackend`). A saída passa por `normalizar()`: nomes resolvidos pelo dicionário e pelos títulos já detectados; tipos, domínio e alcance validados pela ontologia; e filtros que exigem **lastro no texto**. Ollama 0.40.1, RX 7600 via ROCm, 100% na GPU.

| Versão (7B) | O que mudou | Entidades P / R / F1 | Relações P / R / F1 |
|---|---|---|---|
| base sem LLM | | 0,92 / 0,83 / 0,87 | 0,78 / 0,18 / 0,29 |
| v1 | prompt com lista de nomes conhecidos, sem filtros | 0,58 / 0,88 / 0,70 | 0,19 / 0,13 / 0,15 |
| v2 | sem a lista, entidade precisa estar na tela, item só em linha de título, rótulos de interface descartados | 0,80 / 0,87 / 0,84 | 0,31 / 0,33 / 0,32 |
| **v3** | só nome próprio, nomes e relação a até 4 linhas de distância, `membro_de` só com indício, variações de grafia unificadas | **0,91 / 0,87 / 0,89** | **0,52 / 0,38 / 0,44** |

A v1 mostra o risco: com a lista de nomes no prompt o modelo inventou personagens e facções que não estavam na tela (68 itens previstos, 10% de precisão). O que recuperou a precisão foi o **lastro no texto**, não o modelo.

| | Entidades F1 | Relações P / R / F1 | LLM por imagem | VRAM |
|---|---|---|---|---|
| base + qwen2.5:7b | 0,89 | 0,52 / 0,38 / 0,44 | 7,8 s (75 mil tokens de entrada e 12,7 mil de saída nas 50 imagens) | 4,42 GB |
| base + qwen2.5:3b | 0,88 | 0,37 / 0,26 / 0,30 | 6,1 s | 2,01 GB |
| só o LLM 7B, sem a base | 0,80 | 0,48 / 0,28 / 0,35 | 7,8 s | 4,42 GB |
| só o LLM 3B, sem a base | 0,58 | 0,21 / 0,10 / 0,14 | 6,1 s | 2,01 GB |

F1 por predicado (base + 7B): `concede` 1,00 (1 caso) · `ocorre_em` 0,67 · `participa_de` 0,48 · `localizado_em` 0,40 · `relacionado_a` 0,31 · `membro_de`, `obtido_em`, `parte_de` 0,00 (a recompensa vem em banner que o OCR lê torto, "MACAASSADA X 5"; `parte_de` quase nunca está escrito).

Leituras: o LLM traz as **relações** (0,29 → 0,44) e quase nada nas entidades (0,87 → 0,89); o 3B basta para entidades e perde 14 pontos em relações; o gabarito tem só 46 relações, várias inferidas, e uma a mais ou a menos mexe vários pontos.

## B4: vídeo por amostragem de quadros
`scripts/rodar_video.py` amostra um quadro por segundo de cada clipe com FFmpeg (`src/extracao/video.py`; 1920x1088 a 60 fps cortados para 1920x1080), roda em cada quadro o mesmo OCR, dicionário e regras (os 681 quadros ficam em cache) e **agrega por clipe**: nome do dicionário vale em 1 quadro; título de missão precisa de 2 ou mais quadros (ou banner); variações de opção de diálogo viram a mais frequente, que precisa de 2 quadros; relações estruturais somadas. Com `--llm`, o texto distinto de todos os quadros vai ao LLM **uma vez por clipe**.

**Auditoria prévia do gabarito dos clipes:** tinham sido anotados com 6 quadros cada; com 1 quadro por segundo o extrator achou entidades legítimas que faltavam, e 9 entraram (lista em `docs/gabarito.md`). Só entraram as que o extrator achou, então a revocação em vídeo é **limite superior**.

| Quadros usados (13 clipes, 683 s, sem LLM) | Quadros | Precisão | Revocação | F1 |
|---|---|---|---|---|
| 1 (o do meio, como uma screenshot) | 13 | 0,76 | 0,25 | 0,37 |
| 1 a cada 4 s | 172 | 0,82 | 0,62 | 0,71 |
| **1 a cada 2 s** | **342** | **0,84** | **0,70** | **0,76** |
| 1 a cada 1 s | 681 | 0,74 | 0,74 | 0,74 |

Custo: 2,9 s de OCR e regras por quadro (um processo); com 4 processos o lote de 681 quadros levou ~11 minutos (0,97 s por quadro), de modo que **a 2 s por quadro o clipe é processado em cerca de metade da duração dele**. Com LLM: +9,9 s por clipe. O LLM por clipe deixa as entidades iguais (F1 0,76) e dá relações F1 0,29 (P 0,21, R 0,43); o texto de um clipe inteiro perde a vizinhança entre nome e frase, e o gabarito dos clipes tem 7 relações, então esse número é frágil.

## B5: combinação das fontes
Entidades **únicas** do corpus contra o gabarito (61 únicas: 54 das imagens, 30 dos clipes, 7 só dos clipes):

| Fonte | Precisão | Revocação | F1 |
|---|---|---|---|
| só screenshots (50) | 0,86 | 0,72 | 0,79 |
| só clipes (13, 2 s, LLM) | 0,82 | 0,38 | 0,52 |
| **screenshots + clipes** | 0,81 | **0,82** | **0,81** |

Os clipes acham 6 das 7 entidades que só existem neles. **Pipeline completo nos 63 itens** (screenshots com a cascata 7B, clipes a 2 s com LLM): entidades P 0,88 / R 0,85 / **F1 0,86**; relações P 0,42 / R 0,39 / **F1 0,40** (sem LLM: 0,85 e 0,28). Por tipo de entidade: personagem 0,95 · criatura 0,93 · facção 0,91 · missão 0,86 · decisão 0,83 · local 0,69 · item 0,50. Por tipo de tela: glossário 0,98 · escolhas 0,92 · diário 0,90 · quadro de avisos 0,86 · diálogo 0,80 · item 0,75 · mapa 0,61 · HUD 0,61.

## Conclusão provisória (a confirmar na avaliação final, Semana 15)
1. **Um quadro por clipe não serve** (revocação 0,25): texto de legenda, HUD e banner aparece e some. **A cada 2 s** é o ponto certo; 1 s dobra o custo e derruba a precisão.
2. **O vídeo vale pelo tempo, não pela qualidade de imagem:** o clipe acrescenta o que acontece ao longo da cena (várias falas, banners passageiros, as duas escolhas de diálogo); screenshots e clipes se complementam (revocação 0,72 → 0,82).
3. **Entrada recomendada:** screenshots em menus e telas estáticas, vídeo amostrado a cada 2 s em cenas; para o produto, captura em intervalo curto com agregação por cena.
4. **Leitura da tela:** OCR com recortes e filtro de brilho, regras por tipo de tela e dicionário de nomes; **relações e itens:** LLM local, `qwen2.5:7b` (4,4 GB) quando importam as relações, `qwen2.5:3b` (2,0 GB) se bastarem as entidades.
5. **Custo:** ~11 s por imagem e menos que a duração do clipe, só CPU no OCR e GPU no LLM; compatível com processamento assíncrono.
6. **Em aberto:** relações (0,40), item (0,50), local (0,69), mapa e HUD (0,61); IA pública como alternativa; medida em telas novas, sem calibração.
