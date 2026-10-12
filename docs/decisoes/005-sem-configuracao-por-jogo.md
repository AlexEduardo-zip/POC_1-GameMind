# Decisão 005 · O aplicativo não tem nenhuma configuração prévia nem específica de jogo

- Data: 2026-10-10
- **Decisão: o aplicativo funciona sem perfil de jogo, sem lista de nomes, sem regiões calibradas e sem regras de tela de um jogo. Por enquanto só usa recortes de OCR genéricos (os mesmos para qualquer jogo).**

## Contexto
O estudo de viabilidade foi feito com *The Witcher 3* em português e deixou no código coisas específicas daquele jogo: um perfil (`PERFIS`), um dicionário de 90 nomes, regiões de tela calibradas em 1920×1080 e as regras de `estruturada.py` (diário, mapa, quadro de avisos, opções de diálogo, banner de missão, ficha de item, com textos da interface do jogo). Um aplicativo que exige isso para cada jogo não escala e não é o produto.

## O que foi removido do aplicativo
- **Perfil de jogo:** os jogos são pastas que o usuário cria (botão **Novo jogo**). O idioma do OCR é uma configuração (`idioma_ocr`, padrão `por+eng`).
- **Dicionário escrito à mão:** os nomes são aprendidos do texto lido (decisão 004). Nenhum texto de interface de jogo (como "NOVO MARCADOR" ou "Avançar texto") é usado no aprendizado.
- **Regiões calibradas:** os 3 recortes de OCR (legenda, objetivo, avisos) são genéricos (`preprocessamento.ROIS`, `regioes.PADRAO`). O refinamento com IA local continua disponível, mas é opcional (`--aprender-regioes`).
- **Regras por tipo de tela:** `estruturada.py` saiu. Não há mais regras para missão, decisão, item de inventário nem relações lidas da estrutura da tela.
- **Detalhes de captura:** o corte de 1920×1088 para 1920×1080 (de uma ferramenta de captura) deu lugar ao tamanho do próprio vídeo.
- **Textos específicos no LLM:** o prompt não cita mais o jogo, e as listas de rótulos de inventário e de palavras genéricas do jogo foram retiradas.
- O código do estudo (regras, dicionário e scripts das rodadas B1 a B5) saiu do projeto; está no histórico do repositório (commit `cd8e451`).

## Consequências
- O app roda do mesmo jeito para qualquer jogo, sem preparo.
- **Perde-se o que dependia de saber onde ficam as coisas na tela do jogo-piloto:** missões e decisões, e as relações. Personagens, locais, criaturas e facções continuam, pelo dicionário aprendido e pela IA.
- Missões, decisões e relações precisam de um substituto que não dependa de jogo: ler a tela com posição e usar a IA, ou uma IA que veja a imagem (`docs/proximos-passos.md`).
