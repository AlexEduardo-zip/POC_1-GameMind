# Semana 2: coleta do conjunto de teste e início do gabarito

**Objetivo:** reunir o conjunto de teste do The Witcher 3 e anotar o gabarito de um subconjunto.
**Configuração de captura (decidida em 2026-10-05):**
- Resolução: 1920x1080, a mesma em todas as capturas
- Idioma do jogo e dos nomes do gabarito: português do Brasil (pt-BR)
- Screenshots: tecla F12 da Steam (PNG)
- Vídeos: OBS Studio em 1080p, 30 fps, MP4; ou o clipe do AMD Adrenalin (atalho que salva o último minuto de gameplay)
- Os arquivos de exemplo do repositório (`data/gabarito/exemplo/`, `docs/exemplo/`) usam nomes em inglês só para demonstrar o pipeline; o gabarito real usa nomes em pt-BR

**Saída:** `data/raw/` com o material organizado, ferramentas funcionando, teste de fumaça de OCR feito e gabarito iniciado (`docs/gabarito.md`).

## Dia 1: instalar e conferir (no computador do projeto)
- [ ] Instalar Tesseract (com `eng` e `por`), Ollama, FFmpeg, Obsidian e OBS Studio
- [ ] `python -m venv .venv`, `pip install -r requirements.txt` e `python scripts/check_env.py`
- [ ] Preencher SO, disco e VRAM em `docs/hardware.md`
- [x] Idioma definido: pt-BR (nomes do gabarito seguem esse idioma)
- [x] Resolução e formas de captura definidas (ver acima)
- [ ] Rodar `python scripts/check_env.py` e conferir que o Tesseract tem o idioma `por` (`tesseract --list-langs`)

## Dia 1–2: configurar o jogo para capturar
- [ ] Jogo em pt-BR, legendas ligadas, 1920x1080, modo janela ou sem borda.
- [ ] Screenshots: F12 da Steam. Confira em Steam > Configurações > No jogo onde as capturas são salvas (use "Mostrar na pasta").
- [ ] Vídeos: OBS Studio em 1080p, 30 fps, MP4.
- [ ] Clipes do Adrenalin: em AMD Software > Gravação e Streaming, ajuste a resolução para 1080p, 30 fps e formato MP4 e a duração do replay para 1 minuto antes de usar o atalho. O clipe é um recorte do último minuto: aperte logo depois da cena que interessa.
- [ ] Registrar em `docs/diario.md` a configuração usada (resolução, idioma, ferramenta de cada captura).

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

Nomes de arquivo (renomeie as capturas da Steam e do Adrenalin para este padrão): `img_001_dialogo.png`, `vid_003_cutscene.mp4` (tipo de tela no nome). Anote em `data/raw/metadados.csv`: arquivo, tipo de tela, área do jogo, ferramenta (steam, obs, adrenalin), observação.

## Dia 4: teste de fumaça de OCR
- `python scripts/smoke_ocr.py data/raw/img_001_dialogo.png --lang por+eng` em 5 imagens de tipos diferentes.
- Anote: texto legível? Nomes próprios certos? O que se perdeu? Isso entra na decisão 001 (riscos) e valida o jogo-piloto.

## Dias 5–7: gabarito
- Escolher o subconjunto (cerca de 20 screenshots e 3 a 4 clipes, todos os tipos de tela).
- Seguir `docs/gabarito.md`: 5 itens, ajustar regras, anotar o restante, validar, revisar no dia seguinte.

## Fecho da semana
- [ ] `data/raw/` organizado (não versionado) e `metadados.csv` preenchido
- [ ] Teste de fumaça registrado em `docs/decisoes/001-jogo-piloto.md`
- [ ] Gabarito do subconjunto anotado e validado
- [ ] Commit e entrada no diário
