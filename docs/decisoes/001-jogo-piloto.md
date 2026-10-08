# Decisão 001 · Jogo-piloto

- Data: 2026-10-01 (confirmada pelo teste de OCR de 2026-10-07)
- **Jogo escolhido: The Witcher 3**, em português do Brasil
- Candidatos considerados: Skyrim e The Witcher 3 (pontuação: Witcher 3 = 73, Skyrim = 61, parcial, sem o critério de acesso e tempo)
- Motivos: narrativa com decisões e consequências, rede densa de personagens, locais e missões, diário e glossário no próprio jogo, suporte ao português
- Riscos que se confirmaram: legibilidade do OCR sobre legendas com fundo variável e sobre o HUD (texto pequeno); acentos de pt-BR não foram problema (o Tesseract tem o idioma `por`)
- Captura: pt-BR, 1920x1080; Steam (F12) e AMD Adrenalin; resolução, formato e ferramenta são só guia (`docs/coleta.md`)

## O que o teste de OCR mostrou (2026-10-07, Tesseract `por+eng`, imagem inteira, sem pré-processamento)
| Tipo de tela | OCR |
|---|---|
| Glossário, diário, tutorial, quadro de avisos | bom: nomes próprios quase sem erro |
| Inventário e mapa | médio: ruído de estatísticas e ícones; rótulos pequenos se perdem |
| Diálogo com legenda | médio a ruim: legenda longa ou sobre cena clara falha |
| Exploração e HUD | ruim: fonte pequena sobre cena clara |
| Cutscene sem legenda | nada (esperado) |

Leitura: o jogo-piloto se confirma para telas de menu; o ponto fraco é legenda em cena e HUD, o que justificou o pré-processamento por recortes e o vídeo por quadros. O estudo completo está em `docs/estudo-viabilidade.md`.

## Pontuação detalhada (estimativa inicial)
| Critério (peso) | Witcher 3 | Skyrim |
|---|---|---|
| Riqueza narrativa (3) | 5 | 3 |
| Texto na tela (3) | 4 | 4 |
| Legibilidade para OCR (3) | 4 | 4 |
| Diversidade de entidades (2) | 5 | 4 |
| Facilidade de captura (2) | 4 | 4 |
| Idioma do texto (2) | 5 | 3 |
| Dependência de áudio (1) | 3 | 3 |
| Risco de spoiler (1) | 3 | 3 |
