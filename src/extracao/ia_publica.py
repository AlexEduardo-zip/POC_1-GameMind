"""IA fora do computador: Claude pelo Claude Code instalado, com o login da assinatura do usuário (sem chave de API e sem cobrança
por token). Tem a mesma interface do `OllamaBackend` (llm.py): `extrair` para a extração e `perguntar` para as perguntas livres
(revisão das entidades). Só texto sai do computador, nunca imagem: `perguntar` recusa imagens.
As IAs cobradas por token (OpenAI, Gemini, API da Anthropic) foram retiradas do aplicativo por enquanto; estão no histórico do git.
Uso: `criar_backend("claude-code")`, `criar_backend("claude-code:sonnet")`, `criar_backend("ollama:qwen2.5:7b")`."""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from .llm import ESQUEMA, Backend, OllamaBackend, instrucoes, montar_pedido

RAIZ = Path(__file__).resolve().parent.parent.parent

# modelo padrão de cada provedor (troque com "provedor:modelo")
MODELOS_PADRAO = {"claude-code": "haiku", "ollama": "qwen2.5:7b"}
# nomes alternativos aceitos para o provedor
APELIDOS = {"claude": "claude-code", "anthropic": "claude-code", "claudecode": "claude-code", "claude_code": "claude-code", "local": "ollama"}
# provedores por chave de API que o aplicativo não oferece mais: uma configuração antiga com eles dá um aviso claro
RETIRADOS = {"openai", "chatgpt", "gpt", "codex", "gemini", "google"}
TEMPO_CHAMADA_S = 300


class ErroConector(RuntimeError):
    """Falha de configuração ou de chamada à IA, com mensagem pensada para o usuário."""


def carregar_env(caminho: Path | None = None) -> None:
    """Lê `KEY=valor` do `.env` (ex.: CLAUDE_CODE_PATH) e os coloca em os.environ sem sobrescrever o que já está definido."""
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


class ClaudeCodeBackend(Backend):
    """Claude pelo Claude Code instalado (`claude -p`), com o login da assinatura (Pro/Max). Consome a cota de uso do plano e é
    mais lento que o Ollama (um processo por chamada, ~10 s); sem ferramentas, sem sessão gravada e só com texto."""

    def __init__(self, modelo: str = "", executavel: str = ""):
        self.modelo = modelo or MODELOS_PADRAO["claude-code"]
        self.exe = executavel or achar_claude()
        self.nome = f"claude-code:{self.modelo}"

    def _rodar(self, instr: str, pedido: str, esquema: dict) -> tuple[dict, dict]:
        """Uma chamada: (resposta no `esquema`, o JSON completo do Claude Code, com uso e tempo)."""
        cmd = [self.exe, "-p", "--output-format", "json", "--json-schema", json.dumps(esquema), "--system-prompt", instr, "--tools", "",
               "--no-session-persistence", "--disable-slash-commands", "--model", self.modelo]
        try:
            r = subprocess.run(cmd, input=pedido, capture_output=True, text=True, encoding="utf-8", timeout=TEMPO_CHAMADA_S)
        except subprocess.TimeoutExpired:
            raise ErroConector(f"{self.nome}: sem resposta em {TEMPO_CHAMADA_S} s") from None
        except OSError as e:
            raise ErroConector(f"{self.nome}: não consegui executar {self.exe}: {e}") from None
        try:
            d = json.loads(r.stdout)
        except ValueError:
            d = {}
        if r.returncode != 0 or d.get("is_error"):
            msg = (d.get("result") if isinstance(d.get("result"), str) else "") or r.stderr.strip() or r.stdout.strip()
            dica = " Entre com a sua conta: rode `claude` uma vez (no aplicativo: Configurar jogo > Entrar com a conta Claude)." \
                if any(k in msg.lower() for k in ("login", "logged", "auth")) else ""
            raise ErroConector(f"{self.nome}: {msg[:400]}{dica}")
        saida = d.get("structured_output")
        if not isinstance(saida, dict):
            try:
                saida = json.loads(d.get("result", ""))
            except (ValueError, TypeError):
                saida = {}
        return (saida if isinstance(saida, dict) else {}), d

    def extrair(self, secoes, detectado):
        t0 = time.perf_counter()
        saida, d = self._rodar(instrucoes(), montar_pedido(secoes, detectado), ESQUEMA)
        saida.setdefault("entidades", [])
        saida.setdefault("relacoes", [])
        u = d.get("usage", {})
        tempo = round(time.perf_counter() - t0, 2)
        return saida, {"tempo_s": tempo, "tokens_entrada": u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0),
                       "tokens_saida": u.get("output_tokens", 0), "tempo_geracao_s": round(d.get("duration_api_ms", 0) / 1000, 2)}

    def perguntar(self, instrucoes: str, pedido: str, esquema: dict, imagens: list[str] | None = None) -> dict:
        if imagens:   # imagens não saem do computador: só o modelo de imagem do Ollama as recebe
            raise NotImplementedError(f"{self.nome} não recebe imagens")
        return self._rodar(instrucoes, pedido, esquema)[0]


def achar_claude() -> str:
    """O executável do Claude Code: CLAUDE_CODE_PATH, o PATH ou a extensão do VS Code (que não o põe no PATH)."""
    carregar_env()
    if os.environ.get("CLAUDE_CODE_PATH"):
        return os.environ["CLAUDE_CODE_PATH"]
    if achado := shutil.which("claude"):
        return achado
    ext = sorted((Path.home() / ".vscode" / "extensions").glob("anthropic.claude-code-*/resources/native-binary/claude*"))
    if ext:
        return str(ext[-1])
    raise ErroConector("Claude Code não encontrado. Instale (https://claude.com/claude-code) e entre com a sua conta; se ele não "
                       "estiver no PATH, defina CLAUDE_CODE_PATH no arquivo .env com o caminho do executável.")


def abrir_login() -> None:
    """Abre o Claude Code num terminal novo para o usuário entrar com a conta (ele mesmo pede o login se faltar). Levanta
    ErroConector se o Claude Code não for encontrado ou se não houver como abrir um terminal."""
    exe = achar_claude()
    try:
        if os.name == "nt":
            subprocess.Popen([exe], creationflags=subprocess.CREATE_NEW_CONSOLE)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-a", "Terminal", exe])
        else:
            terminal = next((t for t in ("x-terminal-emulator", "gnome-terminal", "konsole", "xterm") if shutil.which(t)), None)
            if not terminal:
                raise OSError("nenhum terminal encontrado")
            subprocess.Popen([terminal, "-e", exe])
    except OSError as e:
        raise ErroConector(f"Não consegui abrir um terminal ({e}). Abra um e rode: {exe}") from None


def criar_backend(spec: str = "ollama") -> Backend:
    """`provedor` ou `provedor:modelo`. Sem prefixo de provedor conhecido, o texto inteiro é tratado como modelo do Ollama (compatível com `--modelo`)."""
    prov, _, modelo = spec.partition(":")
    prov_n = APELIDOS.get(prov.lower(), prov.lower())
    if prov_n in RETIRADOS:
        raise ErroConector(f"A IA por chave de API ({prov}) não está mais no aplicativo. Escolha o Ollama (no computador) ou o Claude "
                           f"com o login da sua conta, em Jogo > Configurar jogo.")
    if prov_n not in MODELOS_PADRAO:
        return OllamaBackend(spec)
    if prov_n == "ollama":
        return OllamaBackend(modelo or MODELOS_PADRAO["ollama"])
    return ClaudeCodeBackend(modelo)
