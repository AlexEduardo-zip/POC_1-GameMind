"""Pré-processamento de capturas para OCR: recorta uma região, amplia e clareia o texto.
Coordenadas relativas (x0, y0, x1, y1), a partir do canto superior esquerdo."""
import cv2
import numpy as np

# Regiões genéricas, iguais para qualquer jogo: a maioria põe a legenda na faixa de baixo, o objetivo num canto de cima e os avisos no
# alto, à esquerda ou ao centro. São o ponto de partida; `regioes.py` as refina por jogo e as guarda em regioes.json.
ROIS = {
    "legenda": (0.08, 0.68, 0.92, 0.92),
    "hud": (0.62, 0.12, 1.00, 0.55),
    "aviso": (0.00, 0.10, 0.62, 0.70),
}
# modo de segmentação de página do Tesseract por região: 6 = bloco de texto, 11 = texto esparso (HUD, com poucas palavras soltas)
PSM = {"legenda": 6, "hud": 11, "aviso": 6}


def recortar(img: np.ndarray, roi: tuple) -> np.ndarray:
    h, w = img.shape[:2]
    x0, y0, x1, y1 = roi
    return img[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)]


def preparar(img: np.ndarray, filtro: str, escala: float = 2.5) -> np.ndarray:
    """Devolve imagem em tons de cinza, ampliada, com texto escuro sobre fundo claro."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    g = cv2.resize(g, None, fx=escala, fy=escala, interpolation=cv2.INTER_CUBIC)
    if filtro == "cinza":
        return g
    if filtro == "otsu":
        _, b = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return b if b.mean() > 127 else 255 - b  # texto escuro sobre fundo claro
    if filtro == "brilho":
        # o texto do jogo é claro (branco ou amarelo) com contorno escuro: fica só o que é bem claro
        t = max(150, int(np.percentile(g, 99.0) * 0.75))
        return np.where(g > t, 0, 255).astype(np.uint8)
    raise ValueError(f"filtro desconhecido: {filtro}")
