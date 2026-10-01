# GameMind

Análise de conteúdo e construção de grafos de conhecimento a partir da jornada do jogador.
POC I / MSI I · DCC/UFMG · Aluno: Alex Eduardo Alves dos Santos · Orientador: Lucas N. Ferreira

## Estado atual
- Repositório: https://github.com/AlexEduardo-zip/POC_1-GameMind
- Fase: POC I, Semana 1 (preparação)
- Jogo-piloto: The Witcher 3

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
| `docs/decisoes/email-orientador.md` | Rascunho de e-mail ao orientador |
| `docs/checklist-semana1.md` | O que já está pronto e o que falta |
| `docs/diario.md` | Diário de bordo |
| `docs/hardware.md` | Inventário de hardware (a preencher) |
| `scripts/check_env.py` | Verifica ferramentas instaladas |
| `scripts/smoke_ocr.py` | Teste rápido de OCR (Semana 2) |
| `data/raw/` | Screenshots e vídeos (não versionados) |
| `data/gabarito/` | Anotações manuais |
| `src/`, `eval/`, `vault_output/` | Código, avaliação e vault gerado (próximas semanas) |

## Preparação do ambiente
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux:   source .venv/bin/activate
pip install -r requirements.txt
python scripts/check_env.py
```
