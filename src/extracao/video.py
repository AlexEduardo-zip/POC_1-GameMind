"""Amostragem de quadros de vídeo com FFmpeg: um quadro por intervalo, no tamanho do próprio vídeo."""
import subprocess
from pathlib import Path

import cv2
import numpy as np


def _tamanho(caminho: Path) -> tuple[int, int]:
    cap = cv2.VideoCapture(str(caminho))
    try:
        return int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    finally:
        cap.release()


def amostrar(caminho: Path, intervalo: float = 1.0) -> list[tuple[float, np.ndarray]]:
    """Quadros BGR a cada `intervalo` segundos. O FFmpeg reduz a taxa, de modo que cada quadro lido corresponde a
    t = i * intervalo (aproximado)."""
    largura, altura = _tamanho(Path(caminho))
    if not largura or not altura:
        return []
    cmd = ["ffmpeg", "-loglevel", "error", "-i", str(caminho), "-an", "-vf", f"fps=1/{intervalo}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    tam = largura * altura * 3
    quadros = []
    with subprocess.Popen(cmd, stdout=subprocess.PIPE) as p:
        while True:
            buf = p.stdout.read(tam)
            if len(buf) < tam:
                break
            quadros.append((len(quadros) * intervalo, np.frombuffer(buf, np.uint8).reshape(altura, largura, 3).copy()))
    return quadros
