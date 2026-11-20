# Empacotamento do GameMind com PyInstaller (uma pasta com o executável e as bibliotecas; a pasta jogos/ é criada ao lado dele).
# Uso, da raiz do repositório:
#   python empacotamento/gerar_icone.py
#   pyinstaller --noconfirm empacotamento/gamemind.spec      -> dist/GameMind/
# Tesseract, FFmpeg, Ollama e Claude Code ficam fora: são programas do sistema que o aplicativo procura e o diagnóstico verifica.
import sys
from pathlib import Path

RAIZ = Path(SPECPATH).parent
icone = RAIZ / "build" / ("gamemind.ico" if sys.platform == "win32" else "gamemind.png")

a = Analysis(
    [str(RAIZ / "empacotamento" / "iniciar.py")],
    pathex=[str(RAIZ / "src")],
    datas=[(str(RAIZ / "src" / "ontologia.json"), ".")],
    excludes=["tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="GameMind",
    console=False,
    icon=str(icone) if icone.exists() else None,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="GameMind", upx=False)
