# Semana 2: coleta do conjunto de teste e início do gabarito

**Objetivo:** reunir o conjunto de teste do The Witcher 3 e anotar o gabarito de um subconjunto.
**Saída:** `data/raw/` com o material organizado, ferramentas funcionando, teste de fumaça de OCR feito e gabarito iniciado (`docs/gabarito.md`).

## Dia 1: instalar e conferir (no computador do projeto)
- [ ] Instalar Tesseract (com `eng` e `por`), Ollama, FFmpeg, Obsidian e OBS Studio
- [ ] `python -m venv .venv`, `pip install -r requirements.txt` e `python scripts/check_env.py`
- [ ] Preencher SO, disco e VRAM em `docs/hardware.md`
- [ ] Definir o idioma do jogo para o projeto (nomes do gabarito seguem esse idioma)

## Dia 1–2: configurar o jogo para capturar
- Legendas ligadas, resolução fixa (a mesma em todas as capturas), modo janela ou sem borda.
- Anote em `docs/diario.md` a resolução e o idioma usados.
- Screenshots: tecla de screenshot da plataforma (por exemplo F12 no Steam), Win+PrtScn ou OBS.
- Vídeos: OBS Studio, 1080p, 30 fps, MP4.

## Dias 2–4: coleta (jogando normalmente, sem encenar)
Meta: cerca de **50 screenshots** e **8 a 10 clipes** de 30 a 60 s.

| Tipo de tela | Screenshots | Clipes |
|---|---|---|
| Diálogo com legenda | 10 | 3 |
| Escolhas de diálogo | 6 | 2 (escolha e consequência) |
| Diário de missões | 8 | 1 (atualização de missão) |
| Item ou inventário | 8 | 1 (rolar inventário) |
| Mapa e títulos de local | 4 | 1 (exploração com título de região) |
| Glossário e personagens | 6 | n/a |
| Cutscene | 4 | 2 |
| HUD e combate (controle) | 4 | 0 a 1 |

Nomes de arquivo: `img_001_dialogo.png`, `vid_003_cutscene.mp4` (tipo de tela no nome). Anote em `data/raw/metadados.csv`: arquivo, tipo de tela, área do jogo, observação.

## Dia 4: teste de fumaça de OCR
- `python scripts/smoke_ocr.py data/raw/img_001_dialogo.png --lang por+eng` (ajuste o idioma) em 5 imagens de tipos diferentes.
- Anote: texto legível? Nomes próprios certos? O que se perdeu? Isso entra na decisão 001 (riscos) e valida o jogo-piloto.

## Dias 5–7: gabarito
- Escolher o subconjunto (cerca de 20 screenshots e 3 a 4 clipes, todos os tipos de tela).
- Seguir `docs/gabarito.md`: 5 itens, ajustar regras, anotar o restante, validar, revisar no dia seguinte.

## Fecho da semana
- [ ] `data/raw/` organizado (não versionado) e `metadados.csv` preenchido
- [ ] Teste de fumaça registrado em `docs/decisoes/001-jogo-piloto.md`
- [ ] Gabarito do subconjunto anotado e validado
- [ ] Commit e entrada no diário
