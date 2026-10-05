# Checklist da Semana 1 (preparação, sem jogar)

Legenda: ✅ feito no repositório · ☐ falta você fazer

## Já pronto
- ✅ Estrutura, README, .gitignore, requirements e scripts
- ✅ Hardware registrado (`docs/hardware.md`; VRAM, SO e disco ainda a confirmar, ver abaixo)
- ✅ Justificativa (`docs/justificativa.md`), estado da arte e síntese (`docs/revisao/`)
- ✅ Referências verificadas (`docs/referencias.md`)
- ✅ Decisão do jogo-piloto e rascunho de e-mail (`docs/decisoes/`)

## Falta fazer (sem instalar nada)
1. ✅ Primeiro commit no repositório https://github.com/AlexEduardo-zip/POC_1-GameMind (feito):
   ```bash
   git clone https://github.com/AlexEduardo-zip/POC_1-GameMind.git
   # copie o conteúdo do zip para dentro da pasta clonada
   cd POC_1-GameMind
   git add .
   git commit -m "Semana 1: estrutura, revisão e decisão do jogo-piloto"
   git push
   ```
2. ☐ Confirmar a VRAM da RX 7600 (Gerenciador de Tarefas > Desempenho > GPU) e preencher SO e disco em `docs/hardware.md`

## Decidido em 2026-10-05 (configuração de captura)
- ✅ Idioma pt-BR, resolução 1920x1080
- ✅ Screenshots: F12 da Steam; vídeos: OBS Studio ou clipe do AMD Adrenalin (1080p, 30 fps, MP4)

## Quando estiver no computador do projeto (início da Semana 2)
- ☐ Instalar Tesseract (com `eng` e `por`), Ollama, FFmpeg, Obsidian e OBS Studio
- ☐ Criar o ambiente Python e rodar `python scripts/check_env.py`
- ☐ Teste de fumaça de OCR e coleta das screenshots e vídeos

## Fora do escopo
- Zotero e gestão de referências à parte: a bibliografia fica só em `docs/referencias.md`
