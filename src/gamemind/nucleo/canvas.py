"""Canvas do Obsidian (formato aberto JSON Canvas, https://jsoncanvas.org) gerado a partir do grafo da partida.
O grafo tem poucas relações e muitas telas, então o canvas organiza por lugar e contexto (missões ficam em segundo plano) e mostra as capturas:
- `Quadro da partida.canvas`: o mundo da partida, uma coluna por lugar (na ordem em que apareceram) com a miniatura, os lugares
  que fazem parte dele, as pessoas e criaturas situadas ali (seta) e as vistas nas mesmas telas (sem seta: aparecer junto não é
  relação); depois facções, o que não se situa e, por último e discretas, as missões (o jogo já as mostra).
- `_canvas/<Tipo>/<nome>.canvas`: o contexto de um personagem, criatura, facção ou lugar: relações à esquerda e à direita,
  capturas em cima, "vistos nas mesmas telas" embaixo; as missões viram uma linha de texto.
- `_midia/`: miniaturas das capturas; de um clipe, o quadro em que a entidade aparece.
Só lê o grafo e as leituras; não muda nada na extração."""
import hashlib
import json
import logging
import subprocess
from collections import defaultdict
from pathlib import Path

from exportar_vault import PASTAS, arquivo
from extracao.gazetteer import norm
from PIL import Image

log = logging.getLogger("gamemind")

PASTA_CANVAS, PASTA_MIDIA, CANVAS_PARTIDA = "_canvas", "_midia", "Quadro da partida.canvas"
# cores do canvas: "1" a "6" seguem o tema do Obsidian (vermelho, laranja, amarelo, verde, ciano, roxo); hex para o resto
CORES = {"missao": "6", "personagem": "4", "local": "5", "item": "3", "decisao": "1", "faccao": "2", "criatura": "#8d6e63", "evento": "#9e9e9e"}
VERBOS = {"participa_de": "participa de", "ocorre_em": "ocorre em", "localizado_em": "fica em", "parte_de": "parte de", "concede": "concede",
          "obtido_em": "obtido em", "gera": "gera", "membro_de": "membro de", "relacionado_a": "relacionado a"}
TITULOS = {"personagem": "Personagens", "criatura": "Criaturas", "faccao": "Facções", "local": "Locais", "item": "Itens",
           "decisao": "Decisões", "evento": "Eventos", "missao": "Missões"}
CARD_W, CARD_H, THUMB_H, GAP, ALTURA_MAX = 260, 60, 146, 20, 1400
LARGURA_COLUNA = CARD_W + 2 * GAP


def _id(*partes: str) -> str:
    return hashlib.md5("|".join(partes).encode("utf-8")).hexdigest()[:16]


def _nota(no: dict) -> str:
    return f"{PASTAS[no['tipo']]}/{arquivo(no['nome'])}.md"


def _sem_sufixo(nome: str) -> str:
    return nome.removesuffix(" (missão)")


class Miniaturas:
    """Miniaturas das capturas dentro do vault, geradas sob demanda e reaproveitadas entre rodadas."""

    def __init__(self, vault: Path, midias: dict[str, tuple[Path, str, dict | None]]):
        self.vault, self.midias = Path(vault), midias   # nome do arquivo -> (caminho, tipo, leitura)
        self.geradas: set[str] = set()

    def de(self, nome_midia: str, entidade: str = "") -> str | None:
        """Caminho no vault da miniatura da captura `nome_midia` (de um clipe: o quadro em que `entidade` aparece)."""
        info = self.midias.get(nome_midia)
        if not info:
            return None
        caminho, tipo, leitura = info
        if tipo == "imagem":
            rel = f"{PASTA_MIDIA}/{Path(nome_midia).stem}.jpg"
            ok = self._imagem(caminho, self.vault / rel)
        else:
            t = self._instante(leitura, entidade)
            rel = f"{PASTA_MIDIA}/{Path(nome_midia).stem}_{int(t)}s.jpg"
            ok = self._quadro(caminho, t, self.vault / rel)
        if ok:
            self.geradas.add(rel)
            return rel
        return None

    @staticmethod
    def _atual(origem: Path, destino: Path) -> bool:
        return destino.exists() and origem.exists() and destino.stat().st_mtime >= origem.stat().st_mtime

    def _imagem(self, origem: Path, destino: Path) -> bool:
        if self._atual(origem, destino):
            return True
        try:
            destino.parent.mkdir(parents=True, exist_ok=True)
            with Image.open(origem) as im:
                im = im.convert("RGB")
                im.thumbnail((640, 360))
                im.save(destino, "JPEG", quality=80)
            return True
        except OSError as e:
            log.warning("miniatura de %s falhou: %s", origem.name, e)
            return False

    def _quadro(self, origem: Path, t: float, destino: Path) -> bool:
        if self._atual(origem, destino):
            return True
        destino.parent.mkdir(parents=True, exist_ok=True)
        cmd = ["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{t:.1f}", "-i", str(origem), "-frames:v", "1", "-vf", "scale=640:-2", "-q:v", "4", str(destino)]
        try:
            ok = subprocess.run(cmd, capture_output=True, timeout=60).returncode == 0 and destino.exists()
        except (OSError, subprocess.TimeoutExpired):
            ok = False
        if not ok:
            log.warning("quadro de %s em %.0f s não foi extraído (FFmpeg?)", origem.name, t)
        return ok

    @staticmethod
    def _instante(leitura: dict | None, entidade: str) -> float:
        """Primeiro quadro lido em que a entidade aparece (pelo dicionário ou pela estrutura da tela); senão, o do meio."""
        qs = (leitura or {}).get("quadros") or []
        if not qs:
            return 0.0
        k = norm(_sem_sufixo(entidade))
        for q in qs:
            if k and (any(norm(n) == k for n in q.get("dic", {})) or any(norm(c["nome"]) == k for c in q.get("cands", []))):
                return float(q["t"])
        return float(qs[len(qs) // 2]["t"])


class Quadro:
    """Montagem de um canvas: cartões, imagens, textos, grupos e setas, com ids estáveis entre rodadas."""

    def __init__(self, nome: str):
        self.nome = nome
        self.nos: list[dict] = []
        self.arestas: list[dict] = []
        self.pos: dict[str, dict] = {}   # entidade -> nó do cartão

    def _no(self, **kw) -> dict:
        n = {k: v for k, v in kw.items() if v is not None}
        self.nos.append(n)
        return n

    def cartao(self, no: dict, x: float, y: float, w: int = CARD_W, h: int = CARD_H) -> dict:
        n = self._no(id=_id(self.nome, "n", no["nome"]), type="file", file=_nota(no), x=int(x), y=int(y), width=w, height=h, color=CORES.get(no["tipo"]))
        self.pos[no["nome"]] = n
        return n

    def imagem(self, rel: str, x: float, y: float, chave: str) -> dict:
        return self._no(id=_id(self.nome, "i", chave, rel), type="file", file=rel, x=int(x), y=int(y), width=CARD_W, height=THUMB_H)

    def texto(self, txt: str, x: float, y: float, w: int, h: int, chave: str) -> dict:
        return self._no(id=_id(self.nome, "t", chave), type="text", text=txt, x=int(x), y=int(y), width=w, height=h)

    def grupo(self, rotulo: str, x: float, y: float, w: float, h: float, cor: str | None = None) -> dict:
        return self._no(id=_id(self.nome, "g", rotulo), type="group", label=rotulo, x=int(x), y=int(y), width=int(w), height=int(h), color=cor)

    def ligar(self, a: dict) -> None:
        """Seta de uma relação do grafo, se as duas pontas estão no canvas; o lado de saída segue a posição relativa."""
        s, o = self.pos.get(a["sujeito"]), self.pos.get(a["objeto"])
        if not s or not o or s is o:
            return
        dx = (o["x"] + o["width"] / 2) - (s["x"] + s["width"] / 2)
        dy = (o["y"] + o["height"] / 2) - (s["y"] + s["height"] / 2)
        if abs(dx) >= abs(dy):
            lados = ("right", "left") if dx > 0 else ("left", "right")
        else:
            lados = ("bottom", "top") if dy > 0 else ("top", "bottom")
        rotulo = VERBOS.get(a["predicado"], a["predicado"]) + (f" ({a['rotulo']})" if a.get("rotulo") else "")
        self.arestas.append({"id": _id(self.nome, "e", a["sujeito"], a["predicado"], a["objeto"]), "fromNode": s["id"], "fromSide": lados[0],
                             "toNode": o["id"], "toSide": lados[1], "toEnd": "arrow", "label": rotulo})

    def coluna(self, rotulo: str, x: float, y: float, blocos: list[tuple], cor: str | None = None) -> float:
        """Grupo com os blocos empilhados; passa para uma subcoluna ao lado quando fica alto demais. Devolve a largura usada.
        Bloco: ("cartao", no) | ("imagem", rel, chave) | ("texto", txt, chave)."""
        cx, cy, larg, alt = x + GAP, y + GAP, LARGURA_COLUNA, 0.0
        for b in blocos:
            h = {"cartao": CARD_H, "imagem": THUMB_H, "texto": 40}[b[0]]
            if cy + h > y + ALTURA_MAX and cy > y + GAP:
                cx, cy = cx + CARD_W + GAP, y + GAP
                larg += CARD_W + GAP
            if b[0] == "cartao":
                self.cartao(b[1], cx, cy)
            elif b[0] == "imagem":
                self.imagem(b[1], cx, cy, b[2])
            else:
                self.texto(b[1], cx, cy, CARD_W, 40, b[2])
            cy += h + GAP
            alt = max(alt, cy - y)
        self.grupo(rotulo, x, y, larg, max(alt, CARD_H + 2 * GAP), cor)
        return larg

    def salvar(self, caminho: Path) -> None:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(json.dumps({"nodes": self.nos, "edges": self.arestas}, ensure_ascii=False, indent=1), encoding="utf-8")


class _Indice:
    """Consultas sobre o grafo usadas pelos canvas. Missões ficam de fora do contexto: são informação que o jogo já dá."""
    TELA_LONGA = 6          # tela com mais entidades que isso é lista (glossário, mapa, diário): não indica que estavam juntas
    SCORE_MINIMO = 0.5      # uma tela com até 3 outras entidades, ou duas telas de lista curta
    RECORRENTE = 8          # quem aparece em mais capturas que isso (o protagonista) está em toda parte: não é situado por proximidade

    def __init__(self, g: dict):
        self.nos = g["nos"]                                   # já na ordem de primeira aparição (src/grafo.py)
        existentes = {n["nome"] for n in self.nos}
        self.arestas = [a for a in g["arestas"] if a["sujeito"] in existentes and a["objeto"] in existentes]   # o grafo pode citar quem não virou nó
        self.por_nome = {n["nome"]: n for n in self.nos}
        self.tipo = {n["nome"]: n["tipo"] for n in self.nos}
        self.ordem = {n["nome"]: i for i, n in enumerate(self.nos)}
        self.vizinhos: dict[str, set] = defaultdict(set)
        for a in self.arestas:
            self.vizinhos[a["sujeito"]].add(a["objeto"])
            self.vizinhos[a["objeto"]].add(a["sujeito"])
        self.telas = {n["nome"]: list(dict.fromkeys(f["arquivo"] for f in n.get("fontes", []))) for n in self.nos}
        por_tela: dict[str, set] = defaultdict(set)
        for nome, ts in self.telas.items():
            if self.tipo[nome] != "missao":
                for t in ts:
                    por_tela[t].add(nome)
        self.por_tela = por_tela
        self.missoes = [n for n in self.nos if n["tipo"] == "missao"]
        # hierarquia de lugares: local parte_de local
        self.pai = {a["sujeito"]: a["objeto"] for a in self.arestas
                    if a["predicado"] == "parte_de" and self.tipo.get(a["sujeito"]) == "local" and self.tipo.get(a["objeto"]) == "local"}

    def raiz(self, local: str) -> str:
        vistos = set()
        while local in self.pai and local not in vistos:
            vistos.add(local)
            local = self.pai[local]
        return local

    def _dentro(self, local: str, ancestral: str) -> bool:
        vistos = set()
        while local in self.pai and local not in vistos:
            vistos.add(local)
            local = self.pai[local]
            if local == ancestral:
                return True
        return False

    def descendentes(self, local: str) -> list[str]:
        """O local e tudo que é parte dele, em ordem de aparição."""
        return [local] + [n["nome"] for n in self.nos if n["tipo"] == "local" and self._dentro(n["nome"], local)]

    def score(self, a: str, b: str) -> float:
        """Quanto duas entidades foram vistas juntas: cada tela em comum vale 1/(outras entidades na tela); telas de lista valem 0."""
        total = 0.0
        for t in set(self.telas.get(a, [])) & set(self.telas.get(b, [])):
            n = len(self.por_tela[t])
            if 1 < n <= self.TELA_LONGA:
                total += 1 / (n - 1)
        return total

    def relacionadas(self, nome: str) -> list[dict]:
        """Vizinhos pelo grafo (relações lidas), sem missões."""
        return [self.por_nome[v] for v in sorted(self.vizinhos[nome], key=self.ordem.get) if v in self.por_nome and self.tipo[v] != "missao"]

    def missoes_de(self, nome: str) -> list[str]:
        return [v for v in sorted(self.vizinhos[nome], key=self.ordem.get) if self.tipo.get(v) == "missao"]

    def mesmas_telas(self, nome: str, limite: int = 12) -> list[dict]:
        """Entidades vistas junto (sem relação afirmada), das mais para as menos ligadas; sem missões."""
        pontos = [(self.score(nome, n["nome"]), n) for n in self.nos
                  if n["nome"] != nome and n["tipo"] != "missao" and n["nome"] not in self.vizinhos[nome]]
        pontos = [(p, n) for p, n in pontos if p >= self.SCORE_MINIMO]
        pontos.sort(key=lambda x: (-x[0], self.ordem[x[1]["nome"]]))
        return [n for _, n in pontos[:limite]]

    def capturas(self, nome: str) -> list[str]:
        return self.telas.get(nome, [])


LEGENDA = ("**Mundo da partida** (gerado pelo GameMind; é refeito a cada rodada, então anote em outro canvas)\n"
           "Uma coluna por lugar: os lugares que fazem parte dele e as pessoas e criaturas que a partida situa ali. "
           "Setas: relações lidas nas telas. \"Vistos nas mesmas telas\": apareceram juntos, sem relação afirmada. "
           "Missões ficam por último, só como referência (o jogo já as mostra).\n"
           "Cores: verde personagem · ciano local · laranja facção · marrom criatura · amarelo item · vermelho decisão")
ESTRUTURAIS = {"localizado_em", "parte_de", "membro_de"}   # setas que valem mesmo entre colunas diferentes
TIPOS_MUNDO = ("personagem", "criatura", "faccao")          # o que se situa em um lugar ou grupo


def canvas_partida(g: dict, mini: Miniaturas) -> Quadro:
    ix = _Indice(g)
    q = Quadro("partida")
    coluna_de: dict[str, str] = {}
    usado: set[str] = set()

    def lugar_de(nome: str) -> str | None:
        """Lugar-raiz onde a partida situa a entidade pela relação `localizado_em`."""
        for a in ix.arestas:
            if a["sujeito"] == nome and a["predicado"] == "localizado_em" and a["objeto"] in ix.por_nome:
                return ix.raiz(a["objeto"])
        return None

    raizes = [n["nome"] for n in ix.nos if n["tipo"] == "local" and ix.raiz(n["nome"]) == n["nome"]]
    colunas: dict[str, dict] = {r: {"fixos": [], "co": []} for r in raizes}
    for n in ix.nos:   # pessoas com lugar afirmado
        if n["tipo"] in TIPOS_MUNDO and (r := lugar_de(n["nome"])) in colunas:
            colunas[r]["fixos"].append(n)
            usado.add(n["nome"])
    for n in ix.nos:   # as demais, pelo lugar com que mais dividem telas (menos as recorrentes)
        if n["tipo"] in TIPOS_MUNDO and n["nome"] not in usado and len(ix.capturas(n["nome"])) <= ix.RECORRENTE:
            melhor = max(((max(ix.score(n["nome"], d) for d in ix.descendentes(r)), r) for r in raizes), default=(0, None))
            if melhor[0] >= ix.SCORE_MINIMO:
                colunas[melhor[1]]["co"].append(n)
                usado.add(n["nome"])

    x = 0.0
    q.texto(LEGENDA, 0, -300, 1000, 240, "legenda")
    soltos_locais = []
    for r in raizes:
        c = colunas[r]
        filhos = [ix.por_nome[d] for d in ix.descendentes(r)[1:]]
        if not (c["fixos"] or c["co"] or filhos):
            soltos_locais.append(ix.por_nome[r])
            continue
        blocos: list[tuple] = [("cartao", ix.por_nome[r])]
        caps = ix.capturas(r)
        if caps and (rel := mini.de(caps[0], r)):
            blocos.append(("imagem", rel, r))
        blocos += [("cartao", n) for n in filhos]
        blocos += [("cartao", n) for n in c["fixos"]]
        if c["co"]:
            blocos.append(("texto", "*vistos nas mesmas telas:*", r + "#co"))
            blocos += [("cartao", n) for n in c["co"]]
        for b in blocos:
            if b[0] == "cartao":
                coluna_de[b[1]["nome"]] = r
                usado.add(b[1]["nome"])
        x += q.coluna(r, x, 0, blocos, CORES["local"]) + 80

    # facções com membros ainda sem coluna ganham coluna própria; as demais ficam nas colunas por tipo
    for n in ix.nos:
        if n["tipo"] != "faccao" or n["nome"] in usado:
            continue
        membros = [m for m in ix.relacionadas(n["nome"]) if m["tipo"] in ("personagem", "criatura") and m["nome"] not in usado]
        if membros:
            blocos = [("cartao", n)] + [("cartao", m) for m in membros]
            for b in blocos:
                coluna_de[b[1]["nome"]] = n["nome"]
                usado.add(b[1]["nome"])
            x += q.coluna(n["nome"], x, 0, blocos, CORES["faccao"]) + 80

    soltos: dict[str, list[dict]] = defaultdict(list)
    for n in ix.nos:
        if n["nome"] not in usado and n["tipo"] != "missao" and n not in soltos_locais:
            soltos[n["tipo"]].append(n)
    soltos["local"] = soltos["local"] + soltos_locais
    for tipo, titulo in (("personagem", "Personagens"), ("criatura", "Criaturas"), ("faccao", "Facções"), ("local", "Outros lugares"),
                         ("decisao", "Decisões"), ("evento", "Eventos"), ("item", "Itens")):
        if soltos.get(tipo):
            x += q.coluna(titulo, x, 0, [("cartao", n) for n in sorted(soltos[tipo], key=lambda n: ix.ordem[n["nome"]])], CORES.get(tipo)) + 80
            coluna_de.update({n["nome"]: tipo for n in soltos[tipo]})
    if ix.missoes:   # por último e discretas: referência, não contexto
        q.coluna("Missões (referência: o jogo já mostra)", x, 0, [("cartao", m) for m in ix.missoes], "#6b6b6b")
        coluna_de.update({m["nome"]: "missoes" for m in ix.missoes})
    for a in ix.arestas:
        s, o = a["sujeito"], a["objeto"]
        if s not in q.pos or o not in q.pos or "missao" in (ix.tipo[s], ix.tipo[o]):
            continue   # relações com missões ficam nas notas e nos canvas de cada entidade
        if coluna_de.get(s) == coluna_de.get(o) or a["predicado"] in ESTRUTURAIS:
            q.ligar(a)
    return q


def canvas_entidade(g: dict, nome: str, mini: Miniaturas, max_capturas: int = 4) -> Quadro:
    """Contexto de uma entidade (personagem, criatura, facção ou lugar): quem e onde se liga a ela, e o que foi visto junto."""
    ix = _Indice(g)
    e = ix.por_nome[nome]
    q = Quadro("entidade|" + nome)
    q.cartao(e, -20, -10, CARD_W + 40, CARD_H + 20)
    rel = ix.relacionadas(nome)
    esq = [n for n in rel if n["tipo"] in ("personagem", "criatura", "faccao")]
    dir_ = [n for n in rel if n["tipo"] == "local"]
    baixo = [n for n in rel if n not in esq and n not in dir_]
    for i, n in enumerate(esq):
        q.cartao(n, -CARD_W - 200, (i - (len(esq) - 1) / 2) * (CARD_H + GAP))
    for i, n in enumerate(dir_):
        q.cartao(n, CARD_W + 200, (i - (len(dir_) - 1) / 2) * (CARD_H + GAP))
    meia_lateral = max(len(esq), len(dir_)) / 2 * (CARD_H + GAP)   # quanto as colunas laterais descem/sobem a partir do centro
    y_baixo = max(220, meia_lateral + 80)
    for i, n in enumerate(baixo):
        q.cartao(n, (i - (len(baixo) - 1) / 2) * (CARD_W + GAP), y_baixo)
    caps = [r for r in (mini.de(c, nome) for c in ix.capturas(nome)[:max_capturas]) if r]
    y_caps = min(-THUMB_H - 140, -meia_lateral - THUMB_H - 80)
    for i, r in enumerate(caps):
        q.imagem(r, (i - (len(caps) - 1) / 2) * (CARD_W + GAP), y_caps, r)
    co = ix.mesmas_telas(nome)
    if co:
        y = (y_baixo + CARD_H + 100) if baixo else y_baixo
        largura = min(len(co), 4) * (CARD_W + GAP) + GAP
        x0 = -largura / 2
        for i, n in enumerate(co):
            q.cartao(n, x0 + GAP + (i % 4) * (CARD_W + GAP), y + GAP + (i // 4) * (CARD_H + GAP))
        linhas = (len(co) + 3) // 4
        q.grupo("Vistos nas mesmas telas (sem relação afirmada)", x0, y, largura, linhas * (CARD_H + GAP) + GAP)
    miss = ix.missoes_de(nome)
    if miss:   # só uma linha de referência, sem cartões
        linha = "*Missões (referência):* " + "; ".join(miss)
        q.texto(linha, -20, 90, CARD_W + 40, 30 + 24 * (len(linha) // 38 + 1), "missoes")   # a altura acompanha o tamanho do texto
    for a in ix.arestas:
        if "missao" not in (ix.tipo[a["sujeito"]], ix.tipo[a["objeto"]]):
            q.ligar(a)
    return q


def tem_contexto(ix: _Indice, nome: str) -> bool:
    """Vale um canvas próprio? Só se há o que mostrar além da própria nota: relação, tela dividida ou mais de uma captura."""
    return bool(ix.relacionadas(nome) or ix.mesmas_telas(nome) or len(ix.capturas(nome)) >= 2)


def gerar(g: dict, vault: Path, midias: dict[str, tuple[Path, str, dict | None]], ao_gravar=None) -> tuple[dict[str, list[str]], set[str]]:
    """Escreve os canvas e as miniaturas no vault. Devolve (linhas a anexar nas notas, arquivos gerados relativos ao vault)."""
    vault = Path(vault)
    mini = Miniaturas(vault, midias)
    geradas = {CANVAS_PARTIDA}
    canvas_partida(g, mini).salvar(vault / CANVAS_PARTIDA)
    if ao_gravar:
        ao_gravar(vault / CANVAS_PARTIDA)
    ix = _Indice(g)
    anexos: dict[str, list[str]] = {}
    for n in g["nos"]:
        if n["tipo"] not in ("personagem", "criatura", "faccao", "local") or not tem_contexto(ix, n["nome"]):
            continue
        rel = f"{PASTA_CANVAS}/{PASTAS[n['tipo']]}/{arquivo(n['nome'])}.canvas"
        canvas_entidade(g, n["nome"], mini).salvar(vault / rel)
        geradas.add(rel)
        if ao_gravar:
            ao_gravar(vault / rel)
        anexos[n["nome"]] = [f"Contexto: [[{rel}|canvas de {n['nome']}]] · [[{CANVAS_PARTIDA}|mundo da partida]]"]
    return anexos, geradas | mini.geradas
