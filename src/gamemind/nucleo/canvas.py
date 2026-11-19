"""Canvas do Obsidian (formato aberto JSON Canvas, https://jsoncanvas.org) gerado a partir do grafo da partida.
O grafo tem poucas relações e muitas telas, então o canvas organiza pela relevância de cada entidade na partida e mostra as capturas:
- `Quadro da partida.canvas`: no centro, empilhados na vertical, os destaques (`Relevancia`: capturas em que a entidade aparece +
  relações lidas, relativo à maior da partida), cada um com a captura mais "dele", miniaturas e um resumo; dos lados, os vizinhos
  de cada destaque (quem se liga a ele: pessoas à esquerda, lugares à direita), com seta para relação lida e linha cinza para
  "vistos nas mesmas telas"; embaixo, o restante do mundo em cartões menores e, passado um limite, em listas de links; por
  último, missões, itens, decisões e eventos só como listas (o jogo já os mostra). Todas as regras são relativas à própria
  partida, nada é específico de um jogo, e o quadro tem tamanho limitado mesmo com centenas de entidades.
- o contexto de um personagem, criatura, facção ou lugar (capturas e "vistos nas mesmas telas") vai na própria nota dele
  (`contexto_nota`): um canvas por entidade duplicava cada uma no vault e no grafo do Obsidian.
- `_midia/`: miniaturas das capturas; de um clipe, o quadro em que a entidade aparece.
Só lê o grafo e as leituras; não muda nada na extração."""
import hashlib
import json
import logging
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

from exportar_vault import PASTAS, arquivo, gravar_se_mudou, link
from schema import SIMETRICOS

from .consolidacao import TELA_LISTA
from extracao.gazetteer import norm
from PIL import Image

log = logging.getLogger("gamemind")

PASTA_MIDIA, CANVAS_PARTIDA = "_midia", "Quadro da partida.canvas"
# cores do canvas: "1" a "6" seguem o tema do Obsidian (vermelho, laranja, amarelo, verde, ciano, roxo); hex para o resto
CORES = {"missao": "6", "personagem": "4", "local": "5", "item": "3", "decisao": "1", "faccao": "2", "criatura": "#8d6e63", "evento": "#9e9e9e"}
VERBOS = {"participa_de": "participa de", "ocorre_em": "ocorre em", "localizado_em": "fica em", "parte_de": "parte de", "concede": "concede",
          "obtido_em": "obtido em", "gera": "gera", "membro_de": "membro de", "relacionado_a": "relacionado a"}
CARD_W, CARD_H, THUMB_H, GAP = 260, 60, 146, 20


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
        self._ids_arestas: set[str] = set()

    def _no(self, **kw) -> dict:
        n = {k: v for k, v in kw.items() if v is not None}
        self.nos.append(n)
        return n

    def cartao(self, no: dict, x: float, y: float, w: int = CARD_W, h: int = CARD_H) -> dict:
        n = self._no(id=_id(self.nome, "n", no["nome"]), type="file", file=_nota(no), x=int(x), y=int(y), width=int(w), height=int(h),
                     color=CORES.get(no["tipo"]))
        self.pos[no["nome"]] = n
        return n

    def imagem(self, rel: str, x: float, y: float, chave: str, w: int = CARD_W, h: int = THUMB_H) -> dict:
        return self._no(id=_id(self.nome, "i", chave, rel), type="file", file=rel, x=int(x), y=int(y), width=int(w), height=int(h))

    def texto(self, txt: str, x: float, y: float, w: int, h: int, chave: str, cor: str | None = None) -> dict:
        return self._no(id=_id(self.nome, "t", chave), type="text", text=txt, x=int(x), y=int(y), width=int(w), height=int(h), color=cor)

    def grupo(self, rotulo: str, x: float, y: float, w: float, h: float, cor: str | None = None, chave: str = "") -> dict:
        return self._no(id=_id(self.nome, "g", chave or rotulo), type="group", label=rotulo, x=int(x), y=int(y), width=int(w), height=int(h),
                        color=cor)

    def _aresta(self, chave: tuple, s: dict, o: dict, rotulo: str, cor: str | None = None, seta: bool = True,
                lados: tuple[str, str] | None = None) -> None:
        eid = _id(self.nome, *chave)
        if eid in self._ids_arestas:
            return
        self._ids_arestas.add(eid)
        dx = (o["x"] + o["width"] / 2) - (s["x"] + s["width"] / 2)
        dy = (o["y"] + o["height"] / 2) - (s["y"] + s["height"] / 2)
        if lados:
            pass
        elif abs(dx) >= abs(dy):
            lados = ("right", "left") if dx > 0 else ("left", "right")
        else:
            lados = ("bottom", "top") if dy > 0 else ("top", "bottom")
        a = {"id": eid, "fromNode": s["id"], "fromSide": lados[0], "toNode": o["id"], "toSide": lados[1],
             "toEnd": "arrow" if seta else "none", "label": rotulo}
        if cor:
            a["color"] = cor
        self.arestas.append(a)

    def salvar(self, caminho: Path) -> bool:
        """Grava o canvas; devolve False se o arquivo já tinha exatamente este conteúdo."""
        caminho.parent.mkdir(parents=True, exist_ok=True)
        return gravar_se_mudou(caminho, json.dumps({"nodes": self.nos, "edges": self.arestas}, ensure_ascii=False, indent=1))


class _Indice:
    """Consultas sobre o grafo usadas pelos canvas. Missões ficam de fora do contexto: são informação que o jogo já dá."""
    TELA_LONGA = TELA_LISTA   # tela de lista (glossário, mapa, diário): não indica que estavam juntas
    SCORE_MINIMO = 0.5      # uma tela com até 3 outras entidades, ou duas telas de lista curta

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


# ---------------------------------------------------------------- quadro da partida
# O quadro só mostra o que é do jogo (nomes, capturas, descrições, relações lidas). A relevância de cada entidade (em quantas
# capturas aparece e quantas relações tem, relativo à própria partida) só decide onde e com que tamanho ela entra:
# - no alto, lado a lado, os protagonistas (os personagens mais presentes);
# - abaixo, uma coluna por lugar principal: o lugar em cima e, embaixo, os sublugares, as facções, os personagens e as criaturas
#   ligados a ele; outro lugar, com os seus, é outra coluna ao lado. Facção sem lugar e com membros também pode ser coluna;
# - embaixo, o restante em cartões menores (passado um limite, só links) e, por último, missões, itens, decisões e eventos.
TIPOS_MUNDO = ("personagem", "criatura", "faccao", "local")   # o contexto do mundo; o resto fica como referência
ORDEM_NA_COLUNA = {"local": 0, "faccao": 1, "personagem": 2, "criatura": 3}
REFERENCIA = (("missao", "Missões"), ("item", "Itens"), ("decisao", "Decisões"), ("evento", "Eventos"))
TITULO_TIPO = {"personagem": "Personagens", "criatura": "Criaturas", "faccao": "Facções", "local": "Lugares"}
PESO_RELACAO = 1.5         # uma relação lida vale uma captura e meia
FRACAO_PROTAGONISTA = 0.5  # protagonista: relevância de 50%+ da do personagem mais relevante (ou em toda parte)...
MAX_PROTAGONISTAS = 4      # ...e no máximo 4, na linha de cima
ONIPRESENTE = 0.4          # em 40% ou mais das capturas: aparecer junto com ele não diz nada
MAX_COLUNAS = 6            # colunas de lugar (ou facção) lado a lado
MAX_MEMBROS = 8            # entidades embaixo da cabeça de cada coluna
FRACAO_NORMAL = 0.15       # membro com miniatura; abaixo disso, só o cartão
MAX_OUTROS = 24            # cartões na faixa de baixo; o resto vira lista de links
MAX_LISTA = 40             # links numa lista
W_PROT, W_COL, H_CARD, W_MINI, H_MINI, W_MENOR, H_MENOR = 460, 320, 56, 100, 56, 220, 44
GAP_COL, GAP_LINHA = 100, 180
COR_JUNTO = "#9e9e9e"
COR_RELACAO = {"localizado_em": "5", "parte_de": "5", "membro_de": "2"}


def _altura_texto(txt: str, largura: int) -> int:
    """Altura de um cartão de texto do Obsidian para caber `txt` (estimativa: ~8,5 px por caractere, 26 px por linha)."""
    por_linha = max(10, int((largura - 24) / 8.5))
    linhas = sum(max(1, -(-len(l) // por_linha)) for l in txt.splitlines()) or 1
    return 28 + 26 * linhas


class Relevancia:
    """Quanto cada entidade pesa na partida, só pelo que foi capturado: em quantas capturas aparece e quantas relações lidas tem."""

    def __init__(self, ix: _Indice):
        self.ix = ix
        self.total = max(1, len({t for n in ix.nos for t in ix.capturas(n["nome"])}))
        self.pontos = {n["nome"]: len(ix.capturas(n["nome"])) + PESO_RELACAO * len(ix.relacionadas(n["nome"])) for n in ix.nos}
        self.pares: Counter = Counter()
        for a in ix.arestas:
            self.pares[frozenset((a["sujeito"], a["objeto"]))] += 1
        self.mundo = sorted((n for n in ix.nos if n["tipo"] in TIPOS_MUNDO), key=lambda n: (-self.pontos[n["nome"]], ix.ordem[n["nome"]]))
        self.topo = self.pontos[self.mundo[0]["nome"]] if self.mundo else 1.0

    def onipresente(self, nome: str) -> bool:
        caps = len(self.ix.capturas(nome))
        return caps >= 3 and caps / self.total >= ONIPRESENTE

    def afinidade(self, a: str, b: str) -> float:
        """Relação lida pesa mais que aparecer junto; aparecer junto com quem está em toda parte vale metade."""
        junto = self.ix.score(a, b) * (0.5 if self.onipresente(a) or self.onipresente(b) else 1.0)
        return 3 * self.pares[frozenset((a, b))] + junto

    def normal(self, nome: str) -> bool:
        return self.pontos[nome] >= FRACAO_NORMAL * self.topo

    def protagonistas(self) -> list[dict]:
        pers = [n for n in self.mundo if n["tipo"] == "personagem" and len(self.ix.capturas(n["nome"])) >= 2]
        if not pers:
            return []
        topo = self.pontos[pers[0]["nome"]]
        return [n for n in pers if self.pontos[n["nome"]] >= FRACAO_PROTAGONISTA * topo or self.onipresente(n["nome"])][:MAX_PROTAGONISTAS]

    def colunas(self, fora: set[str]) -> list[dict]:
        """Colunas do quadro: {"cabeca": nó, "membros": [nós]}, da mais pesada para a mais leve. `fora`: quem já está em outro lugar."""
        ix, usados = self.ix, set(fora)
        grupos: dict[str, list[dict]] = defaultdict(list)   # lugar-raiz -> ele e os lugares que fazem parte dele
        for n in self.mundo:
            if n["tipo"] == "local" and n["nome"] not in usados:
                grupos[ix.raiz(n["nome"])].append(n)
        peso = {r: sum(self.pontos[n["nome"]] for n in ns) for r, ns in grupos.items() if r in ix.por_nome}
        colunas = []
        for r in sorted(peso, key=lambda r: (-peso[r], ix.ordem[r]))[:MAX_COLUNAS]:
            colunas.append({"cabeca": ix.por_nome[r], "membros": [n for n in grupos[r] if n["nome"] != r][:MAX_MEMBROS]})
            usados |= {r} | {n["nome"] for n in colunas[-1]["membros"]}
        # facções, personagens e criaturas: para a coluna com que mais se ligam (relação lida; senão, telas em comum)
        for n in self.mundo:
            if n["nome"] in usados or n["tipo"] == "local":
                continue
            melhor = max(((max(self.afinidade(n["nome"], x["nome"]) for x in [c["cabeca"], *c["membros"]]), k)
                          for k, c in enumerate(colunas)), default=(0, None))
            if melhor[1] is not None and melhor[0] >= ix.SCORE_MINIMO and len(colunas[melhor[1]]["membros"]) < MAX_MEMBROS:
                colunas[melhor[1]]["membros"].append(n)
                usados.add(n["nome"])
        # facção que sobrou com membros (ou relevante) vira coluna própria, se houver vaga
        for f in self.mundo:
            if len(colunas) >= MAX_COLUNAS:
                break
            if f["tipo"] != "faccao" or f["nome"] in usados:
                continue
            membros = [n for n in self.mundo if n["tipo"] in ("personagem", "criatura") and n["nome"] not in usados
                       and self.afinidade(f["nome"], n["nome"]) >= ix.SCORE_MINIMO][:MAX_MEMBROS]
            if membros or self.normal(f["nome"]):
                colunas.append({"cabeca": f, "membros": membros})
                usados |= {f["nome"]} | {n["nome"] for n in membros}
        colunas = [c for c in colunas if c["membros"] or self.normal(c["cabeca"]["nome"])]   # lugar solto e pouco visto: embaixo
        for c in colunas:
            c["membros"].sort(key=lambda n: (ORDEM_NA_COLUNA[n["tipo"]], -self.pontos[n["nome"]], ix.ordem[n["nome"]]))
        return colunas


def _no_meio(itens: list) -> list:
    """A mais pesada no meio e as outras alternando dos lados (itens já do mais para o menos pesado)."""
    esquerda, direita = [], []
    for i, it in enumerate(itens):
        (direita if i % 2 == 0 else esquerda).append(it)
    return esquerda[::-1] + direita


def resumo(ix: _Indice, no: dict) -> str:
    """Texto do bloco de uma entidade: só o que o jogo diz (descrição, relações lidas, missões). Vazio se não há nada."""
    nome = no["nome"]
    linhas = [no["descricao"]] if no.get("descricao") else []
    ligacoes = []
    for a in ix.arestas:
        if "missao" in (ix.tipo[a["sujeito"]], ix.tipo[a["objeto"]]):
            continue
        verbo = VERBOS.get(a["predicado"], a["predicado"])
        if a["sujeito"] == nome or (a["objeto"] == nome and a["predicado"] in SIMETRICOS):
            outro = a["objeto"] if a["sujeito"] == nome else a["sujeito"]
            ligacoes.append(f"{verbo} [[{arquivo(outro)}]]")
        elif a["objeto"] == nome:   # relação recebida: a frase inteira ("Odo fica em Vale Alto")
            ligacoes.append(f"[[{arquivo(a['sujeito'])}]] {verbo} {nome}")
    if ligacoes:
        linhas.append(" · ".join(ligacoes[:4]))
    miss = ix.missoes_de(nome)
    if miss:
        linhas.append("Missões: " + ", ".join(f"[[{arquivo(m)}]]" for m in miss[:3]))
    return "\n".join(linhas)


def _capturas_proprias(ix: _Indice, nome: str, usadas: set[str] = frozenset()) -> list[str]:
    """Capturas da entidade, das mais dela (menos gente na tela) para as de lista; as já mostradas noutro bloco vão para o fim."""
    caps = ix.capturas(nome)
    return sorted(caps, key=lambda t: (t in usadas, len(ix.por_tela.get(t, ())), caps.index(t)))


def _lista(nos: list[dict], titulo: str) -> str:
    return f"**{titulo}**\n" + " · ".join(f"[[{arquivo(n['nome'])}]]" for n in nos[:MAX_LISTA]) + (" · …" if len(nos) > MAX_LISTA else "")


class _Montagem:
    """Posições do quadro: blocos (cartão, capturas e texto) e membros de coluna (cartão com miniatura)."""

    def __init__(self, ix: _Indice, rel: Relevancia, mini: Miniaturas):
        self.ix, self.rel, self.mini, self.q = ix, rel, mini, Quadro("partida")
        self.usadas: set[str] = set()   # capturas já mostradas: cada bloco prefere as suas

    def _capturas(self, nome: str, n: int) -> list[str]:
        escolhidas = _capturas_proprias(self.ix, nome, self.usadas)[:n]
        self.usadas.update(escolhidas)
        return [r for r in (self.mini.de(c, nome) for c in escolhidas) if r]

    def bloco(self, no: dict, x: float, y: float, w: int, miniaturas: int) -> float:
        """Cartão, captura principal, até `miniaturas` capturas menores e o texto do jogo; devolve a altura."""
        q, y0 = self.q, y
        q.cartao(no, x, y, w, 60)
        y += 60 + GAP
        caps = self._capturas(no["nome"], 1 + miniaturas)
        if caps:
            q.imagem(caps[0], x, y, no["nome"] + "#1", w, int(w * 9 / 16))
            y += int(w * 9 / 16) + GAP
        if len(caps) > 1:
            wm = (w - GAP * (len(caps) - 2)) // (len(caps) - 1)
            for i, r in enumerate(caps[1:]):
                q.imagem(r, x + i * (wm + GAP), y, no["nome"] + f"#{i + 2}", wm, int(wm * 9 / 16))
            y += int(wm * 9 / 16) + GAP
        txt = resumo(self.ix, no)
        if txt:
            h = _altura_texto(txt, w)
            q.texto(txt, x, y, w, h, no["nome"] + "#texto")
            y += h + GAP
        return y - y0

    def membro(self, no: dict, x: float, y: float) -> float:
        """Membro de coluna: miniatura à esquerda (se relevante e com captura) e o cartão; devolve a altura."""
        img = self._capturas(no["nome"], 1) if self.rel.normal(no["nome"]) else []
        if img:
            self.q.imagem(img[0], x, y, no["nome"], W_MINI, H_MINI)
            self.q.cartao(no, x + W_MINI + GAP, y, W_COL - W_MINI - GAP, H_CARD)
            return H_MINI
        self.q.cartao(no, x, y, W_COL, H_CARD)
        return H_CARD


def canvas_partida(g: dict, mini: Miniaturas) -> Quadro:
    ix = _Indice(g)
    rel = Relevancia(ix)
    m = _Montagem(ix, rel, mini)
    q = m.q
    prot = rel.protagonistas()
    colunas = _no_meio(rel.colunas({p["nome"] for p in prot}))
    grupo: dict[str, tuple] = {}   # entidade -> onde está ("prot", i) ou ("col", k, é_cabeça): decide quais setas desenhar

    # linha de cima: protagonistas, centrados
    largura = len(prot) * W_PROT + GAP_COL * max(0, len(prot) - 1)
    alt = 0.0
    for i, p in enumerate(prot):
        alt = max(alt, m.bloco(p, -largura / 2 + i * (W_PROT + GAP_COL), 0, W_PROT, 2))
        grupo[p["nome"]] = ("prot", i)
    y = alt + GAP_LINHA if prot else 0.0

    # colunas: cabeça em cima, membros embaixo; lado a lado, a mais pesada no meio
    largura = len(colunas) * W_COL + GAP_COL * max(0, len(colunas) - 1)
    fim = y
    for k, c in enumerate(colunas):
        x = -largura / 2 + k * (W_COL + GAP_COL)
        cy = y + GAP + m.bloco(c["cabeca"], x, y + GAP, W_COL, 0)
        grupo[c["cabeca"]["nome"]] = ("col", k, True)
        for n in c["membros"]:
            cy += m.membro(n, x, cy) + GAP
            grupo[n["nome"]] = ("col", k, False)
        q.grupo("", x - GAP, y, W_COL + 2 * GAP, cy - y + GAP, CORES.get(c["cabeca"]["tipo"]), "coluna|" + c["cabeca"]["nome"])
        fim = max(fim, cy + GAP)
    y = fim + GAP_LINHA if colunas else y

    # embaixo: o restante do mundo em cartões menores, por tipo; passado o limite, só links
    resto = [n for n in rel.mundo if n["nome"] not in grupo]
    cartoes = {n["nome"] for n in resto[:MAX_OUTROS]}
    x, fim = -largura / 2 if colunas else 0.0, y
    for tipo in TIPOS_MUNDO:
        do_tipo = [n for n in resto if n["tipo"] == tipo]
        if not do_tipo:
            continue
        cy = y + GAP
        for n in (n for n in do_tipo if n["nome"] in cartoes):
            q.cartao(n, x + GAP, cy, W_MENOR, H_MENOR)
            cy += H_MENOR + GAP
        links = [n for n in do_tipo if n["nome"] not in cartoes]
        if links:
            txt = _lista(links, TITULO_TIPO[tipo])
            h = _altura_texto(txt, W_MENOR)
            q.texto(txt, x + GAP, cy, W_MENOR, h, "outros#" + tipo)
            cy += h + GAP
        q.grupo(TITULO_TIPO[tipo], x, y, W_MENOR + 2 * GAP, cy - y, CORES.get(tipo), "outros|" + tipo)
        x += W_MENOR + 2 * GAP + GAP_COL
        fim = max(fim, cy)
    y = fim + GAP_LINHA if resto else y

    # por último: missões, itens, decisões e eventos, só como listas de links
    x = -largura / 2 if colunas else 0.0
    for tipo, titulo in REFERENCIA:
        nos = [n for n in ix.nos if n["tipo"] == tipo]
        if nos:
            txt = _lista(nos, titulo)
            q.texto(txt, x, y, W_COL, _altura_texto(txt, W_COL), "ref#" + tipo, CORES.get(tipo))
            x += W_COL + GAP_COL

    # setas das relações lidas, só entre vizinhos no quadro (para não cruzar tudo): na mesma coluna (pela direita, sem passar
    # por cima dos membros), entre protagonistas, de protagonista para cabeça de coluna e entre cabeças de colunas vizinhas
    for a in ix.arestas:
        s, o = grupo.get(a["sujeito"]), grupo.get(a["objeto"])
        if not s or not o or "missao" in (ix.tipo[a["sujeito"]], ix.tipo[a["objeto"]]):
            continue
        if s[0] == o[0] == "col" and s[1] == o[1]:
            lados = ("right", "right")
        elif s[0] == "prot" or o[0] == "prot":
            if not (s[0] == o[0] or (s if s[0] == "col" else o)[2]):
                continue
            lados = None
        elif s[2] and o[2] and abs(s[1] - o[1]) == 1:
            lados = None
        else:
            continue
        rotulo = VERBOS.get(a["predicado"], a["predicado"]) + (f" ({a['rotulo']})" if a.get("rotulo") else "")
        sn, on = q.pos[a["sujeito"]], q.pos[a["objeto"]]
        q._aresta(("e", a["sujeito"], a["predicado"], a["objeto"]), sn, on, rotulo, COR_RELACAO.get(a["predicado"]), True, lados)
    # protagonista e o lugar (ou facção) com que mais aparece, sem relação lida: linha cinza, sem texto
    for p in prot:
        perto = [(rel.afinidade(p["nome"], c["cabeca"]["nome"]), c["cabeca"]["nome"]) for c in colunas]
        af, cab = max(perto, default=(0, None))
        if cab and af >= ix.SCORE_MINIMO and not rel.pares[frozenset((p["nome"], cab))]:
            q._aresta(("j", p["nome"], cab), q.pos[p["nome"]], q.pos[cab], "", COR_JUNTO, False)
    return q


TIPOS_CONTEXTO = ("personagem", "criatura", "faccao", "local")   # quem ganha capturas e "vistos nas mesmas telas" na própria nota


def contexto_nota(ix: _Indice, nome: str, mini: Miniaturas, max_capturas: int = 4) -> tuple[list[str], list[str]]:
    """O contexto de uma entidade, escrito na própria nota dela (e não num canvas à parte, que duplicaria cada entidade no
    vault e no grafo do Obsidian). Devolve (linhas logo abaixo do título, seções antes das fontes): o link para o mundo da
    partida, até `max_capturas` miniaturas e quem foi visto nas mesmas telas. As relações lidas e as missões já estão na nota."""
    topo = [f"[[{CANVAS_PARTIDA}|Ver no mundo da partida]]"]
    secoes: list[str] = []
    caps = [r for r in (mini.de(c, nome) for c in ix.capturas(nome)[:max_capturas]) if r]
    if caps:
        secoes += ["## Capturas", " ".join(f"![[{r}|240]]" for r in caps), ""]
    co = ix.mesmas_telas(nome)
    if co:
        secoes += ["## Vistos nas mesmas telas",
                   " · ".join(link(n["nome"]) for n in co), ""]
    return topo, secoes


def gerar(g: dict, vault: Path, midias: dict[str, tuple[Path, str, dict | None]],
          ao_gravar=None) -> tuple[dict[str, list[str]], dict[str, list[str]], set[str]]:
    """Escreve o canvas do mundo e as miniaturas no vault. Devolve (linhas abaixo do título de cada nota, seções a incluir em
    cada nota, arquivos gerados relativos ao vault)."""
    vault = Path(vault)
    mini = Miniaturas(vault, midias)
    if canvas_partida(g, mini).salvar(vault / CANVAS_PARTIDA) and ao_gravar:
        ao_gravar(vault / CANVAS_PARTIDA)
    ix = _Indice(g)
    anexos: dict[str, list[str]] = {}
    secoes: dict[str, list[str]] = {}
    for n in g["nos"]:
        if n["tipo"] in TIPOS_CONTEXTO:
            anexos[n["nome"]], secoes[n["nome"]] = contexto_nota(ix, n["nome"], mini)
    return anexos, secoes, {CANVAS_PARTIDA} | mini.geradas
