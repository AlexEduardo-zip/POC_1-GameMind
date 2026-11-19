"""Modelo de imagem (visão) do Ollama local, usado quando está instalado para aprender as regiões de leitura de cada jogo.
Só o Ollama local recebe imagens: as capturas nunca saem do computador, qualquer que seja a IA escolhida para as relações.
Qualquer modelo instalado que o Ollama declare com a capacidade "vision" serve; entre vários, vale a ordem de PREFERIDOS
(os que leem melhor texto e layout de tela) e, na mesma família, o maior (rotula melhor; o tempo é limitado pelo prazo de
aprendizado das regiões). Nada aqui depende de um jogo."""
import base64
import json
import logging
import urllib.request

import cv2
import numpy as np

log = logging.getLogger("gamemind")
OLLAMA = "http://localhost:11434"
PREFERIDOS = ("qwen2.5vl", "qwen3-vl", "gemma3", "minicpm-v", "llama3.2-vision", "llava")
LARGURA = 1024          # a captura vai reduzida: com 1024 px o texto da interface ainda é legível e a chamada fica rápida


def _json(caminho: str, corpo: dict | None = None, timeout: float = 3.0) -> dict:
    req = urllib.request.Request(OLLAMA + caminho, data=json.dumps(corpo).encode() if corpo is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def modelos_de_visao() -> list[str]:
    """Modelos instalados no Ollama com a capacidade "vision", do preferido para o menos preferido. Sem Ollama: lista vazia."""
    try:
        instalados = _json("/api/tags").get("models", [])
    except (OSError, ValueError):
        return []
    achados = []
    for m in instalados:
        try:
            caps = _json("/api/show", {"model": m["name"]}).get("capabilities", [])
        except (OSError, ValueError):
            continue
        if "vision" in caps:
            familia = next((i for i, p in enumerate(PREFERIDOS) if m["name"].startswith(p)), len(PREFERIDOS))
            achados.append((familia, -m.get("size", 0), m["name"]))
    return [n for _, _, n in sorted(achados)]


def escolher(config_modelo: str = "") -> str:
    """O modelo de imagem a usar: o configurado (se instalado e com visão), senão o preferido entre os instalados; "" se nenhum.
    `config_modelo` "nenhum" desliga."""
    if config_modelo.strip().lower() in ("nenhum", "nenhuma", "desligado"):
        return ""
    disponiveis = modelos_de_visao()
    if config_modelo and config_modelo in disponiveis:
        return config_modelo
    if config_modelo:
        log.info("modelo de imagem %s não está instalado com visão no Ollama; usando %s", config_modelo, disponiveis[0] if disponiveis else "nenhum")
    return disponiveis[0] if disponiveis else ""


def imagem_marcada(img: np.ndarray, linhas: list[dict], largura: int = LARGURA) -> str:
    """A captura reduzida a `largura`, com cada linha lida pelo OCR num retângulo com o número dela (para o modelo apontar a
    linha pelo número), em JPEG base64."""
    h, w = img.shape[:2]
    escala = min(1.0, largura / w)
    peq = cv2.resize(img, (int(w * escala), int(h * escala)), interpolation=cv2.INTER_AREA) if escala < 1 else img.copy()
    ph, pw = peq.shape[:2]
    for i, l in enumerate(linhas, 1):   # numeradas a partir de 1, como no texto do pedido
        x0, y0, x1, y1 = int(l["x0"] * pw), int(l["y0"] * ph), int(l["x1"] * pw), int(l["y1"] * ph)
        cv2.rectangle(peq, (x0, y0), (x1, y1), (0, 255, 255), 1)
        rotulo = str(i)
        (tw, th), _ = cv2.getTextSize(rotulo, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
        ty = max(th + 2, y0 - 2)
        cv2.rectangle(peq, (x0, ty - th - 2), (x0 + tw + 4, ty + 2), (0, 0, 0), -1)
        cv2.putText(peq, rotulo, (x0 + 2, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1, cv2.LINE_AA)
    ok, buf = cv2.imencode(".jpg", peq, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.b64encode(buf.tobytes()).decode() if ok else ""


__all__ = ["OLLAMA", "PREFERIDOS", "modelos_de_visao", "escolher", "imagem_marcada"]
