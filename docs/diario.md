# Diário de bordo

## Semana 1 · 2026-10-01
- Feito: estrutura do repositório; jogo-piloto definido (The Witcher 3); hardware registrado; revisão enxuta verificada (resumo, introdução e conclusão); justificativa, estado da arte e referências redigidos
- Decisões: ver `docs/decisoes/001-jogo-piloto.md`; sem Zotero, referências só para justificar escolhas; instalações ficam para a Semana 2
- Próximos passos: instalar ferramentas no computador do projeto

## Semana 2 (adiantado) · 2026-10-01
- Feito: primeiro commit; guia do gabarito, esquema provisório, scripts de validação e avaliação testados com exemplo; plano da Semana 2
- Próximos passos: instalar ferramentas no computador do projeto, coletar o conjunto de teste e anotar o gabarito

## Semana 3 (adiantado) · 2026-10-02
- Feito: ontologia v0.1 (7 tipos, 8 relações), esquema e validador com domínio e alcance, grafo de exemplo do prólogo, protótipo do exportador e vault de exemplo
- Decisões presumidas: ver `docs/ontologia.md`
- Próximos passos: revisar as decisões, abrir o vault no Obsidian, testar a ontologia nas telas coletadas

## Revisão da documentação · 2026-10-05
- Feito: conferência do repositório contra a documentação; pipeline de exemplo rodado no `.venv` (validação sem problemas, grafo de 16 nós e 17 arestas, avaliador funcionando); README e Semana 3 atualizados
- Observação: `pydantic` só existe no `.venv`; fora dele `validar_gabarito.py` e `grafo.py` falham
- Pendências inalteradas: instalar ferramentas, confirmar hardware, coletar o conjunto de teste, teste de OCR, validar a decisão 001 com o orientador, revisar e congelar a ontologia

## Configuração de captura · 2026-10-05
- Decidido: jogo em pt-BR; 1920x1080; screenshots pela tecla F12 da Steam; vídeos em 1080p, 30 fps, MP4 pelo OBS Studio ou clipe do último minuto pelo AMD Adrenalin
- Efeito nos docs: decisão 5 da ontologia fechada (nomes em pt-BR); `semana2.md`, `gabarito.md` e decisão 001 atualizados
- Próximos passos: ajustar o Adrenalin para 1080p/30 fps/MP4, instalar ferramentas (Tesseract com `por`), coletar o conjunto de teste, teste de fumaça de OCR

