"""Regiões da tela onde se lê o texto (legenda, objetivo da missão, avisos), sem anotação prévia.
Cada jogo começa com padrões genéricos (a maioria dos jogos põe a legenda na faixa de baixo, o objetivo num canto de cima e os
avisos no alto, à esquerda ou ao centro). Com uma IA local, o aplicativo refina essas regiões a partir do jogo: lê o texto de
algumas capturas com a posição de cada linha, pede à IA que diga o papel de cada linha (legenda, objetivo, aviso, menu ou ruído)
e define a região de cada papel pela posição das linhas. O resultado fica em `regioes.json`, na pasta do jogo, e pode ser editado
(uma região com "origem": "manual" nunca é refeita). O aplicativo não tem regras específicas de nenhum jogo: só estes recortes de OCR."""
import json
import logging
import random
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
LINHAS_CENA = (3, 18) # cena com texto por cima: ao menos 3 linhas lidas e no máximo 18 na tela inteira (menu, diário e mapa enchem)
MAX_AMOSTRAS = 8      # aprendizado incremental: no máximo isto de capturas na IA...
MINIMO_CONVERGIR = 3  # ...e pelo menos isto antes de dar por aprendido
CONVERGENCIA = 0.95   # duas estimativas seguidas com sobreposição (IoU) acima disto em toda região: ajuste pequeno
ESTAVEIS = 2          # estimativas seguidas sem ajuste expressivo para concluir
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
# resposta curta: só os números das linhas de cada papel que interessa (as outras são menu ou ruído); com uma entrada por
# linha, uma tela de 40 linhas custava centenas de tokens e ~15 s
PAPEIS_VISAO = ("legenda", "objetivo", "aviso")
ESQUEMA_VISAO = {"type": "object", "properties": {"tela": {"type": "string", "enum": ["cena", "menu"]},
                                                  **{p: {"type": "array", "items": {"type": "integer"}} for p in PAPEIS_VISAO}},
                 "required": ["tela", *PAPEIS_VISAO]}
# com um modelo de imagem: ele vê a captura com cada linha do OCR num retângulo numerado (as posições continuam no texto)
INSTRUCOES_VISAO = """Você vê a captura de tela de um jogo. Cada linha de texto lida por OCR está num retângulo amarelo com o número dela; a lista abaixo repete cada linha com o número, a posição (x e y em fração da tela, de 0 a 1, a partir do canto superior esquerdo) e o texto lido.
Primeiro diga o tipo da tela: "cena" se a captura mostra o jogo em andamento (exploração, diálogo, combate, cena), mesmo com textos por cima; "menu" se uma interface cobre a tela (menu, mapa, inventário, diário, glossário, ficha de item, tela de carregamento).
Depois, olhando a imagem (onde a linha está, o fundo, o estilo, se faz parte de um painel ou janela) e o texto, liste os números das linhas de cada papel:
- legenda: fala de personagem ou narração sobreposta à cena (costuma ficar na faixa de baixo, com ou sem o nome de quem fala);
- objetivo: título ou objetivo da missão ou tarefa, fixo na interface durante o jogo (HUD);
- aviso: notificação, tutorial, marcador novo, recompensa, mensagem passageira por cima da cena.
Não liste as demais (menu, botões, rótulos da interface, lixo do OCR). Numa tela de menu, as três listas ficam vazias. Responda só com o JSON pedido."""


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


def esquecer_aprendidas(pasta: Path) -> None:
    """Volta aos padrões genéricos tudo que foi aprendido; só uma região editada à mão ("origem": "manual") fica. Sem nenhuma
    região manual, o arquivo é apagado (a próxima rodada o recria com os padrões)."""
    try:
        d = json.loads(caminho(pasta).read_text(encoding="utf-8"))
        manuais = {n: i for n, i in d.get("regioes", {}).items() if isinstance(i, dict) and i.get("origem") == "manual"}
    except (OSError, ValueError, AttributeError):
        manuais = {}
    if manuais:
        caminho(pasta).write_text(json.dumps({"versao": 1, "regioes": manuais}, ensure_ascii=False, indent=1), encoding="utf-8")
    else:
        caminho(pasta).unlink(missing_ok=True)


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
    return "\n".join(f'{i}. x={l["x0"]:.2f}-{l["x1"]:.2f} y={l["y0"]:.2f} altura={l["altura"]:.3f} | {l["texto"][:120]}' for i, l in enumerate(linhas, 1))


def classificar(backend, linhas: list[dict], imagem: str = "") -> dict[int, str]:
    """Papel de cada linha, dado pela IA (com `imagem`, a captura marcada, por um modelo de imagem). Ids ou papéis que não
    existem são ignorados."""
    if imagem:
        resp = backend.perguntar(INSTRUCOES_VISAO, _pedido(linhas), ESQUEMA_VISAO, [imagem])
        if resp.get("tela") == "menu":   # numa tela de menu, frase longa é texto do menu, não legenda nem aviso
            return {i: "menu" for i in range(len(linhas))}
        if resp.get("tela") != "cena":   # resposta fora do esquema: a amostra não conta
            return {}
        papeis = {i: "menu" for i in range(len(linhas))}   # o que não foi listado é menu ou ruído
        for papel in PAPEIS_VISAO:
            for n in resp.get(papel) or []:   # números a partir de 1 (no texto e na imagem)
                if isinstance(n, int) and 1 <= n <= len(linhas):
                    papeis[n - 1] = papel
        return papeis
    else:
        resp = backend.perguntar(INSTRUCOES, _pedido(linhas), ESQUEMA)
    papeis = {}
    for item in resp.get("linhas", []):   # as linhas vão numeradas a partir de 1 (no texto e na imagem)
        if isinstance(item, dict) and isinstance(item.get("id"), int) and 1 <= item["id"] <= len(linhas) and item.get("papel") in PAPEIS:
            papeis[item["id"] - 1] = item["papel"]
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
        vista = (max(0.0, x0 - MARGEM), max(0.0, y0 - MARGEM), min(1.0, x1 + MARGEM), min(1.0, y1 + MARGEM))
        # a região nunca encolhe o padrão, só cresce para incluir onde o texto foi visto: poucas amostras com a legenda no centro
        # não podem cortar a legenda longa de outra tela (um recorte um pouco maior custa pouco; um menor perde texto)
        p = PADRAO[regiao]
        caixa = (min(vista[0], p[0]), min(vista[1], p[1]), max(vista[2], p[2]), max(vista[3], p[3]))
        if caixa == p:
            continue   # tudo o que foi visto já cabe no padrão: nada a aprender
        area = (caixa[2] - caixa[0]) * (caixa[3] - caixa[1])
        if caixa[2] - caixa[0] < 0.10 or caixa[3] - caixa[1] < 0.03 or area > 0.70 or _iou(caixa, PADRAO[regiao]) < SOBREPOSICAO_MINIMA:
            log.info("região %s descartada (caixa %s fora do razoável)", regiao, tuple(round(v, 2) for v in caixa))
            continue
        novas[regiao] = {"caixa": caixa, "linhas": len(ls), "amostras": len(amostras)}
    return novas


def estimar(atual: Regioes, por_amostra: list[list[tuple[dict, str]]]) -> Regioes:
    """As regiões que as amostras rotuladas até aqui indicam, a partir de `atual` (regiões manuais não são tocadas)."""
    r = Regioes(dict(atual.caixas), json.loads(json.dumps(atual.meta)))
    info = r.meta.setdefault("regioes", {})
    for nome, n in caixa_dos_papeis(por_amostra).items():
        if info.get(nome, {}).get("origem") == "manual":
            continue
        r.caixas[nome] = n["caixa"]
        info[nome] = {"origem": "ia", "linhas": n["linhas"], "amostras": n["amostras"], "padrao": [round(v, 3) for v in PADRAO[nome]]}
    return r


class Aprendiz:
    """Aprende as regiões uma captura por vez, durante a leitura: cada captura que parece cena (pelo OCR já feito) passa pela IA
    logo em seguida, e as regiões são reestimadas com tudo o que foi visto. Para quando duas estimativas seguidas não fazem
    ajuste expressivo (CONVERGENCIA), com pelo menos MINIMO_CONVERGIR amostras; ou em MAX_AMOSTRAS; ou no prazo.
    `marcar(quadro, linhas)`: a captura marcada para um modelo de imagem (None: só o texto vai para a IA)."""

    def __init__(self, backend, atual: Regioes, lang: str = "por+eng", marcar=None, prazo_s: float = 0):
        self.backend, self.atual, self.lang, self.marcar, self.prazo_s = backend, atual, lang, marcar, prazo_s
        self.estimativa = atual
        self.por_amostra: list[list[tuple[dict, str]]] = []
        self.nomes: list[str] = []
        self.vistas: set[int] = set()
        self.estaveis = 0
        self.tempo = 0.0

    @property
    def terminou(self) -> bool:
        return (self.estaveis >= ESTAVEIS or len(self.nomes) >= MAX_AMOSTRAS
                or bool(self.prazo_s and self.tempo > self.prazo_s))

    @property
    def convergiu(self) -> bool:
        return self.estaveis >= ESTAVEIS

    def considerar(self, midia, leitura: dict) -> bool:
        """Se a captura parece cena e o aprendizado não terminou, passa ela pela IA e reestima. Devolve True se a usou."""
        if self.terminou or midia.id in self.vistas or not parece_cena(leitura):
            return False
        self.vistas.add(midia.id)
        t0 = time.monotonic()
        try:
            quadro = quadro_da_midia(Path(midia.caminho), midia.tipo)
            linhas = linhas_com_posicao(quadro, self.lang) if quadro is not None else []
            if len(linhas) < 3:
                return False
            papeis = classificar(self.backend, linhas, self.marcar(quadro, linhas) if self.marcar else "")
        except (OSError, ValueError) as e:
            log.warning("regiões: %s sem resposta da IA (%s)", midia.nome, e)
            return False
        finally:
            self.tempo += time.monotonic() - t0
        self.por_amostra.append([(l, papeis[i]) for i, l in enumerate(linhas) if i in papeis])
        self.nomes.append(midia.nome)
        nova = estimar(self.atual, self.por_amostra)
        # só conta como estável depois de amostras suficientes: com 1 ou 2, nada é aprendido e a estimativa não muda
        sem_ajuste = len(self.nomes) >= MINIMO_CONVERGIR and not mudou(self.estimativa, nova, CONVERGENCIA)
        self.estaveis = self.estaveis + 1 if sem_ajuste else 0
        self.estimativa = nova
        estado = ("juntando amostras" if len(self.nomes) < MINIMO_CONVERGIR else
                  "sem ajuste expressivo" if sem_ajuste else "estimativa ajustada")
        log.info("regiões: amostra %d (%s), %s", len(self.nomes), midia.nome, estado)
        return True

    def resultado(self) -> Regioes | None:
        """As regiões aprendidas, com o registro do aprendizado; None se ainda não houve amostras suficientes (tenta numa
        próxima rodada)."""
        if len(self.nomes) < MINIMO_CONVERGIR:
            return None
        r = Regioes(dict(self.estimativa.caixas), json.loads(json.dumps(self.estimativa.meta)))
        r.meta.update({"aprendido_em": time.strftime("%Y-%m-%d %H:%M"), "modelo": getattr(self.backend, "nome", ""),
                       "com_imagem": bool(self.marcar), "capturas_lidas": len(self.nomes), "capturas": list(self.nomes),
                       "convergiu": self.convergiu, "tempo_s": round(self.tempo, 1)})
        return r


def linhas_de_texto(leitura: dict, secoes: tuple = ("tela",)) -> int:
    """Linhas de texto de verdade (não lixo do OCR) que a leitura achou nas `secoes`; num clipe, no quadro do meio."""
    qs = leitura.get("quadros") or []
    if not qs:
        return 0
    n = 0
    for sec in secoes:
        for l in qs[len(qs) // 2]["secoes"].get(sec, "").splitlines():
            letras = sum(c.isalpha() for c in l)
            n += letras >= 4 and letras / max(len(l.strip()), 1) >= 0.6
    return n


def parece_cena(leitura: dict) -> bool:
    """Cena com texto por cima, pelo que o OCR leu: pouco texto na tela inteira (menu, mapa e diário a enchem) e algum texto
    lido, contando os recortes, porque o OCR da tela inteira quase não acha uma legenda sobre a cena e o do recorte acha."""
    tela = linhas_de_texto(leitura)
    return tela <= LINHAS_CENA[1] and tela + linhas_de_texto(leitura, ("legenda", "hud", "aviso")) >= LINHAS_CENA[0]


def mudou(antes: Regioes, depois: Regioes, limiar: float = 0.9) -> list[str]:
    """Regiões cuja caixa mudou de verdade (interseção sobre união abaixo de `limiar`)."""
    return [n for n in depois.caixas if _iou(antes.caixas.get(n, PADRAO[n]), depois.caixas[n]) < limiar]


def ordem_sorteada(itens: list, semente: str = "") -> list:
    """Os itens em ordem sorteada, com a `semente` (o nome do jogo): refazer dá a mesma ordem, e jogos diferentes, ordens
    diferentes. Serve para as amostras do aprendizado não virem todas do mesmo trecho do jogo (uma abertura com cutscene)."""
    itens = list(itens)
    random.Random(semente).shuffle(itens)
    return itens


__all__ = ["PADRAO", "Regioes", "Aprendiz", "carregar", "salvar", "estimar", "mudou", "parece_cena", "ordem_sorteada", "linhas_com_posicao", "quadro_da_midia"]
