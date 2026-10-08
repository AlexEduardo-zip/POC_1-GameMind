# GameMind

Análise de conteúdo e construção de grafos de conhecimento a partir da jornada do jogador.
POC I / MSI I · DCC/UFMG · Aluno: Alex Eduardo Alves dos Santos · Orientador: Lucas N. Ferreira
Repositório: https://github.com/AlexEduardo-zip/POC_1-GameMind

O GameMind lê o que o jogador já viu na tela (screenshots e clipes), extrai entidades e relações (personagens, missões, locais, itens, decisões, facções) e as organiza em um grafo persistente, exportado como vault do Obsidian. Jogo-piloto: The Witcher 3 (pt-BR). Nesta fase só a **camada de análise** existe; captura automática e empacotamento ficam para o POC II.

**Leia primeiro: [docs/resumo-do-projeto.md](docs/resumo-do-projeto.md)** (construção, resultados, limites e como reproduzir).

## Estado (2026-10-08)
- Semanas 1 a 7 do cronograma concluídas: jogo-piloto, coleta, gabarito verificado (63 itens), ontologia 1.1 congelada e estudo de viabilidade (B1 a B5).
- Resultado principal: OCR com recortes + regras por tipo de tela + LLM local (`qwen2.5:7b` via Ollama, 4,4 GB de VRAM, ~11 s por imagem) dá **entidades F1 0,86 e relações F1 0,40** nos 63 itens (screenshots e clipes). Números de desenvolvimento, sem conjunto separado.
- Falta: medida em telas novas, IA pública como alternativa, protótipo integrado e avaliação final. Ver [docs/proximos-passos.md](docs/proximos-passos.md).

## Mapa do projeto
| Caminho | O que é |
|---|---|
| `docs/resumo-do-projeto.md` | **Resumo principal** |
| `docs/estudo-viabilidade.md` | Registro técnico das rodadas B1 a B5 |
| `docs/ontologia.md`, `docs/decisoes/` | Ontologia 1.1; decisões 001 (jogo-piloto) e 002 (ontologia) |
| `docs/coleta.md`, `docs/gabarito.md` | Material coletado; regras de anotação e correções do gabarito |
| `docs/hardware.md` | Hardware e medidas de GPU |
| `docs/justificativa.md`, `docs/referencias.md`, `docs/revisao/` | Justificativa, referências e revisão da literatura |
| `docs/proximos-passos.md`, `docs/diario.md` | Pendências; diário de bordo |
| `docs/exemplo/` | Grafo e vault de exemplo do prólogo (em inglês, só demonstração) |
| `src/extracao/` | OCR, pré-processamento, dicionário, regras por tela, LLM (back-end plugável) e vídeo |
| `src/schema.py`, `src/ontologia.json` | Esquema e ontologia legível por máquina |
| `src/grafo.py`, `src/exportar_vault.py` | Grafo único e exportador para o Obsidian |
| `scripts/rodar_extracao.py`, `rodar_llm.py`, `rodar_video.py` | Estratégias de extração (imagens, LLM, clipes) |
| `scripts/validar_gabarito.py`, `check_env.py`, `smoke_ocr.py` | Validação do gabarito, checagem do ambiente, teste rápido de OCR |
| `eval/avaliar.py`, `eval/cobertura_ocr.py` | Precisão, revocação e F1 (total e por tipo); cobertura do OCR sem dicionário |
| `data/raw/` | Screenshots e clipes e `metadados.csv` (não versionados) |
| `data/gabarito/`, `data/gazetteer/` | Gabarito verificado (+ `exemplo/`); dicionário de nomes independente |
| `eval/predicoes/`, `vault_output/` | Previsões e vault gerados (não versionados) |

## Ambiente
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    Linux: source .venv/bin/activate
pip install -r requirements.txt
python scripts/check_env.py         # precisa também de Tesseract (com `por`), FFmpeg e, para o LLM, Ollama
```

## Testar o pipeline com os exemplos
Com o ambiente ativado (precisa do `pydantic`):
```bash
python scripts/validar_gabarito.py data/gabarito/exemplo
cd src && python grafo.py --gab ../data/gabarito/exemplo --saida ../grafo.json && cd ..
python src/exportar_vault.py --grafo grafo.json --saida vault_output
python eval/avaliar.py --gab data/gabarito/exemplo --pred eval/exemplo_pred
```
O `ex_003_escolhas.json` não tem previsão de exemplo, então o avaliador o ignora de propósito. Os comandos do pipeline real estão em `docs/resumo-do-projeto.md`, seção 7.
