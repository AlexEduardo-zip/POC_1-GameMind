# Decisão 001 · Jogo-piloto

- Data: 2026-10-01
- Jogo escolhido: The Witcher 3
- Candidatos considerados: Skyrim, The Witcher 3
- Pontuação (resumo): Witcher 3 = 73, Skyrim = 61 (parcial, sem o critério de acesso e tempo)
- Motivos da escolha: narrativa com decisões e consequências, rede densa de personagens, locais e missões, diário e glossário no jogo, suporte a português
- Riscos conhecidos: legibilidade do OCR sobre as legendas (fundo variável) e nomes próprios; a confirmar
- Teste de fumaça de OCR (2026-10-07): feito com Tesseract 5.5 (`por+eng`) nas 56 screenshots coletadas. Resultado abaixo.
- Configuração de captura (2026-10-05): jogo em pt-BR, 1920x1080, screenshots pela tecla F12 da Steam, vídeos em 1080p/30 fps/MP4 pelo OBS Studio ou clipe do último minuto pelo AMD Adrenalin
- Risco novo: OCR em pt-BR (acentos nos nomes próprios). O Tesseract tem o idioma `por`; os acentos saem corretos (ex.: "Missão", "Glossário", "Yennefer de Vengerberg")

## Resultado do teste de fumaça de OCR (2026-10-07)
Método: `pytesseract` com `por+eng`, imagem inteira, sem pré-processamento, em todas as 56 screenshots (1920x1080).

| Tipo de tela | Resultado do OCR | Observação |
|---|---|---|
| Glossário (personagens, bestiário, tutorial) | Bom | Texto longo e nomes próprios quase sem erro; os nomes da lista lateral saem fora de ordem |
| Diário de missões | Bom | Título, objetivos e descrição legíveis; a coluna de objetivos mistura com o texto |
| Tutorial em caixa (incl. Gwent) | Bom | Texto claro sobre fundo escuro; é o tipo de tela mais fácil |
| Inventário | Médio | Nome e descrição do item saem, mas com ruído das estatísticas e dos ícones |
| Mapa | Médio | Título da região e marcadores saem; rótulos pequenos sobre o terreno se perdem |
| Diálogo com legenda | Médio a ruim | Legenda curta sobre fundo escuro sai bem; legenda longa ou sobre cena clara tem erros ("Arbustira" por "Arbusteira") e às vezes some |
| Exploração e HUD | Ruim | Objetivo de missão e marcador de local, em fonte pequena sobre cena clara, saem quebrados ou não saem |
| Cutscene sem legenda | Nada | Esperado: sem texto, só a análise visual do modelo com visão consegue entidades |

Leitura:
- O jogo-piloto se confirma para telas de menu (glossário, diário, inventário, tutorial): o OCR basta e dá nomes canônicos confiáveis.
- O ponto fraco é a legenda em cena de jogo e o HUD. Isso justifica comparar OCR com modelo de visão e extrair vídeo por quadros com legenda.
- Passos seguintes: testar pré-processamento (recorte da faixa da legenda, binarização, ampliação) e medir com o gabarito.
- Amostra tem poucas telas de escolhas, cutscene, item e mapa (ver `docs/semana2.md`); o teste desses tipos ainda precisa de mais capturas.

### Segunda rodada (2026-10-07): 27 screenshots novas
Mesmo método (`por+eng`, imagem inteira, 0,4 a 1,9 s por imagem). Palavras reconhecidas por imagem (média): glossário de personagens 140 a 290 (nomes de todos os personagens da lista lateral, exceto Lambert e Cirilla na tela de Eskel); quadro de avisos 85 a 160 (texto do cartaz legível, nomes como Peter Saar Gwynleve e Pomar Branco saem); item/inventário 77 a 150 (nome e descrição saem, mas com ruído de estatísticas); bestiário 160 a 190 (acento falha em "Carniçal" e "Cáscara" no console, a conferir no arquivo); exploração/HUD 29 a 31 (pouco texto útil, mesmo problema anterior). Resultado confirma a leitura anterior: menus são fáceis, HUD e legenda sobre cena são o ponto fraco. Os quadros de avisos entram como tipo novo, fácil para OCR.

## Pontuação detalhada (estimativa inicial, a revisar após o teste)

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
