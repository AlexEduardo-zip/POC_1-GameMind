# GameMind

Análise de conteúdo e construção de grafos de conhecimento a partir da jornada do jogador.
POC I / MSI I · DCC/UFMG · Aluno: Alex Eduardo Alves dos Santos · Orientador: Lucas N. Ferreira
Repositório: https://github.com/AlexEduardo-zip/POC_1-GameMind

O GameMind lê o que o jogador já viu na tela (screenshots e clipes), aprende os nomes do jogo e, com IA local, extrai entidades e relações, que organiza em um grafo exportado como vault do Obsidian. O aplicativo **não tem configuração prévia nem específica de jogo**; o estudo de viabilidade que deu origem a ele foi feito com The Witcher 3 (pt-BR). Captura automática e empacotamento ficam para o POC II.

## Estado (2026-10-10)
- **Estudo de viabilidade concluído** com The Witcher 3 (conclusões em `docs/estudo-viabilidade.md`).
- **Aplicativo** (janela, linha de comando e núcleo) independente de jogo. Teste geral (todas as screenshots e vídeos, 133 mídias): só com OCR acha 30 de cada 100 entidades do gabarito (e acerta 63 das que aponta); com a IA local, 61 (e acerta 60), mais as primeiras ligações. Ainda não acha missões nem decisões (decisão 005). Resultados completos em `docs/arquitetura.md`, seção 10; os vaults gerados ficam em `eval/vaults/`.
- Pendências em `docs/proximos-passos.md`.

## Documentação
| Documento | Para quê |
|---|---|
| `docs/visao-geral.md` | **Comece aqui**: o que o aplicativo faz, modos, tempo e custo, em linguagem simples |
| `docs/arquitetura.md` | Arquitetura do aplicativo: módulos, rodada de processamento, dados, interface e como medir |
| `docs/estudo-viabilidade.md` | Conclusões do estudo de viabilidade (POC I) |
| `docs/decisoes/` | Decisões: 001 jogo-piloto, 002 ontologia, 003 aplicativo, 004 dicionário aprendido, 005 sem configuração por jogo |
| `docs/ontologia.md` | Ontologia 1.1 (tipos e relações) |
| `docs/coleta.md`, `docs/gabarito.md` | Material coletado; regras de anotação do gabarito |
| `docs/ia-publica.md` | Configurar a IA pública (OpenAI, Gemini, Claude) |
| `docs/hardware.md` | Hardware e requisitos de GPU |
| `docs/justificativa.md`, `docs/referencias.md`, `docs/revisao/` | Justificativa, referências e revisão da literatura |
| `docs/proximos-passos.md`, `docs/diario.md` | Pendências; diário de bordo |

## Código e dados
| Caminho | O que é |
|---|---|
| `gamemind.py`, `src/gamemind/` | Aplicativo: núcleo sem interface (`nucleo/`), janela PySide6 (`ui/`) e linha de comando |
| `src/extracao/` | OCR e recortes, dicionário (busca de nomes), LLM com validação, conector de IA pública e vídeo |
| `src/schema.py`, `src/ontologia.json`, `src/grafo.py`, `src/exportar_vault.py` | Esquema e ontologia; grafo único e exportador para o Obsidian |
| `tests/` | Testes offline do núcleo e do conector (`python -m unittest discover -s tests`) |
| `scripts/` | `avaliar_aplicativo.py` (mede o app contra o gabarito: conjunto `all` ou `reduzido`), `testar_conector.py`, `validar_gabarito.py`, `check_env.py` |
| `eval/avaliar.py` | Precisão, revocação e F1 (total e por tipo) contra o gabarito |
| `data/raw/` | Material coletado (não versionado): `teste_reduzido/`, `screenshots/`, `videos/` e `metadados.csv` |
| `data/gabarito/` | Gabarito verificado do jogo-piloto (+ `exemplo/`): material de medida, não é usado pelo aplicativo |

## Ambiente
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    Linux: source .venv/bin/activate
pip install -r requirements-app.txt     # requirements.txt + PySide6 (só a janela precisa do PySide6)
python scripts/check_env.py             # precisa também de Tesseract (com o idioma dos seus jogos), FFmpeg e, para a IA local, Ollama
```

## Aplicativo
```bash
python gamemind.py                        # janela: Novo jogo, escolha a pasta de capturas e clique em Processar só OCR ou Processar com IA
python gamemind.py diagnostico            # verifica Tesseract, FFmpeg e a IA configurada
python gamemind.py processar --jogo "Meu jogo" --pasta "<pasta de capturas>" [--ia ollama] [--observar]
```
Cada jogo fica em `jogos/<jogo>/`, ao lado do programa: banco SQLite, nomes aprendidos, regiões de leitura, grafo e o `vault/` do Obsidian (o botão **Abrir no Obsidian** abre essa pasta). No vault, `Quadro da partida.canvas` mostra o mundo (uma coluna por lugar, com as capturas), e as notas de personagens, lugares, facções e criaturas levam ao canvas de contexto de cada um.

## Testar o grafo e o vault com os exemplos
```bash
python scripts/validar_gabarito.py data/gabarito/exemplo
cd src && python grafo.py --gab ../data/gabarito/exemplo --saida ../grafo.json && cd ..
python src/exportar_vault.py --grafo grafo.json --saida vault_output
python eval/avaliar.py --gab data/gabarito/exemplo --pred eval/exemplo_pred
```
O `ex_003_escolhas.json` não tem previsão de exemplo, então o avaliador o ignora de propósito.
