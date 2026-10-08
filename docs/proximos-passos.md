# Próximos passos (fonte única do que falta)

Atualizado em 2026-10-07. Este arquivo é o único lugar com a lista de pendências; `semana2.md`, `semana3.md` e o `diario.md` guardam só histórico. Ao concluir um item, marque aqui e registre uma linha no diário.

## Onde estamos no cronograma da proposta
| Semanas | Atividade da proposta | Situação |
|---|---|---|
| 1–2 | Revisão, jogo-piloto, coleta | Concluída (falta só o aval do orientador, A1) |
| 3–4 | Ontologia e esquema do grafo | v0.1 pronta e testada nos 24 itens do gabarito; falta congelar a 1.0 |
| 5–7 | Estudo de viabilidade (screenshot × vídeo × combinação) | Não iniciada; é o passo B abaixo |
| 8–10 | Camada de extração (IA local + IA pública opcional) | Não iniciada (`src/` ainda não tem extrator) |
| 11–12 | Exportação Markdown/JSON | Protótipo pronto (`src/grafo.py`, `src/exportar_vault.py`) |

## A. Fechar a ontologia e o aval (bloqueia o resto)
Semana 2 concluída em 2026-10-07: coleta, gabarito e pipeline testado (ver `docs/semana2.md`). Formato e fonte do material são só guia.

| # | Tarefa | Critério de pronto |
|---|---|---|
| A1 | Enviar o e-mail ao orientador com a decisão 001 e registrar o retorno | Campo "Validado com o orientador em" preenchido |
| A2 | Abrir `docs/exemplo/vault` (ou `vault_output/`) no Obsidian e ver o grafo | Conferido por você; ajustes anotados no diário |
| A3 | Revisar as 5 decisões presumidas de `docs/ontologia.md`, usar `evento`, `gera`, `concede`, `obtido_em` em pelo menos uma tela cada (ou decidir removê-los) e **congelar a ontologia 1.0** | `ontologia.md`, `src/ontologia.json` e `src/schema.py` com versão 1.0 e o validador passando |
| A4 | Reavaliar a regra 9 do gabarito (personagem só com nome escrito na tela): é o ponto que mais afeta a revocação | Decisão registrada em `gabarito.md`; se mudar, reanotar os itens afetados |
| A5 | (Opcional) Anotar do material novo (`img_057` a `img_097`, `vid_029` a `vid_037`) para ampliar o gabarito, principalmente escolhas (`img_084` a `img_087`), diário, mapa e quadros de avisos | `validar_gabarito.py data/gabarito` com 0 problemas e verificação humana |

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
