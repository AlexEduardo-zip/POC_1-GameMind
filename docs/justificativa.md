# Justificativa do projeto (versão enxuta)

> Citações no formato autor-data; lista completa em `docs/referencias.md`. Panorama do que já existe em `docs/revisao/estado-da-arte.md`.

## 1. Problema
Jogos longos (RPGs, aventuras) acumulam centenas de personagens, locais, missões, itens e decisões ao longo de dezenas ou centenas de horas. Como as sessões são interrompidas por dias ou semanas, o jogador esquece quem é um personagem secundário, o que resultou de uma decisão ou onde deixou um item. Os recursos disponíveis falham de formas diferentes: diários e códices dos jogos são estáticos; wikis e guias são genéricos, não refletem a partida do jogador e podem trazer spoilers; aplicativos de notas dependem de entrada manual.

## 2. Lacuna na literatura e em ferramentas
- Grafos de conhecimento já são usados em jogos, mas **para gerar conteúdo** (diálogos, missões, mundos), não para **ajudar o jogador a lembrar** (AMMANABROLU et al., 2020; ASHBY et al., 2023; NANANUKUL; WONGKAMJAN, 2024). Nananukul e Wongkamjan, por exemplo, montam o grafo a partir de wikis de fãs, e Ammanabrolu et al. a partir de enredos de livros.
- Ferramentas que transformam screenshots em notas existem (plugins do Obsidian), mas não constroem um grafo de entidades de jogo nem tratam spoilers.
- Há pesquisa em análise de gameplay com OCR e modelo de linguagem, mas voltada à acessibilidade (pôster Argus, Graphics Interface 2026), não à memória do jogador.
- Resultado: entre os trabalhos consultados, não há uma solução que parta do **conteúdo que o jogador já viu** para montar uma memória persistente e consultável.

## 3. Proposta
O GameMind analisa screenshots e trechos de vídeo da própria gameplay, extrai entidades e relações e as organiza em um grafo exportado como vault Markdown do Obsidian (mais JSON). Nesta fase (POC I) o foco é a **camada de análise**; captura automática e empacotamento ficam para o POC II.

## 4. Por que cada decisão de projeto
| Decisão | Justificativa |
|---|---|
| Grafo de conhecimento | Os elementos de um jogo têm relações naturais (personagem participa de missão, missão ocorre em local, decisão gera consequência) (EHRLINGER; WÖSS, 2016; JI et al., 2021) |
| Esquema simples e fixo | LLMs permitem extração com ou sem esquema (BIAN, 2025); um esquema pequeno facilita extrair, validar e avaliar |
| Comparar imagem, vídeo e combinação | Vídeo guarda contexto temporal, mas custa mais; modelos de linguagem para vídeo avançaram (TANG et al., 2023), então a escolha deve ser medida, não presumida |
| Mais de um motor de OCR | Texto de cena exige detecção e reconhecimento com aprendizado profundo, com desafios em aberto (LONG; HE; YAO, 2021); o Tesseract (SMITH, 2007) é o ponto de partida, mas fontes e fundos de jogos podem exigir alternativas |
| IA local por padrão, pública opcional | Privacidade e ausência de custo recorrente; a nuvem é alternativa com credenciais do usuário |
| Obsidian/Markdown | Dispensa criar um visualizador de grafo e é um formato aberto e portátil (OBSIDIAN, 2026) |
| Processamento assíncrono | Evita competir por CPU/GPU com o jogo; simplifica o escopo |
| Jogo-piloto The Witcher 3 | Muitas decisões com consequência, rede densa de personagens, locais e missões, e diário e glossário no jogo que ajudam a montar o gabarito |

## 5. Perguntas que o POC I responde
1. Screenshots, vídeo por amostragem de quadros ou a combinação: qual extrai melhor, com que custo de tempo e hardware?
2. IA local ou pública: quanto se perde (ou ganha) em precisão?
3. Um esquema simples de entidades e relações é suficiente para representar a jornada do jogador no jogo-piloto?

## 6. Como será medido
- Precisão, revocação e F1 de entidades e relações contra o gabarito anotado à mão.
- Tempo de processamento por item.
- Requisitos de hardware (memória, VRAM).
- Taxa de saídas inválidas (JSON fora do esquema).

## 7. Limitações assumidas
- Um único jogo-piloto e conjunto de teste pequeno, coletado manualmente.
- Gabarito feito por uma pessoa.
- Sem avaliação com jogadores reais (planejada para o POC II).

## 8. Parágrafo curto (para introdução ou resumo)
Jogos eletrônicos de longa duração acumulam informações narrativas que o jogador tende a esquecer entre sessões, e os recursos atuais (diários, wikis e aplicativos de notas) são estáticos, genéricos ou manuais. Embora grafos de conhecimento já sejam usados em jogos para gerar missões e diálogos (ASHBY et al., 2023; NANANUKUL; WONGKAMJAN, 2024), eles raramente são construídos a partir do que o próprio jogador viu. O GameMind propõe analisar screenshots e vídeos da gameplay e organizá-los em um grafo de conhecimento consultável, exportado como vault do Obsidian, com IA local por padrão. Esta etapa avalia a viabilidade da camada de análise.
