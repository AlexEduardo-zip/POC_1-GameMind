# Estado da arte: o que já existe e até onde chegou

> Baseado em resumo, introdução e conclusões/direções futuras dos trabalhos consultados. Busca enxuta, não exaustiva.

| Área | O que já existe | Até onde chegou | O que falta para o GameMind |
|---|---|---|---|
| Construção de grafos com LLM | Pipeline em três etapas: ontologia, extração e fusão; extração com e sem esquema (BIAN, 2025) | Maduro para texto; memória dinâmica para agentes e grafos multimodais aparecem como direções futuras | Aplicar a conteúdo visual de gameplay |
| OCR em cenas | Detecção e reconhecimento com aprendizado profundo; Tesseract como motor clássico (LONG; HE; YAO, 2021; SMITH, 2007) | Bom em imagens estáticas, com desafios ainda abertos; vídeo fica em outra literatura (JUNG; KIM; JAIN, 2004) | Testar em fontes estilizadas e fundos variáveis de jogos |
| Vídeo com LLM | Modelos que raciocinam sobre vídeo, com tarefas, benchmarks e limitações resumidas (TANG et al., 2023) | Avançado, porém pesado | Ver se cabe em hardware doméstico (8 GB de VRAM) |
| Grafos em jogos | Grafo parcial extraído de enredos de livros para gerar mundos de jogos de texto (AMMANABROLU et al., 2020); grafo e LLM para missões e diálogos em RPG (ASHBY et al., 2023); triplas montadas a partir de wikis para diálogos em Final Fantasy VII Remake e Pokémon (NANANUKUL; WONGKAMJAN, 2024) | O grafo serve para **gerar** conteúdo, a partir de texto ou wikis | Partir do que **o jogador viu** (screenshots e vídeo) |
| Análise de gameplay | Pôster Argus (Graphics Interface 2026): segmentação, OCR e LLM sobre gameplay | Protótipo de pesquisa para acessibilidade | Sem grafo nem memória do jogador |
| Notas com IA | Plugins do Obsidian que transformam screenshots em notas (Vision Recall, Note Maker AI) | Funcionam para imagens genéricas | Sem esquema de jogo, sem grafo de entidades, sem tratamento de spoiler |

## Conclusão
As peças existem separadas: extração de grafos com LLM, OCR, modelos de vídeo, grafos em jogos e notas no Obsidian. Entre os trabalhos consultados, nenhum as combina para montar uma memória do jogador a partir da própria gameplay. O GameMind é essa integração, com IA local por padrão.
