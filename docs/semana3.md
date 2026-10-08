# Semana 3: ontologia

**Objetivo:** fechar os tipos, as relações e o esquema do grafo antes de anotar o gabarito em massa.
**Estado:** concluída. Ontologia congelada como 1.0 em 2026-10-08 (`docs/decisoes/002-ontologia-1-0.md`); este arquivo é só histórico.

## Já pronto
- ✅ `docs/ontologia.md`: tipos, relações, atributos, identidade, anti-spoiler e decisões presumidas
- ✅ `src/ontologia.json` e `src/schema.py`: versão legível por máquina (mantidos em sincronia pelo validador)
- ✅ `scripts/validar_gabarito.py`: confere formato, nomes, tipos e domínio e alcance dos predicados
- ✅ `src/grafo.py`: funde as anotações do gabarito em um grafo único (nomes canônicos, fontes, `primeira_vez`)
- ✅ `src/exportar_vault.py` (protótipo): grafo em notas do Obsidian
- ✅ `docs/exemplo/`: grafo do prólogo (16 nós e 17 arestas) e o vault gerado a partir dele

Pipeline testado com os exemplos (2026-10-05, no `.venv`; fora dele falta o `pydantic`):
```bash
python scripts/validar_gabarito.py data/gabarito/exemplo
cd src && python grafo.py --gab ../data/gabarito/exemplo --saida ../grafo.json && cd ..
python src/exportar_vault.py --grafo grafo.json --saida vault_output
python eval/avaliar.py --gab data/gabarito/exemplo --pred eval/exemplo_pred
```
Resultado: validador sem problemas em 4 arquivos; o grafo do prólogo em `docs/exemplo/` tem 16 nós e 17 arestas.

## Para você
1. ☐ Abrir `docs/exemplo/vault` como vault no Obsidian e olhar a visualização de grafo (em Groups, crie um grupo por tag, como `tag:#personagem`).
2. ☐ Revisar as 5 decisões presumidas em `docs/ontologia.md` e dizer o que muda.
3. ✅ Telas da Semana 2 anotadas (24 itens, 2026-10-07). A ontologia cobriu o que apareceu: 85 entidades e 24 relações couberam nos 7 tipos e 8 predicados. Ficaram de fora só facções (Nilfgaard, Caçada Selvagem), Gwent e categorias do bestiário, já previstos como fora do escopo. Faltou testar `evento`, que nenhum item usou, e `gera`/`concede`/`obtido_em`, sem exemplo no subconjunto.
4. ☐ Congelar a versão 1.0 antes de anotar o gabarito em massa.

## Próximo passo (Semana 4)
Fechar o esquema JSON e o modelo de nota; o exportador já é um ponto de partida.
