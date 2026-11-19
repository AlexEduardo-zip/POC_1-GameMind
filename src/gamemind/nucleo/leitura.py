"""Leitura de uma mídia (a parte cara, feita uma vez e guardada no banco): o texto da tela inteira e dos recortes de OCR
(legenda, objetivo, avisos; ver regioes.py). Clipe: o mesmo em um quadro a cada `intervalo` segundos.
O resultado é JSON puro: o dicionário de nomes e a consolidação (dicionario.py, consolidacao.py) rodam depois, sobre o jogo inteiro.
Nada aqui depende de um jogo específico."""
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np

from extracao.ocr import ocr_regioes, ocr_secoes, ocr_secoes_img
from extracao.preprocessamento import ROIS
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


def reler_regioes(caminho: Path, tipo: str, leitura: dict, rois: dict, lang: str = "por+eng") -> dict | None:
    """A mesma leitura com só os recortes `rois` refeitos (as regiões de leitura mudaram). O texto da tela inteira, que é a
    parte cara, e as outras regiões ficam. None se a mídia não pôde ser aberta."""
    nova = json.loads(json.dumps(leitura))
    if tipo == "imagem":
        img = cv2.imdecode(np.fromfile(str(caminho), dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            return None
        imagens = {q["t"]: img for q in nova["quadros"]}
    else:
        imagens = dict(amostrar(Path(caminho), float(nova.get("intervalo_s", 2))))   # os mesmos instantes da primeira leitura
    for q in nova["quadros"]:
        if q["t"] in imagens:
            q["secoes"].update(ocr_regioes(imagens[q["t"]], lang, rois=rois))
    nova["rois"] = {**nova.get("rois", _caixas(ROIS)), **_caixas(rois)}
    return nova


def _caixas(rois: dict) -> dict:
    return {n: [round(v, 3) for v in c] for n, c in rois.items()}


def recortes_desatualizados(leitura: dict, rois: dict) -> list[str]:
    """Regiões em que a leitura foi feita com outra caixa que a de `rois` (leitura antiga, sem o registro: os padrões)."""
    feitas = leitura.get("rois") or _caixas(ROIS)
    return [n for n, c in _caixas(rois).items() if feitas.get(n) != c]


def ler(caminho: Path, tipo: str, intervalo: int = 2, workers: int = 4, lang: str = "por+eng",
        rois: dict | None = None) -> tuple[dict, float]:
    t0 = time.perf_counter()
    leitura = ler_imagem(caminho, lang, rois) if tipo == "imagem" else ler_clipe(caminho, intervalo, workers, lang, rois)
    leitura["rois"] = _caixas(rois or ROIS)   # com que regiões foi lida: se elas mudarem, só esses recortes são relidos
    return leitura, time.perf_counter() - t0
