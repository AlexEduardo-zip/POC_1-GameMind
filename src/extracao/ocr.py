"""OCR de uma imagem com Tesseract. Devolve o texto e o tempo gasto."""
import time
from pathlib import Path

import pytesseract
from PIL import Image


def ocr_imagem(caminho: Path, lang: str = "por+eng") -> tuple[str, float]:
    t0 = time.perf_counter()
    texto = pytesseract.image_to_string(Image.open(caminho), lang=lang)
    return texto, time.perf_counter() - t0
