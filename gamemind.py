"""Ponto de entrada do aplicativo GameMind. Sem argumentos abre a janela; `python gamemind.py --help` lista os comandos."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from gamemind.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
