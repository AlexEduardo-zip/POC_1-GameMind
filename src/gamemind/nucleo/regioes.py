"""Regiões da tela onde se lê o texto (legenda, objetivo da missão, avisos), sem anotação prévia.
Cada jogo começa com padrões genéricos (a maioria dos jogos põe a legenda na faixa de baixo, o objetivo num canto de cima e os
avisos no alto, à esquerda ou ao centro). Com uma IA local, o aplicativo refina essas regiões a partir do jogo: lê o texto de
algumas capturas com a posição de cada linha, pede à IA que diga o papel de cada linha (legenda, objetivo, aviso, menu ou ruído)
e define a região de cada papel pela posição das linhas. O resultado fica em `regioes.json`, na pasta do jogo, e pode ser editado
(uma região com "origem": "manual" nunca é refeita). O aplicativo não tem regras específicas de nenhum jogo: só estes recortes de OCR."""
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
import pytesseract
from extracao.preprocessamento import ROIS

log = logging.getLogger("gamemind")

# (x0, y0, x1, y1) em fração da tela. Genéricos de propósito: largos, para pegar a maioria dos jogos
PADRAO = dict(ROIS)
PAPEL_REGIAO = {"legenda": "legenda", "objetivo": "hud", "aviso": "aviso"}   # papel que a IA dá -> região
PAPEIS = ["legenda", "objetivo", "aviso", "menu", "ruido"]
AMOSTRAS = 8          # capturas lidas para aprender (uma chamada à IA por captura)
MINIMO_MIDIAS = 6     # só tenta aprender quando o jogo já tem pelo menos isto
MINIMO_LINHAS = 3     # linhas de um papel para definir a região
MINIMO_AMOSTRAS = 2   # em quantas capturas o papel precisa aparecer
MARGEM = 0.03
VIZINHANCA = 0.12     # a IA só refina o que está perto do padrão: linhas além desta folga em volta dele são ignoradas
SOBREPOSICAO_MINIMA = 0.25   # a região aprendida precisa se parecer com o padrão (interseção sobre união); senão fica o padrão

ESQUEMA = {"type": "object", "properties": {"linhas": {"type": "array", "items": {
    "type": "object", "properties": {"id": {"type": "integer"}, "papel": {"type": "string", "enum": PAPEIS}},
    "required": ["id", "papel"]}}}, "required": ["linhas"]}
INSTRUCOES = """Você recebe linhas de texto lidas por OCR de uma captura de tela de um jogo. Cada linha tem um id, a posição (x e y em fração da tela, de 0 a 1, a partir do canto superior esquerdo) e a altura da letra.
Diga o papel de cada linha:
- legenda: fala de personagem ou narração (costuma ficar na faixa de baixo, com ou sem o nome de quem fala);
- objetivo: título ou objetivo da missão ou tarefa, fixo na interface do jogo;
- aviso: notificação, tutorial, marcador novo, recompensa, mensagem passageira;
- menu: lista, inventário, mapa, glossário, botões e rótulos da interface;
- ruido: texto sem sentido, lixo do OCR.
Responda só com o JSON pedido, com todas as linhas."""


@dataclass
class Regioes:
    caixas: dict[str, tuple] = field(default_factory=lambda: dict(PADRAO))
    meta: dict = field(default_factory=dict)   # origem e estatística de cada região, quando e com que modelo foi aprendida

    @property
    def origem(self) -> dict[str, str]:
        return {n: self.meta.get("regioes", {}).get(n, {}).get("origem", "padrao") for n in self.caixas}

    @property
    def aprendida(self) -> bool:
        return bool(self.meta.get("aprendido_em"))


def caminho(pasta: Path) -> Path:
    return Path(pasta) / "regioes.json"


def carregar(pasta: Path) -> Regioes:
    """Lê `regioes.json` do jogo; sem arquivo ou com defeito, usa os padrões genéricos (e grava o arquivo)."""
    try:
        d = json.loads(caminho(pasta).read_text(encoding="utf-8"))
        caixas = dict(PADRAO)
        for nome, info in d.get("regioes", {}).items():
            c = tuple(float(v) for v in info["caixa"])
            if nome in PADRAO and len(c) == 4 and 0 <= c[0] < c[2] <= 1 and 0 <= c[1] < c[3] <= 1:
                caixas[nome] = c
        r = Regioes(caixas, {k: v for k, v in d.items() if k != "regioes"} | {"regioes": d.get("regioes", {})})
    except (OSError, ValueError, KeyError, TypeError):
        r = Regioes()
        salvar(pasta, r)
    return r


def salvar(pasta: Path, r: Regioes) -> None:
    d = {**{k: v for k, v in r.meta.items() if k != "regioes"}, "versao": 1,
         "regioes": {n: {**r.meta.get("regioes", {}).get(n, {"origem": "padrao"}), "caixa": [round(v, 3) for v in c]} for n, c in r.caixas.items()}}
    caminho(pasta).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------------------------------------------------------------- ler a captura com posição
def linhas_com_posicao(img: np.ndarray, lang: str = "por+eng", maximo: int = 45) -> list[dict]:
    """Linhas da captura com a caixa (frações da tela) e a altura relativa da letra."""
    h, w = img.shape[:2]
    d = pytesseract.image_to_data(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), lang=lang, config="--psm 11", output_type=pytesseract.Output.DICT)
    por_linha: dict[tuple, list[int]] = {}
    for i, t in enumerate(d["text"]):
        if t.strip() and float(d["conf"][i]) >= 20:
            por_linha.setdefault((d["block_num"][i], d["par_num"][i], d["line_num"][i]), []).append(i)
    saida = []
    for idx in por_linha.values():
        texto = " ".join(d["text"][i] for i in idx).strip()
        letras = sum(c.isalpha() for c in texto)
        if letras < 4 or letras / max(len(texto), 1) < 0.6:
            continue
        x0, y0 = min(d["left"][i] for i in idx), min(d["top"][i] for i in idx)
        x1, y1 = max(d["left"][i] + d["width"][i] for i in idx), max(d["top"][i] + d["height"][i] for i in idx)
        saida.append({"texto": texto, "x0": x0 / w, "y0": y0 / h, "x1": x1 / w, "y1": y1 / h, "altura": (y1 - y0) / h})
    saida.sort(key=lambda l: (round(l["y0"], 2), l["x0"]))
    # com muitas linhas, fica com as maiores em texto: são as que têm mais chance de ser frase de verdade
    if len(saida) > maximo:
        saida = sorted(sorted(saida, key=lambda l: -len(l["texto"]))[:maximo], key=lambda l: (round(l["y0"], 2), l["x0"]))
    return saida


def quadro_da_midia(caminho_midia: Path, tipo: str) -> np.ndarray | None:
    """A captura, ou o quadro do meio do clipe."""
    try:
        if tipo == "imagem":
            return cv2.imdecode(np.fromfile(str(caminho_midia), dtype=np.uint8), cv2.IMREAD_COLOR)
        cap = cv2.VideoCapture(str(caminho_midia))
        try:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(cap.get(cv2.CAP_PROP_FRAME_COUNT) // 2))
            ok, quadro = cap.read()
        finally:
            cap.release()
        return quadro if ok else None
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------- aprender com a IA
def _pedido(linhas: list[dict]) -> str:
    return "\n".join(f'{i}. x={l["x0"]:.2f}-{l["x1"]:.2f} y={l["y0"]:.2f} altura={l["altura"]:.3f} | {l["texto"][:120]}' for i, l in enumerate(linhas))


def classificar(backend, linhas: list[dict]) -> dict[int, str]:
    """Papel de cada linha, dado pela IA. Ids ou papéis que não existem são ignorados."""
    resp = backend.perguntar(INSTRUCOES, _pedido(linhas), ESQUEMA)
    papeis = {}
    for item in resp.get("linhas", []):
        if isinstance(item, dict) and isinstance(item.get("id"), int) and 0 <= item["id"] < len(linhas) and item.get("papel") in PAPEIS:
            papeis[item["id"]] = item["papel"]
    return papeis


def _percentil(valores: list[float], p: float) -> float:
    v = sorted(valores)
    return v[min(len(v) - 1, max(0, round(p * (len(v) - 1))))]


def _maior_grupo(itens: list[tuple[int, dict]], chave: str, folga: float) -> list[tuple[int, dict]]:
    """Mantém só o maior grupo de linhas que ficam juntas no eixo `chave` (um corte onde há `folga` de vazio entre duas linhas).
    A IA erra o papel de algumas linhas; elas costumam estar longe das demais e não devem esticar a região."""
    ordenadas = sorted(itens, key=lambda it: it[1][chave])
    grupos, atual = [], [ordenadas[0]]
    for it in ordenadas[1:]:
        if it[1][chave] - atual[-1][1][chave] > folga:
            grupos.append(atual)
            atual = []
        atual.append(it)
    grupos.append(atual)
    return max(grupos, key=len)


def _iou(a: tuple, b: tuple) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    uniao = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / uniao if uniao else 0.0


def _perto(l: dict, padrao: tuple) -> bool:
    return (l["x0"] >= padrao[0] - VIZINHANCA and l["x1"] <= padrao[2] + VIZINHANCA
            and l["y0"] >= padrao[1] - VIZINHANCA and l["y1"] <= padrao[3] + VIZINHANCA)


def caixa_dos_papeis(por_amostra: list[list[tuple[dict, str]]]) -> dict[str, dict]:
    """Região de cada papel a partir das linhas que a IA rotulou nele, em todas as amostras. Descarta o que parece defeito."""
    novas = {}
    for papel, regiao in PAPEL_REGIAO.items():
        # uma IA pequena rotula como legenda qualquer frase (o texto de um diário, por exemplo): só valem as linhas perto do padrão
        linhas = [(i, l) for i, am in enumerate(por_amostra) for l, p in am if p == papel and _perto(l, PADRAO[regiao])]
        amostras = {i for i, _ in linhas}
        if len(linhas) < MINIMO_LINHAS or len(amostras) < MINIMO_AMOSTRAS:
            continue
        linhas = _maior_grupo(_maior_grupo(linhas, "y0", 0.10), "x0", 0.20)   # só o maior grupo de linhas juntas
        amostras = {i for i, _ in linhas}
        if len(linhas) < MINIMO_LINHAS or len(amostras) < MINIMO_AMOSTRAS:
            continue
        ls = [l for _, l in linhas]
        # percentis 10 e 90: uma linha fora do lugar (rótulo errado da IA ou lixo do OCR) não estica a região
        x0, y0 = _percentil([l["x0"] for l in ls], 0.10), _percentil([l["y0"] for l in ls], 0.10)
        x1, y1 = _percentil([l["x1"] for l in ls], 0.90), _percentil([l["y1"] for l in ls], 0.90)
        caixa = (max(0.0, x0 - MARGEM), max(0.0, y0 - MARGEM), min(1.0, x1 + MARGEM), min(1.0, y1 + MARGEM))
        area = (caixa[2] - caixa[0]) * (caixa[3] - caixa[1])
        if caixa[2] - caixa[0] < 0.10 or caixa[3] - caixa[1] < 0.03 or area > 0.70 or _iou(caixa, PADRAO[regiao]) < SOBREPOSICAO_MINIMA:
            log.info("região %s descartada (caixa %s fora do razoável)", regiao, tuple(round(v, 2) for v in caixa))
            continue
        novas[regiao] = {"caixa": caixa, "linhas": len(ls), "amostras": len(amostras)}
    return novas


def aprender(amostras: list[list[dict]], backend, atual: Regioes, nomes: list[str] | None = None) -> Regioes:
    """Refina as regiões com a IA. `amostras`: as linhas (com posição) de cada captura. Regiões manuais não são tocadas."""
    por_amostra, usadas = [], 0
    for linhas in amostras:
        if len(linhas) < 3:
            continue
        papeis = classificar(backend, linhas)
        por_amostra.append([(l, papeis[i]) for i, l in enumerate(linhas) if i in papeis])
        usadas += 1
    novas = caixa_dos_papeis(por_amostra)
    r = Regioes(dict(atual.caixas), json.loads(json.dumps(atual.meta)))
    info = r.meta.setdefault("regioes", {})
    for nome, n in novas.items():
        if info.get(nome, {}).get("origem") == "manual":
            continue
        r.caixas[nome] = n["caixa"]
        info[nome] = {"origem": "ia", "linhas": n["linhas"], "amostras": n["amostras"], "padrao": [round(v, 3) for v in PADRAO[nome]]}
    r.meta.update({"aprendido_em": time.strftime("%Y-%m-%d %H:%M"), "modelo": getattr(backend, "nome", ""),
                   "capturas_lidas": usadas, "capturas": nomes or []})
    return r


def escolher_amostras(midias: list, n: int = AMOSTRAS) -> list:
    """`n` mídias espalhadas ao longo da lista (que já está na ordem do jogo), preferindo imagens."""
    imagens = [m for m in midias if m.tipo == "imagem"]
    base = imagens if len(imagens) >= n else midias
    if len(base) <= n:
        return list(base)
    return [base[round(i * (len(base) - 1) / (n - 1))] for i in range(n)]


__all__ = ["PADRAO", "Regioes", "carregar", "salvar", "aprender", "escolher_amostras", "linhas_com_posicao", "quadro_da_midia"]
