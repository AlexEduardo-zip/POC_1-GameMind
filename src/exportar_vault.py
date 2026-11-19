"""Protótipo do exportador: grafo consolidado (JSON de src/grafo.py) -> vault Markdown do Obsidian.
Uso: python src/exportar_vault.py --grafo grafo.json --saida vault_output  (ou `exportar(grafo, pasta)` no código)"""
import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

PASTAS = {"personagem": "Personagens", "criatura": "Criaturas", "local": "Locais", "missao": "Missoes",
          "item": "Itens", "evento": "Eventos", "decisao": "Decisoes", "faccao": "Faccoes"}


def arquivo(nome):
    return re.sub(r'[\\/:*?"<>|#^\[\]]', "", nome).strip()


def link(nome):
    return f"[[{arquivo(nome)}]]"


def gravar_se_mudou(caminho: Path, texto: str) -> bool:
    """Grava `texto` em `caminho` só se o conteúdo mudou (o vault é regravado várias vezes ao longo de uma rodada).
    Devolve True se gravou."""
    try:
        if caminho.read_text(encoding="utf-8") == texto:
            return False
    except (OSError, UnicodeDecodeError):
        pass
    caminho.write_text(texto, encoding="utf-8")
    return True


def exportar(g: dict, saida: Path, anexos: dict[str, list[str]] | None = None, ao_gravar=None,
             secoes: dict[str, list[str]] | None = None) -> int:
    """Escreve uma nota por nó do grafo (dict no formato de src/grafo.py) em `saida`. Devolve o número de notas.
    `anexos`: linhas de Markdown acrescentadas logo abaixo do título de cada nota (ex.: link para o canvas do mundo).
    `secoes`: linhas de Markdown acrescentadas depois das relações e antes das fontes (ex.: capturas, vistos junto).
    `ao_gravar(caminho)`, se dado, é chamado a cada nota criada ou alterada (notas idênticas não são regravadas)."""
    anexos, secoes = anexos or {}, secoes or {}
    saida = Path(saida)
    saintes, entrantes = defaultdict(list), defaultdict(list)
    for r in g["arestas"]:
        saintes[r["sujeito"]].append(r)
        entrantes[r["objeto"]].append(r)

    for e in g["nos"]:
        pasta = saida / PASTAS[e["tipo"]]
        pasta.mkdir(parents=True, exist_ok=True)
        fm = ["---", f"tipo: {e['tipo']}", f"tags: [{e['tipo']}]"]
        if e.get("subtipo"):
            fm.append(f"subtipo: {e['subtipo']}")
        if e.get("aliases"):
            fm.append("aliases: [" + ", ".join(e["aliases"]) + "]")
        if e.get("estado"):
            fm.append(f"estado: {e['estado']}")
        if e.get("primeira_vez"):
            fm.append(f"primeira_vez: {e['primeira_vez']}")
        fm.append("---")
        linhas = (fm + [f"# {e['nome']}", ""] + ([*anexos[e["nome"]], ""] if anexos.get(e["nome"]) else [])
                  + ([e["descricao"], ""] if e.get("descricao") else []))
        if saintes[e["nome"]]:
            linhas.append("## Relações")
            agrupadas = defaultdict(list)
            for r in saintes[e["nome"]]:
                alvo = link(r["objeto"]) + (f" ({r['rotulo']})" if r.get("rotulo") else "")
                agrupadas[r["predicado"]].append(alvo)
            for pred, alvos in agrupadas.items():
                linhas.append(f"- {pred}: " + ", ".join(alvos))
            linhas.append("")
        if entrantes[e["nome"]]:
            linhas.append("## Relações recebidas")
            for r in entrantes[e["nome"]]:
                linhas.append(f"- {link(r['sujeito'])} {r['predicado']} este")
            linhas.append("")
        linhas += secoes.get(e["nome"], [])
        if e.get("fontes"):
            linhas.append("## Fontes")
            for f in e["fontes"]:
                linhas.append(f"- {f['arquivo']}" + (f": {f['evidencia']}" if f.get("evidencia") else ""))
            linhas.append("")
        if gravar_se_mudou(pasta / f"{arquivo(e['nome'])}.md", "\n".join(linhas)) and ao_gravar:
            ao_gravar(pasta / f"{arquivo(e['nome'])}.md")
    return len(g["nos"])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--grafo", required=True)
    ap.add_argument("--saida", required=True)
    a = ap.parse_args()
    n = exportar(json.loads(Path(a.grafo).read_text(encoding="utf-8")), Path(a.saida))
    print(f"{n} notas geradas em {a.saida}")
