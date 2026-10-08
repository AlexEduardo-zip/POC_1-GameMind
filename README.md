# GameMind

Análise de conteúdo e construção de grafos de conhecimento a partir da jornada do jogador.
POC I / MSI I · DCC/UFMG · Aluno: Alex Eduardo Alves dos Santos · Orientador: Lucas N. Ferreira

## Estado atual
- Repositório: https://github.com/AlexEduardo-zip/POC_1-GameMind
- Fase: POC I. Semanas 1 e 2 (preparação, coleta e gabarito) concluídas; Semana 3 (ontologia) adiantada, falta congelar a 1.0
- Jogo-piloto: The Witcher 3
- Ontologia: **1.0 congelada em 2026-10-08** (7 tipos, 8 relações; `evento` e `gera` em reserva; ver `docs/decisoes/002-ontologia-1-0.md`)
- Pipeline de exemplo funcionando: gabarito → validação → grafo → vault do Obsidian → avaliação
- Captura: pt-BR; resolução, formato e ferramenta são só guia (desvios registrados em `data/raw/metadados.csv`)
- **Próximos passos: `docs/proximos-passos.md` (fonte única das pendências, com critério de pronto)**
- Feito em 2026-10-07: ferramentas instaladas (Tesseract com `por`, FFmpeg), 83 screenshots, 14 quadros de vídeo e 36 clipes coletados e catalogados em `data/raw/metadados.csv`, teste de fumaça de OCR registrado na decisão 001
- Gabarito em `data/gabarito/`: 24 itens verificados pelo autor (20 screenshots e 4 clipes) e 28 itens novos de 2026-10-07 (rascunho de IA, **a verificar**); 52 arquivos, 185 entidades, 34 relações, 51 nomes canônicos
- Ainda não existe extrator em `src/`; o estudo de viabilidade (Semanas 5–7) começa depois de fechar a coleta e congelar a ontologia

## Mapa do projeto
| Caminho | O que é |
|---|---|
| `docs/justificativa.md` | Justificativa do projeto (problema, lacuna, decisões, perguntas, métricas) |
| `docs/referencias.md` | Referências em ABNT simplificada |
| `docs/revisao/estado-da-arte.md` | O que já existe e até onde chegou |
| `docs/revisao/artigos.md` | Tabela enxuta de artigos verificados |
| `docs/revisao/correlatos.md` | Soluções correlatas |
| `docs/revisao/sintese.md` | Síntese por eixo (rascunho com citações) |
| `docs/revisao/buscas.md` | Registro das buscas feitas |
| `docs/decisoes/001-jogo-piloto.md` | Decisão do jogo-piloto |
| `docs/decisoes/002-ontologia-1-0.md` | Análise e decisões do fechamento da ontologia |
| `docs/ontologia.md` | Ontologia 1.0: tipos, relações, atributos, identidade e anti-spoiler |
| `docs/semana3.md` | Plano e estado da Semana 3 (ontologia) |
| `docs/exemplo/` | Grafo de exemplo do prólogo e o vault do Obsidian gerado a partir dele |
| `docs/semana2.md` | Plano da Semana 2: coleta e gabarito |
| `docs/gabarito.md` | Guia do gabarito (o que é, formato, regras, avaliação) |
| `docs/proximos-passos.md` | **Pendências e ordem de execução** (leia primeiro) |
| `docs/diario.md` | Diário de bordo |
| `docs/hardware.md` | Inventário de hardware (Ryzen 5 5500, 16 GB, RX 7600 8 GB, Windows 11) |
| `scripts/check_env.py` | Verifica ferramentas instaladas |
| `scripts/smoke_ocr.py` | Teste rápido de OCR (Semana 2) |
| `scripts/validar_gabarito.py` | Valida o formato e os nomes do gabarito |
| `scripts/baseline_ocr.py` | Linha de base: OCR + busca de nomes; testa o ciclo extração → avaliação |
| `src/schema.py` | Esquema de entidades e relações (ontologia v0.1) |
| `src/ontologia.json` | Ontologia legível por máquina (tipos, domínio e alcance) |
| `src/grafo.py` | Funde as anotações em um grafo único (nomes canônicos, fontes, ordem de aparição) |
| `src/exportar_vault.py` | Protótipo do exportador para vault do Obsidian |
| `eval/avaliar.py` | Calcula precisão, revocação e F1 contra o gabarito |
| `data/raw/` | Screenshots e vídeos (não versionados); `metadados.csv` cataloga cada arquivo |
| `data/gabarito/` | Anotações do gabarito real (24 JSON + `entidades.json`, verificados); `exemplo/` com 4 itens de demonstração |
| `eval/exemplo_pred/` | Previsões de exemplo para testar o avaliador |
| `eval/predicoes/` | Previsões reais (a criar na avaliação) |
| `vault_output/` | Vault gerado pelo exportador (não versionado) |

## Preparação do ambiente
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux:   source .venv/bin/activate
pip install -r requirements.txt
python scripts/check_env.py
```

## Testar o pipeline com os exemplos
Com o ambiente ativado (precisa do `pydantic`):
```bash
python scripts/validar_gabarito.py data/gabarito/exemplo
cd src && python grafo.py --gab ../data/gabarito/exemplo --saida ../grafo.json && cd ..
python src/exportar_vault.py --grafo grafo.json --saida vault_output
python eval/avaliar.py --gab data/gabarito/exemplo --pred eval/exemplo_pred
```
O `ex_003_escolhas.json` não tem previsão de exemplo, então o avaliador o ignora de propósito.
