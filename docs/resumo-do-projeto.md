# GameMind: resumo da construção e dos resultados (POC I)

Estado em 2026-10-08. Este é o documento principal; os demais detalham cada parte (mapa no fim).

## 1. Problema e solução
Em jogos longos (RPGs, aventuras), o jogador perde o fio de personagens, missões, locais e decisões entre uma sessão e outra, e os diários do jogo e as wikis não representam a **partida dele** nem evitam spoiler. O GameMind transforma o que o jogador **já viu na tela** em um **grafo de conhecimento** persistente (um vault de notas Markdown para o Obsidian, mais JSON). Nesta fase (POC I) só a **camada de análise** é construída: o conteúdo é coletado à mão e processado depois, sem captura automática. Jogo-piloto: **The Witcher 3** em português do Brasil.

## 2. O que foi construído
```
screenshot / quadros de vídeo
   └─► OCR com recortes (legenda, HUD, avisos) e filtro de brilho
        └─► regras por tipo de tela + dicionário de nomes   → missões, decisões, itens, personagens, locais...
             └─► LLM local (Ollama) em cascata               → relações e entidades que faltam
                  └─► validação pela ontologia (tipos, domínio e alcance) e lastro no texto
                       └─► grafo único (nomes canônicos, fontes) ─► vault do Obsidian + JSON
avaliação: previsões × gabarito verificado → precisão, revocação, F1 por tipo de entidade, predicado e tela
```
| Parte | Onde |
|---|---|
| Ontologia 1.1 (8 tipos, 9 relações) e esquema | `docs/ontologia.md`, `src/ontologia.json`, `src/schema.py` |
| Gabarito (63 itens verificados) e guia de anotação | `data/gabarito/`, `docs/gabarito.md` |
| Extração: OCR, dicionário, regras por tela, LLM, vídeo | `src/extracao/`, `scripts/rodar_*.py`, `data/gazetteer/` |
| Grafo e vault do Obsidian | `src/grafo.py`, `src/exportar_vault.py` |
| Avaliação | `eval/avaliar.py`, `eval/cobertura_ocr.py` |

Back-end de IA **plugável**: hoje o modelo local via Ollama (`qwen2.5:7b` e `3b`); a IA pública entra como outra implementação da mesma interface (Semanas 8–10).

## 3. Material e gabarito
- **Coleta** (`docs/coleta.md`): 83 screenshots, 14 quadros extraídos de clipes e 36 clipes do AMD Adrenalin (1920x1080, pt-BR), catalogados em `data/raw/metadados.csv` (não versionado).
- **Gabarito**: 50 imagens e 13 clipes anotados à mão (243 entidades, 46 relações, 61 nomes canônicos), verificados pelo autor. Os clipes foram depois auditados com o extrator (+9 entidades).
- **Ontologia 1.1**: personagem, criatura, local, missão, item, evento, decisão e facção; predicados `participa_de`, `ocorre_em`, `localizado_em`, `parte_de`, `concede`, `obtido_em`, `gera`, `membro_de`, `relacionado_a`. `evento` e `gera` ficam em reserva (nenhum caso real). Decisões e análise: `docs/decisoes/002-ontologia-1-0.md`.

## 4. Resultados (50 screenshots do gabarito; medidos de novo em 2026-10-08)
| Etapa | O que entrou | Entidades F1 (micro) | Média entre tipos | Relações F1 | Tempo por imagem |
|---|---|---|---|---|---|
| B1 | OCR da imagem inteira + dicionário independente do gabarito | 0,76 | 0,48 | 0 | 0,9 s |
| B2 | recortes ampliados + filtro de brilho | 0,79 | 0,49 | 0 | 2,3 s |
| B3a | regras por tela (missão, decisão, item) + relações estruturais | 0,87 | 0,84 | 0,29 | 3,3 s |
| **B3b** | **+ LLM local (qwen2.5:7b)** | **0,89** | **0,85** | **0,44** | **11 s** (3 de OCR e regras + 8 do LLM) |
| B3b | + LLM local menor (qwen2.5:3b) | 0,88 | 0,84 | 0,30 | 9 s |

**Vídeo** (13 clipes, sem LLM): 1 quadro por clipe F1 0,37; 1 quadro a cada 4 s 0,71; **a cada 2 s 0,76**; a cada 1 s 0,74 (mais ruído, o dobro do custo). **Combinação** (entidades únicas do corpus): screenshots sozinhas revocação 0,72; clipes sozinhos 0,38 (mas acham 6 das 7 entidades que só existem em vídeo); **juntos 0,82**. **Pipeline completo nos 63 itens: entidades F1 0,86 e relações F1 0,40** (sem LLM, 0,85 e 0,28).

Por tipo de entidade (pipeline completo): personagem 0,95 · criatura 0,93 · facção 0,91 · missão 0,86 · decisão 0,83 · local 0,69 · item 0,50. Por tipo de tela: glossário 0,98 · escolhas 0,92 · diário 0,90 · quadro de avisos 0,86 · diálogo 0,80 · item 0,75 · mapa e HUD 0,61.

**Hardware** (Ryzen 5 5500, 16 GB, RX 7600 8 GB): o OCR roda só na CPU; o Ollama usa a GPU (ROCm) com 100% do modelo: 4,4 GB de VRAM no 7B (7,8 s por imagem) e 2,0 GB no 3B (6,1 s). Um clipe é processado em cerca de metade da sua duração (quadro a cada 2 s, 4 processos).

## 5. O que os resultados dizem
1. **Dá para converter o conteúdo da tela em grafo útil com IA local e modesta:** entidades F1 0,86 e relações 0,40, em hardware de consumo, cabendo em processamento assíncrono.
2. **O ganho veio da estrutura, não do modelo:** recortes, regras por tela e dicionário levaram entidades de 0,76 a 0,87; o LLM acrescenta as relações (0,29 → 0,44) e quase nada nas entidades. Sozinho, o LLM inventa nomes (precisão 0,58 numa tentativa) até receber a regra de **lastro no texto**.
3. **Vídeo e screenshot se complementam:** um quadro por clipe não basta; amostrar a cada 2 s recupera o que aparece e some (falas, banners, escolhas) e a combinação das fontes dá a maior cobertura.
4. **7B ou 3B:** o 3B basta para entidades e cabe em 2 GB, mas perde 14 pontos de F1 em relações.
5. **Pontos fracos:** relações (0,40), item (0,50), local fora do dicionário (0,69), mapa e HUD (0,61, texto pequeno sobre a cena).

## 6. Limites (leia antes de citar os números)
- **Sem conjunto separado:** regras, prompt e filtros foram ajustados sobre as mesmas imagens do gabarito; os números são de desenvolvimento e provavelmente otimistas. Falta uma medida em telas novas.
- **Gabarito pequeno e parcialmente inferido:** 46 relações (7 nos clipes), algumas deduzidas; os clipes foram anotados com 6 quadros e só ampliados onde o extrator achou algo (a revocação em vídeo é limite superior). A decisão de diálogo tem 3 a 7 casos.
- **Dicionário de nomes:** escrito à parte do gabarito, mas por quem conhecia o gabarito; o vazamento da primeira versão (dicionário tirado do gabarito) valia 0,11 de F1.
- **Geometria fixa:** as regiões de leitura valem para 1920x1080 do jogo em pt-BR.
- **Fora do escopo desta fase:** captura automática, empacotamento, consulta em linguagem natural, IA pública, testes com jogadores (POC II).

## 7. Como reproduzir
```bash
python -m venv .venv && .venv\Scripts\activate && pip install -r requirements.txt   # precisa também de Tesseract (com `por`), FFmpeg e Ollama
python scripts/validar_gabarito.py data/gabarito
python scripts/rodar_extracao.py --estrategia estruturado --modo estruturado --workers 4   # OCR + regras + dicionário (imagens)
python scripts/rodar_llm.py --estrategia llm_qwen7b                                         # relações e itens (precisa de `ollama serve` e `ollama pull qwen2.5:7b`)
python scripts/rodar_video.py --estrategia video_2s --intervalo 2 --llm qwen2.5:7b          # clipes
python eval/avaliar.py --pred eval/predicoes/llm_qwen7b                                     # P, R e F1 por tipo
cd src && python grafo.py --gab ../data/gabarito --saida ../grafo.json && cd .. && python src/exportar_vault.py --grafo grafo.json --saida vault_output
```

## 8. Próximos passos
Medida limpa em telas novas; IA pública como back-end alternativo e comparação (Semanas 8–10); avaliação final e relatório (Semanas 15–16); depois, POC II. Lista em `docs/proximos-passos.md`.

## 9. Mapa da documentação
| Documento | Conteúdo |
|---|---|
| `docs/resumo-do-projeto.md` | este resumo |
| `docs/estudo-viabilidade.md` | registro técnico das rodadas B1 a B5 (métodos, tabelas, leituras) |
| `docs/ontologia.md`, `docs/decisoes/` | ontologia 1.1; decisões 001 (jogo-piloto) e 002 (fechamento da ontologia) |
| `docs/coleta.md`, `docs/gabarito.md` | material coletado; regras de anotação e histórico das correções do gabarito |
| `docs/hardware.md` | hardware e medidas de GPU |
| `docs/justificativa.md`, `docs/referencias.md`, `docs/revisao/` | justificativa, referências e revisão da literatura |
| `docs/proximos-passos.md`, `docs/diario.md` | pendências e diário de bordo |
| `docs/exemplo/` | grafo e vault de exemplo (prólogo, em inglês, só para demonstrar o pipeline) |
