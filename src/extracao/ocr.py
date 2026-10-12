"""OCR com Tesseract: o texto da tela inteira e de cada recorte (legenda, objetivo, avisos; ver preprocessamento.py e regioes.py)."""
from pathlib import Path

import cv2
import numpy as np
import pytesseract
from PIL import Image

from .preprocessamento import PSM, ROIS, preparar, recortar


def _ler(caminho: Path) -> np.ndarray:
    # cv2.imread falha em caminhos com acento no Windows; decodifica os bytes
    return cv2.imdecode(np.fromfile(str(caminho), dtype=np.uint8), cv2.IMREAD_COLOR)


def ocr_secoes_img(img: np.ndarray, lang: str = "por+eng", filtro: str = "brilho", rois: dict | None = None) -> dict[str, str]:
    """Como `ocr_secoes`, mas sobre um quadro já em memória (BGR), por exemplo de um vídeo."""
    secoes = {"tela": pytesseract.image_to_string(Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)), lang=lang)}
    for nome, roi in (rois or ROIS).items():
        secoes[nome] = pytesseract.image_to_string(preparar(recortar(img, roi), filtro), lang=lang, config=f"--psm {PSM[nome]}")
    return secoes


def ocr_secoes(caminho: Path, lang: str = "por+eng", filtro: str = "brilho", rois: dict | None = None) -> dict[str, str]:
    """OCR separado por região (tela inteira, legenda, hud, aviso), para dar contexto a um LLM."""
    img = _ler(caminho)
    secoes = {"tela": pytesseract.image_to_string(Image.open(caminho), lang=lang)}
    for nome, roi in (rois or ROIS).items():
        secoes[nome] = pytesseract.image_to_string(preparar(recortar(img, roi), filtro), lang=lang, config=f"--psm {PSM[nome]}")
    return secoes
