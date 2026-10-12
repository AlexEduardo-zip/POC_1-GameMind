# Diário de bordo

Registro cronológico resumido. Conclusões do estudo: `docs/estudo-viabilidade.md`; estado do aplicativo: `docs/arquitetura.md`.

## 2026-10-01 a 10-05 · Preparação
- Estrutura do repositório, justificativa, estado da arte e referências; jogo-piloto definido, The Witcher 3 (decisão 001); hardware registrado.
- Guia do gabarito, esquema provisório, scripts de validação e avaliação testados com exemplos; ontologia 0.1, grafo e vault de exemplo, protótipo do exportador.

## 2026-10-07 · Coleta, gabarito e primeiro pipeline
- Ferramentas instaladas (Tesseract, FFmpeg); capturas e clipes coletados e catalogados; teste de fumaça de OCR (bom em menus, ruim em HUD e legenda sobre cena).
- Gabarito inicial anotado e verificado pelo autor; pipeline de exemplo rodado no gabarito real; segunda leva de coleta, com quadros extraídos de clipes para cobrir lacunas.
- Um clipe com conteúdo pessoal na tela foi removido.

## 2026-10-08 · Ontologia e estudo de viabilidade
- Ontologia congelada como 1.0 e emendada para 1.1 (tipo `faccao` e predicado `membro_de`); `evento` e `gera` em reserva (decisão 002).
- Gabarito ampliado e verificado; avaliador com quebra por tipo de entidade, predicado e tipo de tela.
- Rodadas B1 a B5: OCR com dicionário independente, recortes e filtro de brilho, regras por tipo de tela, LLM local em cascata, vídeo por amostragem de quadros e combinação das fontes. Conclusões em `docs/estudo-viabilidade.md`.

## 2026-10-09 a 10-10 · Aplicativo
- Aplicativo `gamemind.py` (núcleo, linha de comando e janela PySide6; decisão 003): um jogo por pasta, vault do Obsidian com canvas, tela de processamento com a captura em leitura e as notas criadas, botões separados para só OCR e para OCR com IA.
- Dicionário de nomes aprendido do texto lido, sem lista escrita à mão (decisão 004).
- Testes de regiões: os recortes ajudam; recortes genéricos leem pior que os calibrados para um jogo; refinar os recortes com a IA local de texto não ajudou.
- Retirado tudo o que era específico do Witcher 3 (decisão 005). Missões, decisões e relações ficam sem fonte até haver um substituto que não dependa de jogo.
- Próximo: `docs/proximos-passos.md`.
