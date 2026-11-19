# IA fora do computador: Claude com o login da assinatura

O GameMind usa uma IA de texto para achar criaturas, itens e relações e para revisar e resumir as entidades. Há duas opções, e nenhuma cobra por uso:

| Opção | Prefixo (`--ia`) | Modelo padrão | O que precisa |
|---|---|---|---|
| Ollama, no computador | `ollama` | `qwen2.5:7b` | Ollama aberto e o modelo baixado (`ollama pull qwen2.5:7b`) |
| Claude pelo Claude Code | `claude-code` (aceita `claude`) | `haiku` | Claude Code instalado e o login de uma assinatura Pro ou Max |

As IAs cobradas por token (OpenAI, Gemini, API da Anthropic) foram retiradas do aplicativo por enquanto; o código delas está no histórico do git (commit `f82c062`). Uma configuração antiga que ainda as use avisa no fim da rodada para escolher outra IA em Jogo > Configurar jogo.

## Como usar o Claude
1. Instale o Claude Code (https://claude.com/claude-code).
2. No assistente do jogo (Adicionar jogo ou Jogo > Configurar jogo), escolha **Claude** e clique em **Entrar com a conta Claude**: o Claude Code abre num terminal e pede o login no navegador, se faltar. Depois clique em **Testar conexão**.
3. Pela linha de comando: `python gamemind.py processar --jogo "Meu jogo" --ia claude-code` (outros modelos: `claude-code:sonnet`, `claude-code:opus`; o `haiku` gasta menos cota). Teste rápido: `python scripts/testar_conector.py claude-code`.

O executável é procurado no PATH e depois na extensão do VS Code; se não for achado, defina `CLAUDE_CODE_PATH` no `.env` (modelo em `.env.example`).

## O que sai do computador
- **Só texto**: o texto lido de cada tela e os nomes já detectados. Imagens e clipes nunca saem; o aprendizado de regiões usa só o modelo de imagem do Ollama.
- O Claude Code roda sem ferramentas e sem gravar sessão (`claude -p --tools ""`): ele só responde no esquema JSON do GameMind.

## Limites
- Cada chamada abre um processo: cerca de 10 s por captura e por lote de 6 entidades na revisão.
- Desconta da cota do plano, que tem limite por janela de horas; num lote grande a cota pode acabar. A rodada guarda o que já foi respondido e continua de onde parou na próxima.
- Depende de uma pessoa logada. Confira nos termos da Anthropic se o seu uso se enquadra no plano.

## Problemas comuns
| Mensagem | O que fazer |
|---|---|
| `Claude Code não encontrado` | Instale, ou defina `CLAUDE_CODE_PATH` no `.env`. |
| `Not logged in` | Clique em **Entrar com a conta Claude** (ou rode `claude` num terminal) e faça o login. |
| `sem resposta em 300 s` | Cota esgotada ou rede lenta; tente mais tarde. |
