"""OCR de uma imagem com Tesseract. Devolve o texto e o tempo gasto.
Modos: `completo` (imagem inteira, como na B1) e `<regioes>_<filtro>`, por exemplo `rois_otsu`,
que soma ao OCR da imagem inteira o de recortes ampliados (ver preprocessamento.py)."""
import time
from pathlib import Path

import cv2
import numpy as np
import pytesseract
from PIL import Image

from .preprocessamento import FILTROS, PSM, ROIS, preparar, recortar

MODOS = ["completo", "inteira_cinza"] + [f"rois_{f}" for f in FILTROS] + ["rois_mix"]


def _ler(caminho: Path) -> np.ndarray:
    # cv2.imread falha em caminhos com acento no Windows; decodifica os bytes
    return cv2.imdecode(np.fromfile(str(caminho), dtype=np.uint8), cv2.IMREAD_COLOR)


def ocr_imagem(caminho: Path, lang: str = "por+eng", modo: str = "completo") -> tuple[str, float]:
    t0 = time.perf_counter()
    if modo == "completo":
        texto = pytesseract.image_to_string(Image.open(caminho), lang=lang)
        return texto, time.perf_counter() - t0
    img = _ler(caminho)
    if modo == "inteira_cinza":
        textos = [pytesseract.image_to_string(preparar(img, "cinza", 2.0), lang=lang)]
    elif modo.startswith("rois_"):
        # rois_mix soma os filtros cinza e brilho; os demais usam um filtro só
        filtros = ("cinza", "brilho") if modo == "rois_mix" else (modo.split("_", 1)[1],)
        textos = [pytesseract.image_to_string(Image.open(caminho), lang=lang)]
        for nome, roi in ROIS.items():
            for filtro in filtros:
                textos.append(pytesseract.image_to_string(preparar(recortar(img, roi), filtro), lang=lang, config=f"--psm {PSM[nome]}"))
    else:
        raise ValueError(f"modo desconhecido: {modo} (use um de {MODOS})")
    return "\n".join(textos), time.perf_counter() - t0


def ocr_secoes_img(img: np.ndarray, lang: str = "por+eng", filtro: str = "brilho") -> dict[str, str]:
    """Como `ocr_secoes`, mas sobre um quadro já em memória (BGR), por exemplo de um vídeo."""
    secoes = {"tela": pytesseract.image_to_string(Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)), lang=lang)}
    for nome, roi in ROIS.items():
        secoes[nome] = pytesseract.image_to_string(preparar(recortar(img, roi), filtro), lang=lang, config=f"--psm {PSM[nome]}")
    return secoes


def ocr_secoes(caminho: Path, lang: str = "por+eng", filtro: str = "brilho") -> dict[str, str]:
    """OCR separado por região (tela inteira, legenda, hud, aviso), para dar contexto a um LLM."""
    img = _ler(caminho)
    secoes = {"tela": pytesseract.image_to_string(Image.open(caminho), lang=lang)}
    for nome, roi in ROIS.items():
        secoes[nome] = pytesseract.image_to_string(preparar(recortar(img, roi), filtro), lang=lang, config=f"--psm {PSM[nome]}")
    return secoes
