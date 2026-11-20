"""Ponto de entrada do executável. O `gamemind.py` da raiz não serve ao PyInstaller: com o mesmo nome do pacote, o
`import gamemind` dele resolveria para ele mesmo, e o pacote (src/gamemind) ficaria de fora."""
import sys

from gamemind.cli import main

if __name__ == "__main__":
    sys.exit(main())
