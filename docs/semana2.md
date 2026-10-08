# Semana 2: coleta do conjunto de teste e início do gabarito

> Histórico e plano original. Pendências atuais: `docs/proximos-passos.md`. Os itens "configurar o jogo" abaixo foram cumpridos na prática (coleta feita em 2026-10-05 a 07, ver "Estado da coleta"); hardware já está preenchido em `docs/hardware.md`.

**Objetivo:** reunir o conjunto de teste do The Witcher 3 e anotar o gabarito de um subconjunto.
**Configuração de captura (guia, não regra):** o que importa é ter material variado para testar o pipeline. Resolução, formato (JPG/PNG), taxa de quadros, ferramenta (Steam F12, Adrenalin, OBS) e a origem (screenshot de verdade ou quadro extraído de vídeo) são só orientação; desvios não bloqueiam nada e ficam registrados em `metadados.csv`. Mantido como padrão: jogo em pt-BR (nomes do gabarito em pt-BR). Os arquivos de `data/gabarito/exemplo/` e `docs/exemplo/` usam inglês só para demonstrar o pipeline.

**Saída:** `data/raw/` com o material organizado, ferramentas funcionando, teste de fumaça de OCR feito e gabarito iniciado (`docs/gabarito.md`).

## Dia 1: instalar e conferir (no computador do projeto)
- [x] Tesseract (com `eng` e `por`) e FFmpeg instalados; Ollama instalado, mas sem instância em execução; Obsidian e OBS Studio a confirmar
- [x] `.venv` com `pytesseract`, `pillow` e `pydantic` (o `check_env.py` fora do `.venv` acusa falta de pacotes; rode dentro dele)
- [x] SO, disco e VRAM preenchidos em `docs/hardware.md`
- [x] Idioma definido: pt-BR (nomes do gabarito seguem esse idioma)
- [x] Resolução e formas de captura definidas (ver acima)
- [x] Tesseract com o idioma `por` conferido (`eng`, `osd`, `por`)

## Dia 1–2: configurar o jogo para capturar
- [x] Jogo em pt-BR, legendas ligadas, 1920x1080 (cumprido, conforme as capturas)
- [x] Screenshots: F12 da Steam. Confira em Steam > Configurações > No jogo onde as capturas são salvas (use "Mostrar na pasta").
- [x] Vídeos: feitos pelo Adrenalin (OBS não usado).
- [x] Clipes do Adrenalin (gravaram a 60 fps, ver desvios): em AMD Software > Gravação e Streaming, ajuste a resolução para 1080p, 30 fps e formato MP4 e a duração do replay para 1 minuto antes de usar o atalho. O clipe é um recorte do último minuto: aperte logo depois da cena que interessa.
- [x] Configuração registrada em `docs/diario.md` (2026-10-05)

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

Nomes de arquivo (renomeie as capturas da Steam e do Adrenalin para este padrão): `img_001_dialogo.jpg`, `vid_003_cutscene.mp4` (tipo de tela no nome). Anote em `data/raw/metadados.csv`: arquivo, tipo de tela, área do jogo, ferramenta (steam, obs, adrenalin), observação.

## Estado da coleta (2026-10-07, após a segunda leva)
Coletados **83 screenshots** (JPG, 1920x1080), **14 quadros extraídos de vídeo** (abaixo) e **37 clipes** (36 na pasta) (MP4 do AMD Adrenalin, 22 a 60 s), todos como `img_NNN_tipo.jpg` e `vid_NNN_tipo.mp4` e catalogados em `data/raw/metadados.csv` (tipo de tela, área, ferramenta, observação, nome original, `no_gabarito`). A segunda leva (27 screenshots, `img_057` a `img_083`; 10 clipes, `vid_028` a `vid_037`) foi identificada e renomeada em 2026-10-07; os 5 JPG `20261007000220_1` a `20261007000333_1` que sobraram na pasta são cópias idênticas de `img_052`, `img_053`, `img_054`, `img_055` e `img_056` (mesmo hash) e podem ser apagados.

| Tipo de tela | Screenshots (meta) | Clipes (meta) |
|---|---|---|
| Tutorial (extra, não previsto) | 33 | 0 |
| Diálogo com legenda | 7 (10) | 23 (3) |
| Escolhas de diálogo | **0** (6) + 4 de quadro | 2 (2) |
| Diário de missões | 3 (8) + 3 de quadro | 1 (1) |
| Item ou inventário | 10 (8) | 0 (1) |
| Mapa e títulos de local | 2 (4) + 4 de quadro | 1 (1) |
| Glossário e personagens | 15 (6) | n/a |
| Cutscene | 1 (4) + 3 de quadro | 3 (2) |
| HUD e exploração | 6 (4) | 7 (0 a 1) |
| Quadro de avisos (extra) | 6 | 0 |

Lacunas que restam (alimentam as tarefas A1 e A2 de `docs/proximos-passos.md`):
- **Screenshots:** escolhas de diálogo (nenhuma; falta 6), diário (3, faltam 5), mapa (2, faltam 2) e cutscene (1, faltam 3). Item, glossário e exploração já passaram da meta. Clipes de item/inventário: 0 (a meta é 1; o `vid_034_diario` mostra inventário por alguns segundos).
- **Excesso:** tutorial (33), glossário (15) e diálogo em clipe (23 contra 3) estão acima do necessário; ficam como material de observação.
- **Privacidade:** `vid_028_cutscene` mostra WhatsApp Web (conversas pessoais) nos primeiros ~30 s. Não usar no gabarito nem em demonstrações antes de cortar; a pasta `data/raw/` não é versionada.
- **Novidades de conteúdo:** quadros de avisos de Pomar Branco (6 telas com contratos e anúncios, vários com nomes próprios como Peter Saar Gwynleve) e glossário completo de Personagens e Bestiário (Afogadores, Carniçal). Gwent (`img_066_item`) é fora de escopo.

### Screenshots obtidas de quadros de vídeo (2026-10-07)
Para fechar lacunas sem jogar de novo, extraí 14 quadros de clipes já coletados com `ffmpeg` (corte 1920x1080 do clipe 1920x1088, PNG, sem reescala), como `img_084` a `img_097`, com `ferramenta = frame_de_video` e a origem (clipe@segundo) em `nome_original` de `metadados.csv`:

| Tipo | Quadros | Origem |
|---|---|---|
| Escolhas de diálogo | `img_084`, `img_085`, `img_086`, `img_087` | `vid_008` (4 s, 36 s), `vid_025` (8 s, 10 s) |
| Diário de missões | `img_088`, `img_089`, `img_090` | `vid_034` (31 s, 30 s, 32 s) |
| Mapa | `img_091` a `img_094` | `vid_029` (27, 40, 43, 48 s) |
| Cutscene | `img_095`, `img_096`, `img_097` | `vid_001` (36 s), `vid_002` (2 s, 20 s) |

Observações (sem caráter de regra):
- Servem como screenshots para testar o pipeline. Só para o estudo "screenshot × vídeo" (Semanas 5–7) vale lembrar que o conteúdo também existe nos clipes; se preciso, filtre por `ferramenta = frame_de_video`.
- `img_089` e `img_090` são quase idênticas (mesma tela, cursor diferente).
- Cutscene: os quadros com legenda são `img_096` e `img_097`; `img_095` não tem legenda.
- As cenas de `vid_001` e `vid_002` mostram nudez parcial (cena do banho); evite em demonstrações públicas.
- Escolhas de diálogo com texto legível só existem nesses 2 clipes; as 4 imagens são as únicas telas de escolha disponíveis. Faltam 2 para a meta de 6 e, ainda, screenshot de verdade.
- `vid_028_cutscene.mp4` não está mais na pasta (provavelmente apagado por causa do WhatsApp); a linha em `metadados.csv` ficou marcada.

## Dia 4: teste de fumaça de OCR
**Feito em 2026-10-07** nas 56 screenshots (e nas 27 novas, ver decisão 001) com `por+eng`. Resultado completo em `docs/decisoes/001-jogo-piloto.md`: bom em glossário, diário e tutorial; médio em inventário e mapa; ruim em legenda sobre cena clara e HUD.

- `python scripts/smoke_ocr.py data/raw/img_001_dialogo.png --lang por+eng` em 5 imagens de tipos diferentes.
- Anote: texto legível? Nomes próprios certos? O que se perdeu? Isso entra na decisão 001 (riscos) e valida o jogo-piloto.

## Dias 5–7: gabarito
- Escolher o subconjunto (cerca de 20 screenshots e 3 a 4 clipes, todos os tipos de tela).
- Seguir `docs/gabarito.md`: 5 itens, ajustar regras, anotar o restante, validar, revisar no dia seguinte.

## Fecho da semana (concluída em 2026-10-07)
- [x] `data/raw/` organizado (não versionado) e `metadados.csv` preenchido (83 screenshots, 14 quadros de vídeo, 36 clipes)
- [x] Todos os tipos de tela cobertos (escolhas, diário, mapa e cutscene via quadros de vídeo; ver acima)
- [x] Subconjunto escolhido e gabarito anotado, validado pelo script e verificado pelo autor (20 screenshots e 4 clipes, 24 JSON em `data/gabarito/`)
- [x] Teste de fumaça de OCR registrado em `docs/decisoes/001-jogo-piloto.md` (83 screenshots)
- [x] Pipeline testado ponta a ponta no gabarito real: validação (0 problemas), grafo (32 nós, 20 arestas), vault (32 notas) e avaliação com a linha de base `scripts/baseline_ocr.py` (ver abaixo)
- [x] Commit e entrada no diário

## Linha de base de ponta a ponta (2026-10-07)
`python scripts/baseline_ocr.py` faz OCR da imagem inteira e procura os nomes e aliases de `entidades.json`; `python eval/avaliar.py --pred eval/predicoes/baseline_ocr` compara com o gabarito. Resultado nas 20 screenshots (clipes ficam sem previsão): **entidades precisão 1,00, revocação 0,70, F1 0,83; relações 0** (a linha de base não extrai relações); 15,6 s no total.
Leitura: serve para provar que o ciclo extração → avaliação funciona. A precisão 1,00 é enganosa, porque o dicionário vem do próprio gabarito (vazamento); o número que vale é a revocação por tipo de tela: glossário, diário e item saem quase perfeitos; exploração, HUD, tutorial com legenda, cena sem texto e diálogo com rosto sem legenda ficam em 0 a 0,5.

### Atualização (2026-10-07, depois da ampliação do gabarito)
Com 28 itens novos anotados (rascunho, a verificar), a linha de base nas 48 screenshots do gabarito deu **entidades precisão 0,93, revocação 0,82, F1 0,88; relações 0**; 41,6 s. A precisão caiu de 1,00 (a causa não foi investigada; o OCR achou nomes que o gabarito novo não anota). O dicionário continua vindo do gabarito (vazamento). O grafo passou de 32 nós e 20 arestas para **51 nós e 26 arestas**; o vault de `vault_output/` tem 51 notas.
