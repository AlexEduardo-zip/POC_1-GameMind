# Conector de IA pública

O GameMind extrai entidades e relações do texto lido da tela. Esse passo pode usar um modelo **local** (Ollama) ou uma **IA pública** na nuvem; no aplicativo, a escolha fica em Configurações ou em `--ia`. O conector de IA pública suporta três provedores, com a mesma interface e o mesmo esquema de saída:

| Provedor | Produtos | Prefixo | Modelo padrão | Variável da chave |
|---|---|---|---|---|
| OpenAI | ChatGPT / Codex (API) | `openai` (aceita `chatgpt`, `codex`, `gpt`) | `gpt-5-mini` | `OPENAI_API_KEY` |
| Google | Gemini | `gemini` (aceita `google`) | `gemini-2.5-flash` | `GEMINI_API_KEY` ou `GOOGLE_API_KEY` |
| Anthropic | Claude | `claude` (aceita `anthropic`) | `claude-haiku-4-5-20251001` | `ANTHROPIC_API_KEY` |
| Anthropic via assinatura | Claude Code (plano Pro/Max, **sem chave e sem custo por token**) | `claude-code` | `haiku` | nenhuma (login do Claude Code) |
| Local | Ollama | `ollama` | `qwen2.5:7b` | nenhuma |

Os padrões são modelos baratos e rápidos. Para trocar, use `provedor:modelo` (ex.: `openai:gpt-5`, `gemini:gemini-2.5-pro`, `claude:claude-sonnet-5-5`). Confira nomes e preços vigentes na página do provedor; eles mudam.

## Claude pelo plano Pro/Max (sem custo adicional)
O provedor `claude-code` chama o Claude Code instalado (`claude -p`) e usa o login da sua assinatura, então **não precisa de chave de API nem gera cobrança por token**. Ele consome a cota de uso do plano (que tem limite por janela de horas).
1. Instale o Claude Code e faça login uma vez: rode `claude` no terminal (ou use a extensão do VS Code já logada).
2. Teste: `python scripts/testar_conector.py claude-code`
3. Use: escolha **Claude Code** nas Configurações ou rode `python gamemind.py processar --jogo "Meu jogo" --ia claude-code`
   (outros modelos: `claude-code:sonnet`, `claude-code:opus`; o padrão `haiku` é o mais econômico para a cota).

O executável é procurado no PATH, depois na extensão do VS Code; se não achar, defina `CLAUDE_CODE_PATH` no `.env`.
Limites: cerca de 10 a 20 s por imagem (um processo por chamada), a cota do plano pode acabar num lote grande (a rodada para e continua de onde parou na próxima) e depende de uma pessoa logada. Serve para testar a qualidade do Claude; para uso contínuo ou automático use a API (`claude`). Confira nos termos da Anthropic se o seu uso se enquadra no plano.

## O que sai do seu computador
- **Só texto.** O OCR roda localmente; a nuvem recebe apenas o texto lido da tela e a lista de nomes já detectados. Imagens e clipes **nunca** são enviados.
- A chave é lida de variável de ambiente ou do `.env` (ignorado pelo git). Nunca a coloque no código nem em commits.
- O uso é cobrado na **sua conta** do provedor, por token. Uma imagem gasta cerca de 1,5 mil tokens de entrada e ~250 de saída; uma partida de algumas centenas de capturas custa de centavos a poucos dólares com os modelos padrão (estimativa em `docs/visao-geral.md`; confira a tabela de preços do provedor). A linha de comando mostra os tokens gastos ao fim de cada rodada.

## Passo a passo

### 1. Instalar o ambiente
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
```
O conector não precisa de nenhum pacote a mais (usa só a biblioteca padrão).

### 2. Obter a chave de API
A chave de API é diferente da assinatura do app. Assinar ChatGPT Plus, Gemini Advanced ou Claude Pro **não** dá chave de API; é preciso criar uma no painel de desenvolvedor de cada um (com crédito ou faturamento ativado):
- **OpenAI (ChatGPT/Codex):** https://platform.openai.com/api-keys
- **Gemini:** https://aistudio.google.com/apikey (há faixa gratuita com limites)
- **Claude:** https://console.anthropic.com/settings/keys

### 3. Configurar a chave
Copie o modelo e preencha só os provedores que for usar:
```bash
cp .env.example .env        # Windows: copy .env.example .env
```
```
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=AI...
ANTHROPIC_API_KEY=sk-ant-...
```
Alternativa sem arquivo (vale só para o terminal aberto): `export OPENAI_API_KEY=sk-...` (Linux/Mac) ou `$env:OPENAI_API_KEY="sk-..."` (PowerShell). Variável de ambiente tem prioridade sobre o `.env`.

### 4. Testar a conexão
```bash
python scripts/testar_conector.py openai      # ou gemini, claude
python scripts/testar_conector.py todos       # todos os que têm chave
```
Faz uma chamada real mínima e mostra tempo, tokens e o que foi extraído de um texto de exemplo. Deve listar `Lena` (personagem) e `Vale Claro` (local).

### 5. Usar no aplicativo
Na janela, escolha o provedor em Configurações (o campo Modelo vazio usa o padrão) e clique em **Testar conexão com a IA**. Pela linha de comando:
```bash
python gamemind.py processar --jogo "Meu jogo" --pasta "<pasta de capturas>" --ia gemini
```
A resposta de cada mídia fica guardada por IA: trocar de provedor não apaga a resposta do outro, e só as mídias sem resposta da IA escolhida são enviadas.

### 6. Comparar com o modelo local
`scripts/avaliar_aplicativo.py` mede o aplicativo contra o gabarito com a IA que você passar:
```bash
python scripts/avaliar_aplicativo.py --ia gemini --so aprendido,com_ia
```
As respostas da IA pública passam pelo mesmo `normalizar()` do modelo local (nomes pelo dicionário, tipos e predicados pela ontologia, descarte do que não está no texto), então a comparação é justa.

## Usar no seu código
```python
from extracao.ia_publica import criar_backend
backend = criar_backend("claude")            # ou "openai:gpt-5", "gemini", "ollama:qwen2.5:7b"
saida, meta = backend.extrair({"missao": "Fale com Lena."}, ["missao: O Campo de Feira"])
# saida = {"entidades": [...], "relacoes": [...]}; meta = {"tempo_s", "tokens_entrada", "tokens_saida", ...}
```
Para um provedor novo, crie uma subclasse de `BackendNuvem` em `src/extracao/ia_publica.py` com `_chamar()` (montar o pedido e devolver o JSON e os tokens) e registre-a em `BACKENDS`. Qualquer serviço com API compatível com a da OpenAI (gateways, servidores locais como LM Studio ou vLLM) funciona com `OpenAIBackend(modelo, chave, url="http://localhost:1234/v1")`.

## Como cada provedor é chamado
Todos os pedidos usam o mesmo texto de instruções (`src/extracao/llm.py`) e forçam saída em JSON no esquema do GameMind, de modo que a resposta é sempre parseável:

| Provedor | Endpoint | Saída estruturada |
|---|---|---|
| OpenAI | `POST /v1/chat/completions` | `response_format` com `json_schema` estrito |
| Gemini | `POST /v1beta/models/{modelo}:generateContent` | `responseMimeType` JSON + `responseSchema` |
| Claude | `POST /v1/messages` | ferramenta obrigatória (`tool_choice`) com o esquema como `input_schema` |

Erros transitórios (429 e 5xx) são repetidos até 4 vezes com espera crescente; os demais viram uma mensagem curta dizendo o que fazer.

## Problemas comuns
| Mensagem | Causa e solução |
|---|---|
| `Chave de API do ... não encontrada` | Variável ausente: confira o nome em `.env` (sem espaços ao redor do `=`) e rode a partir da raiz do projeto ou com a variável exportada. |
| `HTTP 401/403 (chave inválida ou sem permissão)` | Chave errada, revogada, ou conta sem crédito/faturamento. |
| `HTTP 404 (modelo inexistente?)` | Nome do modelo errado ou sem acesso; use `provedor:modelo` com um nome atual. |
| `HTTP 429` persistente | Limite de requisições ou de cota; use `--limite`, espere ou suba o plano. |
| Resultado vazio sem erro | O modelo devolveu JSON inválido (raro); repita ou troque de modelo. |

## Testes
`python -m unittest discover -s tests -v` roda testes offline (HTTP simulado) que validam o pedido e a leitura da resposta de cada provedor, o tratamento de erros e a nova tentativa. **Eles não substituem o `testar_conector.py`**: só uma chamada real confirma que a sua chave e o modelo escolhido funcionam.
