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

| # | Tarefa | Critério de pronto |
|---|---|---|
| A1 | Abrir `vault_output/` no Obsidian e conferir o grafo | Conferido; ajustes anotados no diário |
| A2 | **Verificar** os itens de gabarito novos (28 de 2026-10-07, `img_080`, `img_071` e as facções reanotadas em 11 itens; lista em `docs/gabarito.md`), revisando 5 sorteados | Verificação registrada; `validar_gabarito.py data/gabarito` com 0 problemas |
| A3 | Ampliar o gabarito onde a ontologia ficou sem teste: telas de recompensa, notificação de missão atualizada, cenas com consequência visível, clipes novos (`vid_029` a `vid_037`) | Pelo menos 1 caso de `concede`, `obtido_em` e, se existir, `evento`/`gera` além dos atuais |
| A4 | Na avaliação, relatar F1 por tipo de tela e por tipo de entidade (o glossário domina o micro) e tratar `evento`/`gera` à parte | `eval/avaliar.py` com a quebra por tipo |

## B. Estudo de viabilidade (Semanas 5–7)
Ordem sugerida, cada passo gera um número comparável com `eval/avaliar.py`:
1. **Extrator de OCR de base** em `src/extracao/ocr.py`: imagem → texto bruto (Tesseract `por+eng`). Ponto de partida: `scripts/baseline_ocr.py` (F1 de entidades 0,83 nas screenshots, mas com vazamento: o dicionário vem do gabarito; relações 0). O dicionário deve vir de fora do gabarito para a medida valer.
2. **Pré-processamento**: recorte da faixa da legenda e do HUD, ampliação, binarização. Medir o ganho nos tipos de tela que a decisão 001 classificou como "médio a ruim".
3. **Texto → entidades e relações** (`src/extracao/`, interface comum de back-end que devolve o formato de `src/schema.py`): primeiro regras/dicionário a partir de `entidades.json`, depois LLM local via Ollama (modelos de 7–8B, ver `docs/hardware.md`).
4. **Vídeo**: amostrar quadros com FFmpeg/OpenCV a cada 1–2 s e rodar o mesmo extrator; depois unir as entidades dos quadros por clipe.
5. **Combinação**: screenshot + vídeo do mesmo trecho.
6. Gravar previsões em `eval/predicoes/<estrategia>/` (um JSON por item, mesmo nome do gabarito) e rodar:
   ```bash
   python eval/avaliar.py --gab data/gabarito --pred eval/predicoes/<estrategia> --csv eval/resultados_<estrategia>.csv
   python eval/avaliar.py --gab data/gabarito --pred eval/predicoes/<estrategia> --sem-tipo
   ```
7. Anotar para cada rodada: estratégia, back-end, modelo, tempo total, memória/VRAM, F1 de entidades e de relações. Registrar o resultado e a conclusão em `docs/decisoes/002-estrategia-de-entrada.md`.

## C. Depois (fora do que já está definido)
- IA pública opcional (Semanas 8–10): mesma interface de back-end, credenciais do próprio usuário por `.env` (já ignorado pelo git).
- Exportador definitivo e modelo de nota (Semanas 11–12): partir de `src/exportar_vault.py`.
- Integração, avaliação comparativa final e relatório (Semanas 13–16).

## Pendências menores
- `scripts/check_env.py` e `validar_gabarito.py` só funcionam dentro do `.venv` (precisam de `pydantic`).
