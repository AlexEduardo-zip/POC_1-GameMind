"""Amostragem de quadros de vídeo (etapa B4), com FFmpeg: um quadro por intervalo, no corte de 1920x1080."""
import subprocess
from pathlib import Path

import numpy as np

LARGURA, ALTURA = 1920, 1080


def amostrar(caminho: Path, intervalo: float = 1.0) -> list[tuple[float, np.ndarray]]:
    """Quadros BGR a cada `intervalo` segundos. Os clipes do Adrenalin têm 1920x1088 a 60 fps: corta-se o excesso
    de altura e o FFmpeg reduz a taxa, de modo que cada quadro lido corresponde a t = i * intervalo (aproximado)."""
    cmd = ["ffmpeg", "-loglevel", "error", "-i", str(caminho), "-an", "-vf", f"fps=1/{intervalo},crop={LARGURA}:{ALTURA}:0:4",
           "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    tam = LARGURA * ALTURA * 3
    quadros = []
    with subprocess.Popen(cmd, stdout=subprocess.PIPE) as p:
        while True:
            buf = p.stdout.read(tam)
            if len(buf) < tam:
                break
            quadros.append((len(quadros) * intervalo, np.frombuffer(buf, np.uint8).reshape(ALTURA, LARGURA, 3).copy()))
    return quadros
