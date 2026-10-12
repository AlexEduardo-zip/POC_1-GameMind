"""Onde ficam os arquivos: recursos do programa (ontologia), a configuração do usuário e a pasta `jogos/` (um jogo por pasta, com
banco, grafo e vault), criada ao lado do programa. Nada aqui é específico de um jogo."""
import os
import sys
from pathlib import Path

# raiz do programa: a do repositório em desenvolvimento ou a pasta extraída pelo PyInstaller no executável
RAIZ = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[3]))

# onde o programa é executado: a pasta do .exe quando empacotado; em desenvolvimento, a raiz do repositório
RAIZ_EXECUCAO = Path(sys.executable).parent if getattr(sys, "frozen", False) else RAIZ

EXT_IMAGEM = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
EXT_CLIPE = {".mp4", ".mkv", ".mov", ".webm"}


def pasta_jogos() -> Path:
    """`jogos/` na raiz de onde o programa roda (GAMEMIND_DADOS sobrescreve a raiz: testes, portátil)."""
    base = Path(os.environ["GAMEMIND_DADOS"]) if os.environ.get("GAMEMIND_DADOS") else RAIZ_EXECUCAO
    p = base / "jogos"
    p.mkdir(parents=True, exist_ok=True)
    return p


def pasta_usuario() -> Path:
    """%LOCALAPPDATA%/GameMind no Windows, ~/.local/share/gamemind no Linux. GAMEMIND_DADOS sobrescreve (testes, portátil)."""
    if os.environ.get("GAMEMIND_DADOS"):
        p = Path(os.environ["GAMEMIND_DADOS"])
    elif os.name == "nt":
        p = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "GameMind"
    else:
        p = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "gamemind"
    p.mkdir(parents=True, exist_ok=True)
    return p
