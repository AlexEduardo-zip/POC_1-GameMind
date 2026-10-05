"""Funde anotações (gabarito ou previsões) em um grafo único, com nomes canônicos, fontes e ordem de aparição.
Uso: python src/grafo.py --gab data/gabarito --saida grafo.json"""
import argparse
import json
import unicodedata
from pathlib import Path

from pydantic import BaseModel, Field

from schema import SIMETRICOS, Anotacao


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return " ".join(s.lower().split())


class Fonte(BaseModel):
    arquivo: str
    evidencia: str = ""


class No(BaseModel):
    nome: str
    tipo: str
    subtipo: str = ""
    estado: str = ""
    aliases: list[str] = Field(default_factory=list)
    descricao: str = ""
    primeira_vez: str = ""   # arquivo em que apareceu primeiro (ordem do jogo)
    fontes: list[Fonte] = Field(default_factory=list)


class Aresta(BaseModel):
    sujeito: str
    predicado: str
    objeto: str
    rotulo: str = ""
    fontes: list[Fonte] = Field(default_factory=list)


class Grafo(BaseModel):
    nos: list[No] = Field(default_factory=list)
    arestas: list[Aresta] = Field(default_factory=list)


def carregar_anotacoes(pasta: Path) -> list[Anotacao]:
    arqs = sorted(p for p in pasta.glob("*.json") if p.name != "entidades.json")
    return [Anotacao(**json.loads(p.read_text(encoding="utf-8"))) for p in arqs]


def fundir(anotacoes: list[Anotacao], canonicos: dict) -> Grafo:
    """A ordem da lista é a ordem do tempo de jogo (nomes de arquivo em ordem crescente)."""
    alias = {}
    for c, v in canonicos.items():
        alias[norm(c)] = c
        for a in v.get("aliases", []):
            alias[norm(a)] = c
    canon = lambda n: alias.get(norm(n), n)  # noqa: E731

    nos: dict[str, No] = {}
    arestas: dict[tuple, Aresta] = {}
    for ann in anotacoes:
        for e in ann.entidades:
            nome = canon(e.nome)
            no = nos.setdefault(nome, No(nome=nome, tipo=e.tipo, aliases=canonicos.get(nome, {}).get("aliases", []),
                                         primeira_vez=ann.arquivo))
            no.fontes.append(Fonte(arquivo=ann.arquivo, evidencia=e.evidencia))
            no.subtipo = no.subtipo or e.subtipo
            no.estado = e.estado or no.estado            # o estado mais recente vence
        for r in ann.relacoes:
            s, o = canon(r.sujeito), canon(r.objeto)
            if r.predicado in SIMETRICOS:
                s, o = sorted((s, o))
            a = arestas.setdefault((s, r.predicado, o), Aresta(sujeito=s, predicado=r.predicado, objeto=o))
            a.rotulo = a.rotulo or r.rotulo
            a.fontes.append(Fonte(arquivo=ann.arquivo, evidencia=r.evidencia))
    return Grafo(nos=list(nos.values()), arestas=list(arestas.values()))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--gab", default="data/gabarito")
    ap.add_argument("--saida", default="grafo.json")
    a = ap.parse_args()
    pasta = Path(a.gab)
    canonicos = json.loads((pasta / "entidades.json").read_text(encoding="utf-8"))
    g = fundir(carregar_anotacoes(pasta), canonicos)
    Path(a.saida).write_text(g.model_dump_json(indent=2), encoding="utf-8")
    print(f"{len(g.nos)} nós e {len(g.arestas)} arestas em {a.saida}")
