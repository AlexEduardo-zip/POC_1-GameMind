# Coleta do conjunto de teste

Material coletado à mão no The Witcher 3 (pt-BR, 1920x1080), jogando normalmente. Fica em `data/raw/` (não versionado), separado em `screenshots/` e `videos/` (todos juntos em `all/`), mais `escopo_reduzido/` (cópia de 15 capturas para testar o aplicativo com rapidez), e é catalogado em `data/raw/metadados.csv` (arquivo, tipo de tela, área do jogo, ferramenta, observação, nome original, `no_gabarito`).

**Configuração é guia, não regra.** O que importa é ter material variado para testar o pipeline. Resolução, formato (JPG ou PNG), taxa de quadros, ferramenta de captura e origem (screenshot ou quadro de vídeo) não bloqueiam nada. Mantido como padrão: jogo em pt-BR (nomes do gabarito em pt-BR).

## Nomes e tipos de tela
Nomes: `img_NNN_tipo.jpg|png` e `vid_NNN_tipo.mp4` (o tipo de tela vai no nome). Tipos cobertos: diálogo, escolhas, diário, item, mapa, glossário, cutscene, HUD e exploração, quadro de avisos e tutorial. As capturas vêm da Steam e os clipes, de uma ferramenta de captura da placa de vídeo.

## Observações
- **Quadros de clipe como screenshot:** lacunas de escolhas, diário, mapa e cutscene foram fechadas extraindo quadros de clipes já coletados com `ffmpeg` (catalogados com `ferramenta = frame_de_video`). Ao comparar screenshot com vídeo, lembre que o conteúdo também existe nos clipes.
- **Privacidade:** um clipe que mostrava conversas pessoais na tela foi removido da pasta. Dois clipes de uma cena de banho mostram nudez parcial: evitar em demonstrações públicas.
- **Distribuição:** tutorial e glossário estão acima do necessário; ficam como material de observação.
- **Fora do escopo do gabarito:** Gwent e telas de tutorial.

## Do conjunto ao gabarito
Um subconjunto foi anotado à mão (`docs/gabarito.md`). O `escopo_reduzido/` tem só imagens com gabarito: telas de menu, glossário e quadro de avisos em que o mesmo nome aparece de formas diferentes, e cenas de diálogo, exploração e escolhas (para aprender as regiões de leitura).
