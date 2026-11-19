# Próximos passos

Atualizado em 2026-10-10. Única lista de pendências; o histórico está em `docs/diario.md`.

## Onde estamos no cronograma da proposta
| Semanas | Atividade | Situação |
|---|---|---|
| 1–2 | Revisão, jogo-piloto, coleta | Concluída (`docs/coleta.md`, decisão 001) |
| 3–4 | Ontologia e esquema do grafo | Concluída: ontologia 1.1 (decisão 002) |
| 5–7 | Estudo de viabilidade (screenshot, vídeo e combinação) | Concluído (`docs/estudo-viabilidade.md`) |
| 8–10 | Camada de extração | IA local feita; Claude pelo login da assinatura pronto, **sem comparação medida** (IAs por token retiradas por enquanto) |
| 11–12 | Exportação Markdown/Obsidian e JSON | Pronta (notas, canvas e `grafo.json`); falta o modelo de nota definitivo |
| 13–14 | Protótipo integrado (pasta → vault) | Pronto: aplicativo `gamemind.py`, independente de jogo (decisões 003 a 005) |
| 15 | Avaliação comparativa e ajustes | A fazer |
| 16 | Consolidação e relatório | A fazer |

## A fazer, em ordem
1. **Missões, decisões e relações sem regras de jogo.** Desde a decisão 005 o aplicativo não acha nenhum dos três. Caminhos a testar, todos sem configuração por jogo:
   - ler a tela com a posição de cada linha e deixar a IA dizer o papel de cada uma (título de missão, objetivo, opção de diálogo); o mecanismo já existe, opcional, para as regiões (`regioes.py`);
   - IA local que veja a imagem (Qwen2.5-VL, Gemma 3; não testado nesta máquina);
   - aprender as regiões pela persistência do texto entre capturas e vídeos (o que fica parado é interface; o que aparece e some é legenda).
2. **Medir em outro jogo e em telas novas.** Coletar e anotar capturas de um segundo jogo, sem mexer em regras nem prompt. É a única forma de saber se o aplicativo generaliza e o quanto os números atuais, ajustados no mesmo material, estão otimistas.
3. **Comparar o Claude com a IA local.** Rodar `python scripts/testar_conector.py claude-code` e `python scripts/avaliar_aplicativo.py --ia claude-code` e comparar acerto e tempo (`docs/ia-publica.md`).
4. **Modelo de nota definitivo** e seção do usuário preservada dentro das notas geradas.
5. **Avaliação final e relatório** (Semanas 15–16): reavaliar `evento` e `gera` (em reserva, sem nenhum caso; saem na ontologia 1.2 se continuarem sem uso) e registrar a estratégia de entrada final numa decisão.

## Pendências menores
- `scripts/check_env.py` e `scripts/validar_gabarito.py` só funcionam dentro do `.venv` (precisam de `pydantic`).
- No Obsidian, abra como vault a pasta `jogos/<jogo>/vault` (ou `vault_output/` no exemplo), não a raiz do repositório.
