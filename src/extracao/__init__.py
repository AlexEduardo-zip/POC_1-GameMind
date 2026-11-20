"""Camada de extração do GameMind: imagem -> texto (ocr) -> entidades (gazetteer)."""
import os
import shutil
import subprocess
from pathlib import Path

# para subprocess: no Windows, o executável empacotado (sem console) abriria uma janela preta a cada chamada (ffmpeg, Claude Code...)
SEM_JANELA = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}


def _tesseract_no_path() -> None:
    """O instalador do Tesseract para Windows não o põe no PATH por padrão: se ele não estiver lá, procura nas pastas de
    instalação de sempre e acrescenta a que tiver o tesseract.exe ao PATH deste processo (pytesseract e o diagnóstico usam o PATH)."""
    if os.name != "nt" or shutil.which("tesseract"):
        return
    pastas = [Path(os.environ[v]) / "Tesseract-OCR" for v in ("ProgramFiles", "ProgramFiles(x86)") if os.environ.get(v)]
    if os.environ.get("LOCALAPPDATA"):
        pastas += [Path(os.environ["LOCALAPPDATA"]) / "Programs" / "Tesseract-OCR", Path(os.environ["LOCALAPPDATA"]) / "Tesseract-OCR"]
    for pasta in pastas:
        if (pasta / "tesseract.exe").exists():
            os.environ["PATH"] = f"{pasta}{os.pathsep}{os.environ.get('PATH', '')}"
            return


_tesseract_no_path()
