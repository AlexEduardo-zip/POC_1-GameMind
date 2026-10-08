# Próximos passos

Atualizado em 2026-10-08. Única lista de pendências; o histórico está em `docs/diario.md` e os resultados em `docs/resumo-do-projeto.md`.

## Onde estamos no cronograma da proposta
| Semanas | Atividade | Situação |
|---|---|---|
| 1–2 | Revisão, jogo-piloto, coleta | Concluída (`docs/coleta.md`, `docs/decisoes/001-jogo-piloto.md`) |
| 3–4 | Ontologia e esquema do grafo | Concluída: ontologia 1.1 congelada (`docs/decisoes/002-ontologia-1-0.md`) |
| 5–7 | Estudo de viabilidade (screenshot, vídeo e combinação) | Feito, com conclusão provisória (`docs/estudo-viabilidade.md`) |
| 8–10 | Camada de extração: IA local feita; **IA pública opcional falta** | Em andamento |
| 11–12 | Exportação Markdown/Obsidian e JSON | Protótipo pronto (`src/grafo.py`, `src/exportar_vault.py`); falta o modelo de nota definitivo |
| 13–14 | Protótipo integrado (pasta de teste → vault) | A fazer: hoje são scripts separados |
| 15 | Avaliação comparativa e ajustes | A fazer, com material novo |
| 16 | Consolidação e relatório | A fazer |

## A fazer, em ordem
1. **Medida em telas novas.** Capturar e anotar telas novas (sem mexer em regras, prompt e filtros) e rodar o pipeline: é a única forma de saber o quanto os números atuais, calibrados nas mesmas imagens, estão otimistas.
2. **IA pública como back-end alternativo** (Semanas 8–10): segunda implementação de `Backend` em `src/extracao/llm.py`, credenciais do próprio usuário por `.env` (já ignorado pelo git), e comparação com o local em F1, tempo e custo.
3. **Melhorar os pontos fracos**, em ordem de ganho esperado:
   - relações (F1 0,40): recompensa de missão (`obtido_em`, hoje 0) com leitura melhor do banner; vizinhança entre nome e frase no vídeo;
   - item (0,50) e local fora do dicionário (0,69);
   - HUD e mapa (0,61): recorte próprio para rótulos de mapa e opções de diálogo.
4. **Protótipo integrado** (Semanas 13–14): um comando que recebe uma pasta de imagens e clipes e gera o vault (hoje: `rodar_extracao`, `rodar_llm`, `rodar_video`, `grafo`, `exportar_vault`). Incluir contexto de sessão (missão ativa do HUD ligando decisões e itens a missões) e o modelo de nota definitivo.
5. **Avaliação final e relatório** (Semanas 15–16): reavaliar `evento` e `gera` (em reserva, sem nenhum caso; saem na ontologia 1.2 se continuarem sem uso) e registrar a estratégia de entrada final em `docs/decisoes/003-estrategia-de-entrada.md`.

## Pendências menores
- `scripts/check_env.py` e `scripts/validar_gabarito.py` só funcionam dentro do `.venv` (precisam de `pydantic`).
- No Obsidian, abrir `vault_output/` (e não a raiz do repositório) como vault; `workspace.json` e `graph.json` do Obsidian são estado local.
