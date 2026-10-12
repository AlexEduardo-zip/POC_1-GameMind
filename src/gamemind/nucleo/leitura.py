"""Leitura de uma mídia (a parte cara, feita uma vez e guardada no banco): o texto da tela inteira e dos recortes de OCR
(legenda, objetivo, avisos; ver regioes.py). Clipe: o mesmo em um quadro a cada `intervalo` segundos.
O resultado é JSON puro: o dicionário de nomes e a consolidação (dicionario.py, consolidacao.py) rodam depois, sobre o jogo inteiro.
Nada aqui depende de um jogo específico."""
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from extracao.ocr import ocr_secoes, ocr_secoes_img
from extracao.video import amostrar

# suba quando a leitura mudar de um jeito que pede reler as mídias antigas
VERSAO_LEITURA = 3   # 3: sem regras de tela de nenhum jogo; recortes genéricos ou aprendidos (regioes.json)


def ler_imagem(caminho: Path, lang: str = "por+eng", rois: dict | None = None) -> dict:
    return {"tipo": "imagem", "quadros": [{"t": 0.0, "secoes": ocr_secoes(Path(caminho), lang, rois=rois)}]}


def ler_clipe(caminho: Path, intervalo: int = 2, workers: int = 4, lang: str = "por+eng", rois: dict | None = None) -> dict:
    quadros = amostrar(Path(caminho), float(intervalo))
    if not quadros:
        raise ValueError(f"nenhum quadro lido de {Path(caminho).name} (FFmpeg instalado?)")
    with ThreadPoolExecutor(max_workers=workers) as ex:
        lidos = list(ex.map(lambda tq: {"t": tq[0], "secoes": ocr_secoes_img(tq[1], lang, rois=rois)}, quadros))
    return {"tipo": "clipe", "intervalo_s": intervalo, "quadros": lidos}


def ler(caminho: Path, tipo: str, intervalo: int = 2, workers: int = 4, lang: str = "por+eng",
        rois: dict | None = None) -> tuple[dict, float]:
    t0 = time.perf_counter()
    leitura = ler_imagem(caminho, lang, rois) if tipo == "imagem" else ler_clipe(caminho, intervalo, workers, lang, rois)
    return leitura, time.perf_counter() - t0
