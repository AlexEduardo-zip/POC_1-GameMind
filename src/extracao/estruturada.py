"""Extração estruturada por tipo de tela (etapa B3a).
Lê regiões fixas da interface do jogo e converte a estrutura em entidades que dicionário nenhum alcança:
missões (título do HUD, banner de missão, lista do diário, painel do mapa e contratos de quadro de avisos)
e decisões (opção de diálogo marcada). Nada aqui consulta o gabarito.

Fluxo: `candidatos()` por imagem -> `consolidar()` no lote, que junta variações de leitura do mesmo nome
(ex.: "KAERIMORHEN" e "KAER MORHEN") e escolhe a grafia mais frequente."""
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

import numpy as np
import pytesseract

from .gazetteer import norm
from .preprocessamento import preparar, recortar

# Regiões (x0, y0, x1, y1) calibradas em 1920x1080; filtro e modo de página do Tesseract por região
REGIOES = {
    "hud": ((0.72, 0.26, 1.00, 0.50), "brilho", 6),
    "banner": ((0.00, 0.18, 0.50, 0.66), "brilho", 6),
    "diario": ((0.065, 0.14, 0.32, 0.62), "cinza", 6),
    "mapa": ((0.72, 0.09, 1.00, 0.22), "cinza", 6),
    "quadro": ((0.54, 0.14, 0.96, 0.25), "cinza", 6),
    "opcoes": ((0.58, 0.66, 0.92, 0.77), "cinza", 6),
}
ESCALA = 2.5
CONECTORES = {"E", "O", "A", "DE", "DA", "DO", "DAS", "DOS", "AS", "OS", "EM", "NA", "NO", "COM"}
PEQUENAS = {c.lower() for c in CONECTORES}
RUIDO_HUD = {"por perto", "perto", "limpo", "chovendo", "nublado"}
CABECALHOS_DIARIO = {"missoes principais", "missoes secundarias", "missoes", "completa", "principais", "secundarias", "caca ao tesouro", "contratos"}


@dataclass
class Cand:
    nome: str
    tipo: str
    fonte: str          # hud, banner, diario, mapa, quadro, opcoes
    estado: str = ""
    subtipo: str = ""
    evidencia: str = ""


def linhas(img: np.ndarray, regiao: str) -> list[dict]:
    """Linhas lidas na região, com posição (x, y) em coordenadas do recorte original."""
    roi, filtro, psm = REGIOES[regiao]
    d = pytesseract.image_to_data(preparar(recortar(img, roi), filtro, ESCALA), lang="por+eng",
                                  config=f"--psm {psm}", output_type=pytesseract.Output.DICT)
    por_linha: dict[tuple, list[int]] = {}
    for i, t in enumerate(d["text"]):
        if t.strip() and float(d["conf"][i]) >= 0:
            por_linha.setdefault((d["block_num"][i], d["par_num"][i], d["line_num"][i]), []).append(i)
    saida = []
    for idx in por_linha.values():
        saida.append({"texto": " ".join(d["text"][i] for i in idx),
                      "x": min(d["left"][i] for i in idx) / ESCALA, "y": min(d["top"][i] for i in idx) / ESCALA})
    return sorted(saida, key=lambda l: l["y"])


def _tokens(linha: str, minimo: int = 3) -> list[str]:
    """Palavras da linha sem o ruído que a cena e os ícones deixam nas pontas."""
    toks = [re.sub(r"[^A-Za-zÀ-ÿ'\-]", "", t) for t in linha.split()]
    # ruído à esquerda: sequência de fragmentos curtos (ícone, borda); só um "o"/"a" isolado abre um título
    i = 0
    while i < len(toks) and len(toks[i]) < minimo and not (toks[i].upper() in {"O", "A"} and i == 0 and len(toks) > 1 and len(toks[1]) >= minimo):
        i += 1
    toks = toks[i:]
    # ruído à direita: fragmento curto que não é conector
    while toks and len(toks[-1]) <= 3 and toks[-1].upper() not in CONECTORES:
        toks.pop()
    return [t for t in toks if len(t) >= minimo or t.upper() in CONECTORES]


def titulo_maiusculo(linha: str) -> list[str] | None:
    """Linha de título do jogo: texto todo em maiúsculas, sem ruído de cena."""
    toks = _tokens(linha)
    letras = [c for t in toks for c in t if c.isalpha()]
    if len(letras) < 6 or norm(linha) in RUIDO_HUD or any(r in norm(linha) for r in ("limpo", "perto")):
        return None
    if sum(c.isupper() for c in letras) / len(letras) < 0.85:
        return None
    while toks and toks[0].upper() in CONECTORES and toks[0].islower():
        toks = toks[1:]
    palavras = [t for t in toks if t.upper() not in CONECTORES]
    if not palavras or (len(toks) == 1 and len(toks[0]) < 5):
        return None
    while toks and toks[0].upper() in CONECTORES - {"O", "A", "UMA"} and len(toks) > 2:
        toks = toks[1:]  # conector solto no começo costuma ser ruído; "O" e "A" abrem títulos de verdade
    return toks


def sem_ruido_inicial(toks: list[str]) -> list[str]:
    """Tira um fragmento curto antes de um artigo ("Pos O monstro de ...") que o OCR leu de ícone ou borda."""
    if len(toks) > 3 and len(toks[0]) <= 4 and toks[1].lower() in {"o", "a"} and toks[0].lower() not in PEQUENAS:
        return toks[1:]
    return toks


def caso_titulo(toks: list[str]) -> str:
    out = []
    for i, t in enumerate(toks):
        t = t.lower()
        out.append(t.capitalize() if i == 0 or t not in PEQUENAS else t)
    return " ".join(out)


def _lugar(nome: str, gaz) -> bool:
    """O nome é o de um local do dicionário, com no máximo uma palavra de ruído antes ("Ven Pomar Branco")."""
    k = norm(nome)
    for c in gaz.tipo:
        if gaz.tipo[c] != "local":
            continue
        p = norm(c)
        if SequenceMatcher(None, k, p).ratio() >= 0.9:
            return True
        resto = k[: max(len(k) - len(p), 0)].split()
        if len(resto) <= 1 and SequenceMatcher(None, k[len(k) - len(p):], p).ratio() >= 0.9 and k != p:
            return True
    return False


def _cabecalho(k: str) -> bool:
    return any(SequenceMatcher(None, k, h).ratio() >= 0.75 for h in CABECALHOS_DIARIO)


def _plausivel(texto: str) -> bool:
    """Frase de verdade e não ruído de cena: palavras com vogal, grafia regular e pontuação final."""
    toks = [re.sub(r"[^A-Za-zÀ-ÿ]", "", t) for t in texto.split()]
    toks = [t for t in toks if t]
    boas = [t for t in toks if re.search(r"[aeiouáéíóúâêôãõ]", t, re.I) and (t.islower() or t.istitle() or t.isupper()) and len(t) <= 14]
    return len(toks) >= 2 and len(boas) / len(toks) >= 0.8 and bool(re.search(r"[.?!…]\s*$", texto.strip()))


def candidatos(img: np.ndarray, texto: str, gaz) -> list[Cand]:
    """Candidatos de missão e decisão de uma imagem. `texto` é o OCR completo (decide o tipo de tela)."""
    n = norm(texto)
    # barra superior dos menus (glossário, alquimia, inventário, mapa, missões, personagem, meditação)
    barra = sum(p in n for p in ("glossario", "alquimia", "inventario", "personagem", "meditacao", "missoes"))
    menu = barra >= 3 or (barra >= 1 and "voltar" in n)
    out: list[Cand] = []

    # 1) título da missão no HUD (fora dos menus): primeira linha em maiúsculas
    if not menu:
        for l in linhas(img, "hud"):
            t = titulo_maiusculo(l["texto"])
            if t:
                out.append(Cand(caso_titulo(t), "missao", "hud", "ativa", "", f"HUD: '{l['texto']}'"))
                break

    # 2) banner "MISSÃO COMPLETADA!" / "MISSÃO ATUALIZADA!" / "NOVA MISSÃO" seguido do título
    if not menu and "missao" in n:
        ls = linhas(img, "banner")
        for i, l in enumerate(ls):
            m = re.search(r"miss[aã]o\s+(completada|atualizada)|nova\s+miss[aã]o", norm(l["texto"]))
            if m:
                prox = next((titulo_maiusculo(x["texto"]) for x in ls[i + 1:i + 3] if titulo_maiusculo(x["texto"])), None)
                if prox:
                    est = "concluida" if "completada" in m.group() else "ativa"
                    out.append(Cand(caso_titulo(prox), "missao", "banner", est, "", f"banner: '{l['texto']}'"))
                break

    # 3) diário: lista de missões à esquerda (título seguido da região, que é legenda e não missão)
    if "missoes principais" in n:
        anterior = ""
        for l in linhas(img, "diario"):
            t = " ".join(_tokens(l["texto"]))
            k = norm(t)
            if len(re.sub(r"[^a-z]", "", k)) < 6 or _cabecalho(k) or k == anterior:
                continue
            if _lugar(t, gaz) and anterior:
                continue  # legenda com o nome da região sob o título
            anterior = k
            out.append(Cand(caso_titulo(sem_ruido_inicial(t.split())), "missao", "diario", "ativa", "principal", f"diário: '{l['texto']}'"))

    # 4) painel da missão rastreada no mapa: o título vem logo depois da linha "Mudar missão rastreada"
    ls = linhas(img, "mapa")
    for i, l in enumerate(ls):
        if "rastread" in norm(l["texto"]):
            for x in ls[i + 1:i + 3]:
                t = " ".join(_tokens(x["texto"]))
                if len(re.sub(r"[^a-z]", "", norm(t))) >= 8 and "mudar" not in norm(t):
                    out.append(Cand(caso_titulo(sem_ruido_inicial(t.split())), "missao", "mapa", "ativa", "", f"mapa: '{x['texto']}'"))
                    break
            break

    # 5) quadro de avisos: "Procurado: X" e "Contrato: X" são contratos ainda não aceitos
    if True:
        for l in linhas(img, "quadro"):
            m = re.search(r"(?<![a-z])(procurado|contrato)\s*:\s*(.+)", l["texto"], re.I)
            if m:
                nome = f"{m.group(1).capitalize()}: {m.group(2).strip(' .-–—_|')}"
                out.append(Cand(nome, "missao", "quadro", "disponivel", "contrato", f"quadro: '{l['texto']}'"))
                break

    # 6) decisão: primeira opção de diálogo (onde o cursor começa), só em tela de jogo (sem menu, "Voltar" ou quadro)
    if not menu and "voltar" not in n:
        ls = [l for l in linhas(img, "opcoes") if len(re.sub(r"[^A-Za-zÀ-ÿ]", "", l["texto"])) >= 10]
        if len(ls) >= 2 and all(_plausivel(re.sub(r"^[^A-Za-zÀ-ÿ0-9]*", "", l["texto"])) for l in ls[:2]):
            nome = re.sub(r"^\W*(?:[A-Za-z]{1,2}\W+\d\s*[.)]?\s*|\d\s*[.)]?\s*)?[^A-Za-zÀ-ÿ]*", "", ls[0]["texto"]).strip(" .…?!")
            nome = gaz.corrigir(nome)
            out.append(Cand(nome[0].upper() + nome[1:], "decisao", "opcoes", "", "opção de diálogo", f"opções: '{ls[0]['texto']}'"))
    return out


def _chave(nome: str) -> str:
    return re.sub(r"[^a-z]", "", norm(nome))


def consolidar(por_item: dict[str, list[Cand]], gaz, limiar: float = 0.8) -> dict[str, list[Cand]]:
    """Junta no lote as variações de leitura do mesmo nome e aplica o sufixo "(missão)" quando o título
    coincide com o nome de um local (ontologia: nomes iguais de tipos diferentes se desambiguam)."""
    todos = [(item, c) for item, cs in por_item.items() for c in cs]
    grupos: list[list[tuple[str, Cand]]] = []
    for item, c in todos:
        if c.tipo != "missao" or c.fonte == "quadro":
            continue
        k = _chave(c.nome)
        for g in grupos:
            r = SequenceMatcher(None, k, _chave(g[0][1].nome)).ratio()
            if len(k) >= 8 and r >= limiar:
                g.append((item, c))
                break
        else:
            grupos.append([(item, c)])
    # texto de tutorial e de cena também sai em maiúsculas; missão de verdade fica à vista em várias telas
    grupos = [g for g in grupos if any(c.fonte != "hud" for _, c in g) or len({item for item, _ in g}) >= 2]
    canon: dict[int, str] = {}
    for g in grupos:
        freq: dict[str, int] = {}
        for _, c in g:
            freq[_chave(c.nome)] = freq.get(_chave(c.nome), 0) + 1
        # grafia da fonte mais confiável (banner e diário antes do mapa e do HUD); empate: a mais frequente e depois a mais longa
        peso = {"banner": 3, "diario": 3, "mapa": 2, "hud": 1}
        melhor = max(g, key=lambda ic: (peso.get(ic[1].fonte, 0), freq[_chave(ic[1].nome)], len(ic[1].nome)))[1].nome
        # "Monstro de Pomar Branco" e "O Monstro de Pomar Branco" são o mesmo nome: o artigo se perde fácil no OCR
        for _, c in g:
            t = c.nome.split()
            if c.fonte in ("banner", "diario", "mapa") and len(t) > 2 and t[0].lower() in {"o", "a", "os", "as"} and _chave(" ".join(t[1:])) == _chave(melhor):
                melhor = c.nome
                break
        for _, c in g:
            canon[id(c)] = melhor
    aceitos = set(canon)
    saida: dict[str, list[Cand]] = {}
    for item, cs in por_item.items():
        vistos, lista = set(), []
        for c in cs:
            if c.tipo == "missao" and c.fonte != "quadro" and id(c) not in aceitos:
                continue
            nome = canon.get(id(c), c.nome)
            if c.tipo == "missao" and c.fonte != "quadro" and _lugar(nome, gaz):
                nome = f"{nome} (missão)"
            if (nome, c.tipo) in vistos:
                continue
            vistos.add((nome, c.tipo))
            lista.append(Cand(nome, c.tipo, c.fonte, c.estado, c.subtipo, c.evidencia))
        saida[item] = lista
    return saida
