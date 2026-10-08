# Diário de bordo

Registro cronológico resumido. Resultados consolidados: `docs/resumo-do-projeto.md`; detalhes técnicos: `docs/estudo-viabilidade.md`.

## 2026-10-01 a 10-05 · Preparação
- Estrutura do repositório, justificativa, estado da arte e referências (sem Zotero; referências só para justificar escolhas); jogo-piloto definido, The Witcher 3 (decisão 001); hardware registrado.
- Guia do gabarito, esquema provisório, scripts de validação e avaliação testados com exemplos; ontologia 0.1 (7 tipos, 8 relações), grafo e vault de exemplo do prólogo, protótipo do exportador.
- Configuração de captura definida (pt-BR, 1920x1080), depois tratada como guia e não regra. Nomes do gabarito em pt-BR.

## 2026-10-07 · Coleta, gabarito e primeiro pipeline
- Ferramentas instaladas (Tesseract com `por`, FFmpeg); 56 screenshots e 27 clipes coletados, catalogados em `metadados.csv`; teste de fumaça de OCR (bom em menus, ruim em HUD e legenda sobre cena).
- Gabarito de 20 screenshots e 4 clipes anotado (rascunho de IA), verificado pelo autor; pipeline de exemplo rodado no gabarito real (32 nós, 20 arestas).
- Segunda leva: 27 screenshots e 10 clipes identificados e renomeados; 14 quadros extraídos de clipes para fechar lacunas (escolhas, diário, mapa, cutscene); 28 itens novos anotados; `vid_028` removido (conteúdo pessoal na tela).

## 2026-10-08 · Ontologia, estudo de viabilidade e organização
- Ontologia congelada como 1.0 (análise do gabarito, decisão 002) e emendada para 1.1 (tipo `faccao` e predicado `membro_de`, depois de medir facções em 17% das telas); `evento` e `gera` em reserva.
- Gabarito novo (39 itens) verificado pelo autor; 9 cópias duplicadas de `data/raw/` apagadas; avaliador com quebra por tipo de entidade, predicado e tela, `relacionado_a` simétrico.
- **B1** extrator de OCR com dicionário independente (o vazamento da primeira linha de base valia 0,11 de F1); **B2** recortes e filtro de brilho (nomes no texto 0,81 → 0,89); **B3a** regras por tipo de tela (missão e decisão saem de 0,00); **B3b** LLM local em cascata (Ollama na RX 7600, `qwen2.5:7b` e `3b`; relações 0,29 → 0,44); **B4** vídeo (quadro a cada 2 s, F1 0,76) e **B5** combinação das fontes (revocação 0,72 → 0,82). Gabarito corrigido duas vezes a partir do que o extrator mostrou (`img_088`, `img_094` e 9 entidades dos clipes).
- Documentação reorganizada: resumo principal, `coleta.md` (substitui os planos das semanas 2 e 3 e o roteiro de verificação), histórico enxuto; script de linha de base com vazamento removido.
- Observação: o Ollama atualizou-se sozinho e criou um atalho de inicialização do Windows; o servidor foi iniciado com `ollama serve`.
- Próximo: `docs/proximos-passos.md`.
