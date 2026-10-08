# Próximos passos (fonte única do que falta)

Atualizado em 2026-10-07. Este arquivo é o único lugar com a lista de pendências; `semana2.md`, `semana3.md` e o `diario.md` guardam só histórico. Ao concluir um item, marque aqui e registre uma linha no diário.

## Onde estamos no cronograma da proposta
| Semanas | Atividade da proposta | Situação |
|---|---|---|
| 1–2 | Revisão, jogo-piloto, coleta | Concluída |
| 3–4 | Ontologia e esquema do grafo | Concluída: ontologia 1.1 congelada em 2026-10-08 (decisão 002 e emenda) |
| 5–7 | Estudo de viabilidade (screenshot × vídeo × combinação) | Não iniciada; é o passo B abaixo |
| 8–10 | Camada de extração (IA local + IA pública opcional) | Não iniciada (`src/` ainda não tem extrator) |
| 11–12 | Exportação Markdown/JSON | Protótipo pronto (`src/grafo.py`, `src/exportar_vault.py`) |

## A. Pendências antes do estudo de viabilidade
Semana 2 concluída em 2026-10-07 e ontologia 1.1 congelada em 2026-10-08 (decisão 002 e emenda 1: `faccao` e `membro_de`).

| # | Tarefa | Situação |
|---|---|---|
| A1 | Abrir `vault_output/` no Obsidian e conferir o grafo | **Feito** em 2026-10-08 (grafo visível; vault com 60 notas) |
| A2 | **Verificar** o gabarito novo | **Feito** em 2026-10-08: gabarito verificado pelo autor e confirmado correto (roteiro em `docs/verificacao-gabarito.md`) |
| A3 | Ampliar o gabarito onde a ontologia ficou sem teste | **Feito** em 2026-10-08: clipes novos `vid_029` a `vid_037` anotados e verificados, com missão atualizada (`vid_036`), recompensa (`img_080`), diário e mapa em vídeo. `evento` e `gera` seguem sem nenhum caso real (não há consequência nem acontecimento visível nas telas coletadas) e continuam em reserva |
| A4 | Relatório de F1 por tipo de entidade, por predicado e por tipo de tela, com `evento`/`gera` à parte | **Feito**: `eval/avaliar.py` (ver abaixo) |

Resultado da linha de base com a quebra (50 screenshots; clipes ainda sem previsão), em 2026-10-08:

| Tipo de entidade | Gabarito | Precisão | Revocação | F1 |
|---|---|---|---|---|
| personagem | 94 | 0,98 | 0,91 | 0,95 |
| faccao | 11 | 1,00 | 1,00 | 1,00 |
| criatura | 12 | 1,00 | 0,92 | 0,96 |
| local | 38 | 0,90 | 0,74 | 0,81 |
| item | 12 | 0,67 | 0,67 | 0,67 |
| decisao | 3 | 1,00 | 0,67 | 0,80 |
| missao | 18 | 0,88 | 0,39 | 0,54 |
| **média simples** | | 0,92 | 0,76 | 0,82 |
| **micro (total)** | | 0,94 | 0,81 | 0,87 |

Leituras: (1) o micro (0,87) esconde que **missão** (0,54) e **item** (0,67) são os tipos fracos, e o dicionário vindo do gabarito (vazamento) ainda favorece todos eles; (2) por tipo de tela, o ponto fraco é HUD (0,00, nenhum nome achado), mapa (0,48) e diálogo (0,70), enquanto glossário (0,96) e quadro de avisos (1,00) saem quase perfeitos; (3) relações: nenhuma, porque a linha de base não extrai relações, o que fixa o alvo do extrator da etapa B; (4) a média simples entre tipos é a medida a reportar junto com o micro.

## B. Estudo de viabilidade (Semanas 5–7)
Ordem sugerida, cada passo gera um número comparável com `eval/avaliar.py`:
1. ✅ **Extrator de OCR de base** (feito em 2026-10-08): `src/extracao/` (`ocr.py`, `gazetteer.py`), `scripts/rodar_extracao.py` e dicionário independente em `data/gazetteer/`. Resultado: F1 de entidades 0,76 (micro) nas 50 screenshots, contra 0,87 da linha de base com vazamento; relações 0. Registro e leituras em `docs/estudo-viabilidade.md`.
2. ✅ **Pré-processamento** (feito em 2026-10-08): recorte e filtro de brilho em legenda, HUD e avisos (`rois_brilho`); cobertura de nomes no texto do OCR 0,81 → 0,89, diálogo 0,53 → 0,87, 2,1 s por imagem. Detalhes em `docs/estudo-viabilidade.md`. **Próximo: B3a.**
3. ✅ **(parte a, feita em 2026-10-08)** extração estruturada por tipo de tela: missão 0,00 → 0,89 e decisão 0,00 → 1,00 (F1 micro 0,84; 3,08 s por imagem), detalhes em `docs/estudo-viabilidade.md`. **B3b feita em 2026-10-08** (itens por ficha, relações estruturais e LLM local em cascata: entidades F1 0,89, relações 0,44; ver `docs/estudo-viabilidade.md`). **Próximo: B4 (vídeo).** Plano geral do passo: **Texto → entidades e relações** (`src/extracao/`, interface comum de back-end que devolve o formato de `src/schema.py`): primeiro regras/dicionário a partir de `entidades.json`, depois LLM local via Ollama (modelos de 7–8B, ver `docs/hardware.md`).
4. **Vídeo**: amostrar quadros com FFmpeg/OpenCV a cada 1–2 s e rodar o mesmo extrator; depois unir as entidades dos quadros por clipe.
5. **Combinação**: screenshot + vídeo do mesmo trecho.
6. Gravar previsões em `eval/predicoes/<estrategia>/` (um JSON por item, mesmo nome do gabarito) e rodar:
   ```bash
   python eval/avaliar.py --gab data/gabarito --pred eval/predicoes/<estrategia> --csv eval/resultados_<estrategia>.csv --csv-quebras eval/quebras_<estrategia>.csv
   python eval/avaliar.py --gab data/gabarito --pred eval/predicoes/<estrategia> --sem-tipo
   ```
7. Anotar para cada rodada: estratégia, back-end, modelo, tempo total, memória/VRAM, F1 de entidades e de relações. Registrar cada rodada em `docs/estudo-viabilidade.md` e, no fim, a conclusão em `docs/decisoes/003-estrategia-de-entrada.md`.

## C. Depois (fora do que já está definido)
- IA pública opcional (Semanas 8–10): mesma interface de back-end, credenciais do próprio usuário por `.env` (já ignorado pelo git).
- Exportador definitivo e modelo de nota (Semanas 11–12): partir de `src/exportar_vault.py`.
- Integração, avaliação comparativa final e relatório (Semanas 13–16).

## Pendências menores
- `scripts/check_env.py` e `validar_gabarito.py` só funcionam dentro do `.venv` (precisam de `pydantic`).
