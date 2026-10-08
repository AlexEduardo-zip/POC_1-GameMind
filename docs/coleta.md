# Coleta do conjunto de teste

Material coletado à mão no The Witcher 3 (pt-BR, 1920x1080) entre 2026-10-05 e 2026-10-08, jogando normalmente. Fica em `data/raw/` (não versionado) e é catalogado em `data/raw/metadados.csv` (arquivo, tipo de tela, área do jogo, ferramenta, observação, nome original, `no_gabarito`).

**Configuração é guia, não regra.** O que importa é ter material variado para testar o pipeline. Resolução, formato (JPG ou PNG), taxa de quadros, ferramenta (Steam F12, AMD Adrenalin) e origem (screenshot ou quadro de vídeo) não bloqueiam nada; os desvios ficam no catálogo. Mantido como padrão: jogo em pt-BR (nomes do gabarito em pt-BR).

## O que há
Nomes: `img_NNN_tipo.jpg|png` e `vid_NNN_tipo.mp4` (o tipo de tela vai no nome).

| Origem | Quantidade | Detalhe |
|---|---|---|
| Screenshots | 83 | Steam, JPG 1920x1080 (`img_001` a `img_083`) |
| Quadros extraídos de clipes | 14 | PNG, com `ferramenta = frame_de_video` e a origem em `nome_original` (`img_084` a `img_097`: escolhas, diário, mapa, cutscene) |
| Clipes | 36 | AMD Adrenalin, MP4 de 22 a 60 s, 1920x1088 a 60 fps (`vid_001` a `vid_037`, sem `vid_028`) |

Cobertura por tipo de tela (screenshots + quadros de clipe / clipes): diálogo 7 / 23 · escolhas 4 / 2 · diário 6 / 1 · item 10 / 0 · mapa 6 / 1 · glossário 15 / n/a · cutscene 4 / 2 · HUD e exploração 6 / 7 · quadro de avisos 6 / 0 (tipo extra) · tutorial 33 / 0 (extra, fora do gabarito).

## Observações
- **Quadros de clipe como screenshot:** as lacunas de escolhas, diário, mapa e cutscene foram fechadas extraindo 14 quadros de clipes já coletados com `ffmpeg`. Servem para testar o pipeline; no estudo "screenshot × vídeo" convém lembrar que o conteúdo também existe nos clipes (filtre por `ferramenta = frame_de_video`). `img_089` e `img_090` são quase idênticas.
- **Privacidade:** `vid_028_cutscene` mostrava WhatsApp Web (conversas pessoais) nos primeiros ~30 s e foi removido da pasta; a linha no catálogo está marcada. Os clipes `vid_001` e `vid_002` (cena do banho) mostram nudez parcial: evitar em demonstrações públicas.
- **Duplicatas:** 9 cópias idênticas (5 JPG e 4 MP4 com o nome original) foram apagadas em 2026-10-08.
- **Distribuição:** tutorial (33 imagens) e glossário (15) estão acima do necessário; ficam como material de observação.
- **Fora do escopo do gabarito:** Gwent (`img_067_item`) e telas de tutorial.

## Do conjunto ao gabarito
Subconjunto anotado: 50 imagens e 13 clipes (`docs/gabarito.md`). Teste de fumaça do OCR (2026-10-07) e depois o estudo completo em `docs/estudo-viabilidade.md`.
