"""Conector de IA pública (OpenAI/ChatGPT/Codex, Google Gemini e Anthropic Claude) para a extração de entidades e relações.
Cada provedor é um `Backend` com a mesma interface do `OllamaBackend`: recebe o texto lido da tela e devolve o JSON do esquema do GameMind.
Só o texto do OCR vai para a nuvem (nunca a imagem). Sem SDKs: usa só a biblioteca padrão (urllib).
A chave de API vem de variável de ambiente ou do arquivo `.env` na raiz do projeto (ver docs/ia-publica.md).
Também há `claude-code`, que usa o Claude Code instalado e o login da assinatura (sem chave de API).
Uso: `criar_backend("openai:gpt-5-mini")`, `criar_backend("gemini")`, `criar_backend("claude:claude-haiku-4-5-20251001")`, `criar_backend("ollama:qwen2.5:7b")`."""
import copy
import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from .llm import ESQUEMA, Backend, OllamaBackend, instrucoes, montar_pedido

RAIZ = Path(__file__).resolve().parent.parent.parent

# modelo padrão de cada provedor (barato e rápido; troque com "provedor:modelo")
MODELOS_PADRAO = {"openai": "gpt-5-mini", "gemini": "gemini-2.5-flash", "claude": "claude-haiku-4-5-20251001", "claude-code": "haiku", "ollama": "qwen2.5:7b"}
# nomes alternativos aceitos para o provedor
APELIDOS = {"chatgpt": "openai", "gpt": "openai", "codex": "openai", "google": "gemini", "anthropic": "claude", "claudecode": "claude-code", "claude_code": "claude-code", "local": "ollama"}
# variáveis de ambiente com a chave, em ordem de preferência
VARIAVEIS_CHAVE = {"openai": ("OPENAI_API_KEY",), "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"), "claude": ("ANTHROPIC_API_KEY", "CLAUDE_API_KEY")}
MAX_SAIDA = 4096  # teto de tokens de saída; modelos com raciocínio gastam parte disso pensando (a resposta em si tem ~300)
TENTATIVAS = 4


class ErroConector(RuntimeError):
    """Falha de configuração ou de chamada ao provedor, com mensagem pensada para quem está rodando o script."""


def carregar_env(caminho: Path | None = None) -> None:
    """Lê `KEY=valor` do `.env` e os coloca em os.environ sem sobrescrever o que já está definido."""
    caminho = caminho or RAIZ / ".env"
    if not caminho.exists():
        return
    for linha in caminho.read_text(encoding="utf-8-sig").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        k, v = linha.split("=", 1)
        k, v = k.strip().removeprefix("export ").strip(), v.strip().strip("\"'")
        if v:
            os.environ.setdefault(k, v)


def _esquema_estrito() -> dict:
    """Esquema aceito pelo modo estrito do OpenAI: todas as propriedades obrigatórias e sem campos extras (o `subtipo` não é usado)."""
    def limpa(s: dict) -> dict:
        s = copy.deepcopy(s)
        if s.get("type") == "object":
            s["properties"] = {k: limpa(v) for k, v in s["properties"].items() if k != "subtipo"}
            s["required"] = list(s["properties"])
            s["additionalProperties"] = False
        elif s.get("type") == "array":
            s["items"] = limpa(s["items"])
        return s
    return limpa(ESQUEMA)


def _esquema_gemini() -> dict:
    """Subconjunto OpenAPI do Gemini: tipos em maiúsculas e sem `additionalProperties`."""
    def conv(s: dict) -> dict:
        s = {k: v for k, v in s.items() if k != "additionalProperties"}
        s["type"] = s["type"].upper()
        if "properties" in s:
            s["properties"] = {k: conv(v) for k, v in s["properties"].items()}
        if "items" in s:
            s["items"] = conv(s["items"])
        return s
    return conv(ESQUEMA)


class BackendNuvem(Backend):
    """Base dos provedores públicos: chave, POST com tentativas e medição. As subclasses montam o pedido e leem a resposta."""
    provedor = ""

    def __init__(self, modelo: str = "", chave: str = "", url: str = ""):
        carregar_env()
        self.modelo = modelo or MODELOS_PADRAO[self.provedor]
        self.chave = chave or next((os.environ[v] for v in VARIAVEIS_CHAVE[self.provedor] if os.environ.get(v)), "")
        if not self.chave:
            raise ErroConector(f"Chave de API do {self.provedor} não encontrada. Defina {VARIAVEIS_CHAVE[self.provedor][0]} no ambiente "
                               f"ou no arquivo .env (modelo em .env.example; veja docs/ia-publica.md).")
        self.url = url or self.url_padrao
        self.nome = f"{self.provedor}:{self.modelo}"

    def _post(self, url: str, corpo: dict, cabecalhos: dict) -> dict:
        req = urllib.request.Request(url, data=json.dumps(corpo).encode(), headers={"Content-Type": "application/json", **cabecalhos})
        for tentativa in range(1, TENTATIVAS + 1):
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    return json.load(r)
            except urllib.error.HTTPError as e:
                detalhe = e.read().decode("utf-8", "replace")[:400]
                if e.code in (429, 500, 502, 503, 504, 529) and tentativa < TENTATIVAS:
                    espera = float(e.headers.get("Retry-After") or 0) or 2 ** tentativa
                    time.sleep(min(espera, 30))
                    continue
                dica = " (chave inválida ou sem permissão)" if e.code in (401, 403) else " (modelo inexistente?)" if e.code == 404 else ""
                raise ErroConector(f"{self.nome}: HTTP {e.code}{dica}: {detalhe}") from None
            except (urllib.error.URLError, TimeoutError) as e:
                if tentativa < TENTATIVAS:
                    time.sleep(2 ** tentativa)
                    continue
                raise ErroConector(f"{self.nome}: sem conexão com {url.split('?')[0]}: {e}") from None
        raise ErroConector(f"{self.nome}: falha após {TENTATIVAS} tentativas")

    def _chamar(self, instr: str, pedido: str) -> tuple[str | dict, int, int]:
        """Devolve (JSON da resposta como texto ou dict, tokens de entrada, tokens de saída)."""
        raise NotImplementedError

    def extrair(self, secoes, detectado):
        t0 = time.perf_counter()
        bruto, t_ent, t_sai = self._chamar(instrucoes(), montar_pedido(secoes, detectado))
        try:
            saida = json.loads(bruto) if isinstance(bruto, str) else bruto
            if not isinstance(saida, dict):
                raise ValueError
        except (ValueError, TypeError):
            saida = {"entidades": [], "relacoes": []}
        saida.setdefault("entidades", [])
        saida.setdefault("relacoes", [])
        tempo = round(time.perf_counter() - t0, 2)
        return saida, {"tempo_s": tempo, "tokens_entrada": t_ent, "tokens_saida": t_sai, "tempo_geracao_s": tempo}


class OpenAIBackend(BackendNuvem):
    """OpenAI (ChatGPT/Codex): Chat Completions com saída estruturada. Serve também a qualquer API compatível (passe `url`)."""
    provedor = "openai"
    url_padrao = "https://api.openai.com/v1"

    def _chamar(self, instr, pedido):
        corpo = {"model": self.modelo, "max_completion_tokens": MAX_SAIDA,
                 "response_format": {"type": "json_schema", "json_schema": {"name": "extracao", "strict": True, "schema": _esquema_estrito()}},
                 "messages": [{"role": "system", "content": instr}, {"role": "user", "content": pedido}]}
        r = self._post(self.url.rstrip("/") + "/chat/completions", corpo, {"Authorization": f"Bearer {self.chave}"})
        try:
            texto = r["choices"][0]["message"]["content"] or "{}"
        except (KeyError, IndexError):
            texto = "{}"
        u = r.get("usage", {})
        return texto, u.get("prompt_tokens", 0), u.get("completion_tokens", 0)


class GeminiBackend(BackendNuvem):
    """Google Gemini: generateContent com `responseSchema`."""
    provedor = "gemini"
    url_padrao = "https://generativelanguage.googleapis.com/v1beta"

    def _chamar(self, instr, pedido):
        corpo = {"systemInstruction": {"parts": [{"text": instr}]},
                 "contents": [{"role": "user", "parts": [{"text": pedido}]}],
                 "generationConfig": {"temperature": 0, "maxOutputTokens": MAX_SAIDA, "responseMimeType": "application/json",
                                      "responseSchema": _esquema_gemini()}}
        r = self._post(f"{self.url.rstrip('/')}/models/{self.modelo}:generateContent", corpo, {"x-goog-api-key": self.chave})
        try:
            texto = "".join(p.get("text", "") for p in r["candidates"][0]["content"]["parts"]) or "{}"
        except (KeyError, IndexError):
            texto = "{}"
        u = r.get("usageMetadata", {})
        return texto, u.get("promptTokenCount", 0), u.get("candidatesTokenCount", 0)


class ClaudeBackend(BackendNuvem):
    """Anthropic Claude: Messages API com uma ferramenta obrigatória cujo esquema é o da extração (garante JSON válido)."""
    provedor = "claude"
    url_padrao = "https://api.anthropic.com/v1"

    def _chamar(self, instr, pedido):
        corpo = {"model": self.modelo, "max_tokens": MAX_SAIDA, "temperature": 0, "system": instr,
                 "tools": [{"name": "registrar_extracao", "description": "Registra as entidades e relações extraídas da tela.", "input_schema": ESQUEMA}],
                 "tool_choice": {"type": "tool", "name": "registrar_extracao"},
                 "messages": [{"role": "user", "content": pedido}]}
        r = self._post(self.url.rstrip("/") + "/messages", corpo, {"x-api-key": self.chave, "anthropic-version": "2023-06-01"})
        saida = next((b.get("input") for b in r.get("content", []) if b.get("type") == "tool_use"), None) or {}
        u = r.get("usage", {})
        return saida, u.get("input_tokens", 0), u.get("output_tokens", 0)


class ClaudeCodeBackend(Backend):
    """Claude pelo Claude Code instalado (`claude -p`), usando o login da assinatura (Pro/Max): sem chave de API e sem cobrança por token.
    Consome a cota de uso do plano, é mais lento (um processo por chamada) e depende de uma pessoa logada; serve para testar, não como produção."""

    def __init__(self, modelo: str = "", executavel: str = ""):
        self.modelo = modelo or MODELOS_PADRAO["claude-code"]
        self.exe = executavel or self._achar()
        self.nome = f"claude-code:{self.modelo}"

    @staticmethod
    def _achar() -> str:
        carregar_env()
        if os.environ.get("CLAUDE_CODE_PATH"):
            return os.environ["CLAUDE_CODE_PATH"]
        if achado := shutil.which("claude"):
            return achado
        # a extensão do VS Code traz o executável sem colocá-lo no PATH
        ext = sorted((Path.home() / ".vscode" / "extensions").glob("anthropic.claude-code-*/resources/native-binary/claude*"))
        if ext:
            return str(ext[-1])
        raise ErroConector("Claude Code não encontrado. Instale (https://claude.com/claude-code), faça login com `claude` e, se não estiver no PATH, "
                           "defina CLAUDE_CODE_PATH com o caminho do executável (docs/ia-publica.md).")

    def extrair(self, secoes, detectado):
        cmd = [self.exe, "-p", "--output-format", "json", "--json-schema", json.dumps(ESQUEMA), "--system-prompt", instrucoes(), "--tools", "",
               "--no-session-persistence", "--disable-slash-commands", "--model", self.modelo]
        t0 = time.perf_counter()
        try:
            r = subprocess.run(cmd, input=montar_pedido(secoes, detectado), capture_output=True, text=True, encoding="utf-8", timeout=300)
        except subprocess.TimeoutExpired:
            raise ErroConector(f"{self.nome}: sem resposta em 300 s") from None
        except OSError as e:
            raise ErroConector(f"{self.nome}: não consegui executar {self.exe}: {e}") from None
        try:
            d = json.loads(r.stdout)
        except ValueError:
            d = {}
        if r.returncode != 0 or d.get("is_error"):
            msg = (d.get("result") if isinstance(d.get("result"), str) else "") or r.stderr.strip() or r.stdout.strip()
            dica = " Rode `claude` uma vez e faça login." if any(k in msg.lower() for k in ("login", "logged", "auth")) else ""
            raise ErroConector(f"{self.nome}: {msg[:400]}{dica}")
        saida = d.get("structured_output")
        if not isinstance(saida, dict):
            try:
                saida = json.loads(d.get("result", ""))
            except (ValueError, TypeError):
                saida = {}
        saida.setdefault("entidades", [])
        saida.setdefault("relacoes", [])
        u = d.get("usage", {})
        tempo = round(time.perf_counter() - t0, 2)
        return saida, {"tempo_s": tempo, "tokens_entrada": u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0),
                       "tokens_saida": u.get("output_tokens", 0), "tempo_geracao_s": round(d.get("duration_api_ms", 0) / 1000, 2)}


BACKENDS = {"openai": OpenAIBackend, "gemini": GeminiBackend, "claude": ClaudeBackend}


def criar_backend(spec: str = "ollama") -> Backend:
    """`provedor` ou `provedor:modelo`. Sem prefixo de provedor conhecido, o texto inteiro é tratado como modelo do Ollama (compatível com `--modelo`)."""
    prov, _, modelo = spec.partition(":")
    prov_n = APELIDOS.get(prov.lower(), prov.lower())
    if prov_n not in MODELOS_PADRAO:
        return OllamaBackend(spec)
    if prov_n == "ollama":
        return OllamaBackend(modelo or MODELOS_PADRAO["ollama"])
    if prov_n == "claude-code":
        return ClaudeCodeBackend(modelo)
    return BACKENDS[prov_n](modelo)
