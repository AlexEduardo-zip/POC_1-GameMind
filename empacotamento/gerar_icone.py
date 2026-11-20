"""Grava o logo do GameMind (o mesmo da janela, no tema padrão) em build/gamemind.png e build/gamemind.ico para o executável.
Uso: python empacotamento/gerar_icone.py (sem tela: QT_QPA_PLATFORM=offscreen)."""
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from gamemind.ui.aparencia import logo  # noqa: E402
from gamemind.ui.temas import PADRAO, tema  # noqa: E402


def main() -> None:
    app = QApplication.instance() or QApplication([])   # o QPixmap precisa de uma aplicação
    saida = RAIZ / "build"
    saida.mkdir(exist_ok=True)
    png = saida / "gamemind.png"
    logo(tema(PADRAO), 256).save(str(png))
    Image.open(png).save(saida / "gamemind.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"ícone em {saida}")
    app.quit()


if __name__ == "__main__":
    main()
