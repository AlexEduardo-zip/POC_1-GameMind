# GameMind

Aplicativo desktop (PySide6) que lê capturas e clipes de um jogo (OCR + IA opcional) e gera um grafo de conhecimento num vault do Obsidian. Código e documentação em português.

## Regras do produto (não negociáveis)
- **Nada específico de jogo.** Nenhuma regra, lista ou exemplo no código pode vir do jogo de teste (The Witcher 3). Tudo o que é do jogo é aprendido no processamento. Em comentários, exemplos usam nomes inventados (Aldric, Ravena, Vale Alto).
- **Sem configuração prévia.** Um jogo novo funciona sem o usuário criar ou editar nada. Arquivos "manuais" (`dicionario_manual.json`, região `manual`) são opcionais e nunca necessários.
- **Um jogo não afeta outro.** Tudo o que é aprendido fica em `jogos/<jogo>/` (banco, `dicionario.json`, `regioes.json`, `resumos.json`, vault).
- **Imagens não saem do computador.** Só o Ollama local recebe imagens; IA pública recebe só texto.
- Limites e regras são relativos à própria partida (frações, percentis), não números fixos do jogo de teste.

## Estrutura
- `src/gamemind/nucleo/` — núcleo sem interface: `pipeline.py` (rodada), `dicionario.py`, `regioes.py` + `visao.py` (modelo de imagem), `consolidacao.py`, `canvas.py` (Quadro da partida), `resumos.py`, `repositorio.py` (SQLite do jogo).
- `src/gamemind/ui/` (janela) e `src/gamemind/cli.py` só chamam o núcleo.
- `src/extracao/` — OCR, gazetteer, conectores de IA (`llm.py` Ollama, `ia_publica.py`). `src/grafo.py`, `src/exportar_vault.py`.
- `tests/` — testes offline. `scripts/` — avaliações. `docs/arquitetura.md` — referência técnica.

## Ambiente (Windows)
- Python: `.venv/Scripts/python.exe` (o `python` do sistema não tem as dependências).
- Ollama: se `curl -s localhost:11434/api/tags` não responder, rode `ollama serve` em segundo plano. Modelos: `qwen2.5:7b` (texto), `qwen2.5vl:7b` (imagem). Se o Ollama devolver resposta vazia ou erro 500 seguido, `ollama stop <modelo>`.
- GPU de 8 GB: os dois modelos de 7B não cabem juntos; trocar entre eles custa ~20 s.

## Testes — escopo reduzido sempre
1. `.venv/Scripts/python.exe -m unittest discover -s tests` (~3 s) e `-m pyflakes src/gamemind` depois de toda mudança. A janela não é importada pelos testes: rode pyflakes nela.
2. Com OCR/IA de verdade: `scripts/avaliar_duplicados.py` (15 capturas de `data/raw/escopo_reduzido`, com cenas suficientes para aprender as regiões; ~3 min com IA). Experimentos próprios: **no máximo 10 capturas**, scripts no scratchpad.
3. `scripts/avaliar_aplicativo.py --conjunto reduzido` (as mesmas 15 capturas, F1 contra o gabarito) só quando o usuário pedir uma medida; `--conjunto all` nunca sem pedido.
- A IA de texto varia até ~0,04 de F1 entre rodadas iguais: compare antes/depois na mesma sessão e não conclua por uma diferença menor que isso.

## Como trabalhar aqui
- Edite código com a ferramenta Edit. Scripts Python em heredoc para substituir trechos quebram com `\n` e aspas (aconteceu várias vezes); use-os só para trocas simples, sem escapes.
- Comandos longos (avaliações, `ollama pull`) em segundo plano; não reler arquivos que acabou de editar.
- Não commitar sem pedido. `eval/` e `data/raw/` são ignorados pelo git.

## Documentação — curta
- `docs/arquitetura.md` descreve o que o sistema faz hoje, em poucas linhas por assunto. Constantes, limiares e o porquê de cada detalhe ficam no docstring do código, não na doc.
- Não colar histórico de tentativas nem tabelas de experimento. Resultado medido entra como uma linha em "Resultados" (o número final e a condição).
- README: só visão geral, instalação e comandos.

## Agentes (`.claude/agents/`)
- `testador` — testes unitários, pyflakes e `avaliar_duplicados` (escopo reduzido); devolve só o resumo.
- `avaliador-ia` — experimentos de qualidade e tempo com OCR/Ollama em até 10 capturas, comparando antes e depois.
- `revisor-generico` — revisa o diff contra as regras do produto acima.
- `documentador` — atualiza a documentação depois de uma mudança, sem poluir.
