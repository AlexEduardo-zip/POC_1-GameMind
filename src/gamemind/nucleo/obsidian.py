"""Abrir o vault do jogo no Obsidian. O Obsidian só abre por link (`obsidian://`) os vaults que ele já conhece, que ficam no
`obsidian.json` da pasta de configuração dele. Aqui o vault do jogo é registrado nesse arquivo quando falta (se o Obsidian estiver
fechado: com ele aberto, ele reescreveria o arquivo e perderia o registro) e só então o link é montado."""
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote

from extracao import SEM_JANELA


def pasta_config() -> Path:
    """Pasta de configuração do Obsidian no sistema (OBSIDIAN_CONFIG sobrescreve, para testes)."""
    if os.environ.get("OBSIDIAN_CONFIG"):
        return Path(os.environ["OBSIDIAN_CONFIG"])
    if os.name == "nt":
        return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "obsidian"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "obsidian"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "obsidian"


def _igual(a: str, b: Path) -> bool:
    try:
        return Path(a).resolve() == Path(b).resolve()
    except OSError:
        return False


def _ler(pasta: Path) -> dict:
    try:
        d = json.loads((pasta / "obsidian.json").read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def vault_registrado(vault: Path, config: Path | None = None) -> str | None:
    """Id do vault no Obsidian, se ele já o conhece."""
    for vid, info in _ler(config or pasta_config()).get("vaults", {}).items():
        if isinstance(info, dict) and _igual(info.get("path", ""), vault):
            return vid
    return None


def obsidian_aberto() -> bool:
    try:
        if os.name == "nt":
            r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Obsidian.exe", "/NH"], capture_output=True, text=True, timeout=10, **SEM_JANELA)
            return "obsidian.exe" in r.stdout.lower()
        return subprocess.run(["pgrep", "-xi", "obsidian"], capture_output=True, timeout=10).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def registrar_vault(vault: Path, config: Path | None = None) -> str | None:
    """Acrescenta o vault ao `obsidian.json` (com cópia de segurança do arquivo). Devolve o id, ou None se não foi possível."""
    pasta = config or pasta_config()
    if not pasta.is_dir():
        return None   # o Obsidian nunca foi aberto neste computador (ou não está instalado)
    d = _ler(pasta)
    vid = secrets.token_hex(8)
    d.setdefault("vaults", {})[vid] = {"path": str(Path(vault).resolve()), "ts": int(time.time() * 1000)}
    try:
        arq = pasta / "obsidian.json"
        if arq.exists():
            shutil.copy2(arq, pasta / "obsidian.json.gamemind.bak")
        arq.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    except OSError:
        return None
    return vid


def link(vault: Path, arquivo: Path | None = None, config: Path | None = None) -> tuple[str | None, str]:
    """(link `obsidian://` ou None, mensagem para o usuário se não houver link). `arquivo` abre uma nota do vault."""
    vault = Path(vault)
    vault.mkdir(parents=True, exist_ok=True)
    vid = vault_registrado(vault, config)
    if vid is None:
        if obsidian_aberto():
            return None, ("O Obsidian ainda não conhece este vault e está aberto, então o GameMind não pode registrá-lo agora. "
                          "Feche o Obsidian e clique de novo, ou no Obsidian use \"Abrir pasta como cofre\" e escolha:\n\n" + str(vault))
        vid = registrar_vault(vault, config)
        if vid is None:
            return None, ("Não encontrei a configuração do Obsidian. Instale e abra o Obsidian uma vez, ou use nele "
                          "\"Abrir pasta como cofre\" e escolha:\n\n" + str(vault))
    url = f"obsidian://open?vault={vid}"
    if arquivo is not None:
        try:
            rel = Path(arquivo).resolve().relative_to(vault.resolve()).with_suffix("") if str(arquivo).endswith(".md") else \
                Path(arquivo).resolve().relative_to(vault.resolve())
            url += "&file=" + quote(rel.as_posix())
        except ValueError:
            pass
    return url, ""
