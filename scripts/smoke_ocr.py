"""Teste de fumaça de OCR. Uso: python scripts/smoke_ocr.py data/raw/*.png --lang por+eng"""
import argparse
from PIL import Image
import pytesseract

ap = argparse.ArgumentParser()
ap.add_argument("arquivos", nargs="+")
ap.add_argument("--lang", default="eng")
args = ap.parse_args()

for caminho in args.arquivos:
    texto = pytesseract.image_to_string(Image.open(caminho), lang=args.lang)
    print(f"=== {caminho} ===")
    print(texto.strip() or "(nenhum texto reconhecido)")
    print()
