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


def ocr_regioes(img: np.ndarray, lang: str = "por+eng", filtro: str = "brilho", rois: dict | None = None) -> dict[str, str]:
    """Só os recortes (legenda, hud, aviso): o texto de cada região da tela."""
    return {nome: pytesseract.image_to_string(preparar(recortar(img, roi), filtro), lang=lang, config=f"--psm {PSM[nome]}")
            for nome, roi in (rois or ROIS).items()}


def ocr_secoes_img(img: np.ndarray, lang: str = "por+eng", filtro: str = "brilho", rois: dict | None = None) -> dict[str, str]:
    """Como `ocr_secoes`, mas sobre um quadro já em memória (BGR), por exemplo de um vídeo."""
    tela = pytesseract.image_to_string(Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)), lang=lang)
    return {"tela": tela, **ocr_regioes(img, lang, filtro, rois)}


def ocr_secoes(caminho: Path, lang: str = "por+eng", filtro: str = "brilho", rois: dict | None = None) -> dict[str, str]:
    """OCR separado por região (tela inteira, legenda, hud, aviso), para dar contexto a um LLM."""
    return {"tela": pytesseract.image_to_string(Image.open(caminho), lang=lang), **ocr_regioes(_ler(caminho), lang, filtro, rois)}
