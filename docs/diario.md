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

## Coleta e teste de OCR · 2026-10-07
- Feito: 56 screenshots (Steam, JPG) e 27 clipes (Adrenalin, MP4) organizados como `img_NNN_tipo` e `vid_NNN_tipo`; `data/raw/metadados.csv` criado; teste de fumaça de OCR (`por+eng`) rodado nas 56 imagens e registrado na decisão 001
- Resultado do OCR: bom em glossário, diário e tutorial; médio em inventário e mapa; ruim em legenda sobre cena clara e HUD
- Desvios: vídeos em 1920x1088 e 60 fps (previsto 1080p/30 fps); screenshots em JPG
- Lacunas: nenhuma screenshot de escolhas; poucas de diário, item, mapa e cutscene; 31 de 56 são tutorial
- Próximos passos: completar as lacunas, escolher o subconjunto do gabarito (cerca de 20 screenshots e 3 a 4 clipes) e anotar 5 itens para testar as regras

## Rascunho do gabarito · 2026-10-07
- Feito: escolhidos 20 screenshots e 4 clipes cobrindo diálogo, HUD, glossário, diário, mapa, item, cutscene e escolhas; anotados 85 entidades e 24 relações em 24 JSON; `entidades.json` com 32 nomes canônicos em pt-BR; validação sem problemas e grafo gerado (32 nós, 20 arestas)
- Regras novas no `docs/gabarito.md` (8 a 13): sufixo "(missão)" para nome igual ao de um local, personagem só com nome escrito na tela, menção conta, só a decisão escolhida, itens fora de escopo, título do HUD é a missão
- Atenção: é rascunho de IA e precisa de verificação humana; as dúvidas estão em `docs/gabarito.md` e nas `observacoes` de cada arquivo
- Próximos passos: verificar o gabarito, revisar 5 itens sorteados no dia seguinte, completar a coleta e testar pré-processamento do OCR

## Gabarito verificado · 2026-10-07
- Feito: o autor verificou o gabarito (correto, 5 itens revisados); pipeline rodado sobre o gabarito real (validação 0 problemas, grafo de 32 nós e 20 arestas, vault de 32 notas em `vault_output/`, não versionado)
- Cobertura da ontologia: tudo coube nos 7 tipos e 8 predicados; sem uso no subconjunto: `evento`, `gera`, `concede`, `obtido_em`
- Próximos passos: completar a coleta (escolhas em screenshot, diário, item, mapa, cutscene), abrir o vault no Obsidian, testar pré-processamento do OCR e rodar a primeira extração para comparar com o gabarito

## Organização da documentação · 2026-10-07
- Feito: criado `docs/proximos-passos.md` como fonte única das pendências (ordem, critério de pronto, mapa para o cronograma da proposta); README, `semana2.md` e `semana3.md` apontam para ele; `docs/checklist-semana1.md` (obsoleto) retirado do README; `workspace.json` do Obsidian adicionado ao `.gitignore` (estado local)
- Achado: ainda não há extrator em `src/`; as Semanas 5–7 dependem de fechar a coleta (A1–A2) e congelar a ontologia (A5)

## Segunda leva da coleta · 2026-10-07
- Feito: identificadas e renomeadas 27 screenshots (`img_057` a `img_083`) e 10 clipes (`vid_028` a `vid_037`); `metadados.csv` com 120 itens; OCR rodado nas novas imagens (resumo na decisão 001); semana2.md com a nova tabela de cobertura
- Achados: tipo novo "quadro de avisos" (6 telas); glossário de Personagens e Bestiário completos; `vid_028_cutscene` mostra WhatsApp nos ~30 s iniciais (não usar sem cortar); 5 JPG na pasta são cópias de `img_052` a `img_056`
- Lacunas: escolhas (0 screenshots), diário (faltam 5), mapa (2), cutscene (3)

## Quadros extraídos de vídeo · 2026-10-07
- Feito: 14 quadros de clipes (`img_084` a `img_097`: 4 escolhas, 3 diário, 4 mapa, 3 cutscene) com `ffmpeg`, catalogados como `frame_de_video`; OCR confirmou as opções de diálogo, o diário e os tooltips do mapa
- Cuidado: não contar esses quadros como "screenshot" na comparação screenshot × vídeo (mesmo conteúdo dos clipes); `vid_028_cutscene` sumiu da pasta (linha em `metadados.csv` marcada)

## Fecho da Semana 2 · 2026-10-07
- Decidido: formato, resolução e fonte do material (screenshot ou quadro de vídeo) são só guia, não regra; o foco é testar a aplicação
- Feito: lacunas da coleta fechadas com quadros de vídeo; pipeline rodado no gabarito real (validação 0 problemas, 32 nós, 20 arestas, 32 notas); criada a linha de base `scripts/baseline_ocr.py` e rodado o avaliador (entidades P 1,00 / R 0,70 / F1 0,83; relações 0; vazamento do dicionário explicado em `semana2.md`)
- Próximos passos: `docs/proximos-passos.md` (A1 a A4, depois o estudo de viabilidade)
