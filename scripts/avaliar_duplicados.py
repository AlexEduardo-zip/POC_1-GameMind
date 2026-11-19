"""Confere se o grafo junta as formas diferentes do mesmo nome (ex.: "Yennefer" e "Yennefer de Vengerberg") num nó só.
Processa data/raw/escopo_reduzido (15 capturas) num diretório isolado (não toca nos seus jogos nem na sua configuração), com a IA
pedida, e compara o grafo final com data/gabarito_duplicados/grafo_esperado.json:
  mesmo_no       as formas listadas que aparecem no grafo têm de cair no mesmo nó (nome ou apelido)
  nos_distintos  os nomes listados têm de ficar em nós diferentes
  relacoes       a relação tem de existir entre os nós que contêm sujeito e objeto
Uso: python scripts/avaliar_duplicados.py [--ia ollama:qwen2.5:7b] [--manter]
Se a pasta data/raw/escopo_reduzido não existir, ela é montada a partir de data/raw/all com a lista do gabarito.
Sai com código 1 se alguma verificação falhar."""
import argparse
import json
import os
import shutil
import sys
import tempfile
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
GABARITO = RAIZ / "data" / "gabarito_duplicados" / "grafo_esperado.json"
PASTA = RAIZ / "data" / "raw" / "escopo_reduzido"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return " ".join(s.lower().replace(".", " ").split())


def conferir(grafo: dict, esperado: dict) -> list[tuple[bool | None, str]]:
    """Lista de (passou, descrição); passou None = inconclusivo (a forma não apareceu no grafo)."""
    no_de: dict[str, str] = {}
    for n in grafo["nos"]:
        for forma in [n["nome"], *n.get("aliases", [])]:
            no_de[norm(forma)] = n["nome"]
    res = []
    for g in esperado["mesmo_no"]:
        achados = {f: no_de.get(norm(f)) for f in g["nomes"]}
        nos = {v for v in achados.values() if v}
        if len(nos) > 1:
            res.append((False, f"mesmo nó: {g['nomes']} ficaram separados em {sorted(nos)}"))
        elif sum(1 for v in achados.values() if v) < 2:
            res.append((None, f"mesmo nó: {g['nomes']}: só {[f for f, v in achados.items() if v]} apareceu"))
        else:
            res.append((True, f"mesmo nó: {g['nomes']} -> {nos.pop()!r}"))
    for g in esperado["nos_distintos"]:
        nos = [no_de.get(norm(f)) for f in g["nomes"]]
        if None in nos:
            res.append((None, f"nós distintos: {g['nomes']}: algum não apareceu"))
        else:
            res.append((len(set(nos)) == len(nos), f"nós distintos: {g['nomes']} -> {nos}"))
    for r in esperado["relacoes"]:
        s, o = no_de.get(norm(r["sujeito"])), no_de.get(norm(r["objeto"]))
        ok = any(a["predicado"] == r["predicado"] and {a["sujeito"], a["objeto"]} == {s, o} for a in grafo["arestas"])
        res.append((ok, f"relação: {r['sujeito']} {r['predicado']} {r['objeto']} (nós {s!r} e {o!r})"))
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ia", default="ollama:qwen2.5:7b", help="provedor[:modelo]; 'nenhuma' roda só o OCR")
    ap.add_argument("--manter", action="store_true", help="não apaga o diretório de dados temporário (para abrir o vault)")
    a = ap.parse_args()
    esperado = json.loads(GABARITO.read_text(encoding="utf-8"))
    if not PASTA.is_dir():
        PASTA.mkdir(parents=True)
        for nome in esperado["midias"]:
            shutil.copy2(RAIZ / "data" / "raw" / "all" / nome, PASTA / nome)

    dados = Path(tempfile.mkdtemp(prefix="gamemind_dup_"))
    os.environ["GAMEMIND_DADOS"] = str(dados)   # antes de importar o núcleo: nada do usuário é lido ou gravado
    sys.path[:0] = [str(RAIZ / "src")]
    from gamemind.nucleo.config import Config
    from gamemind.nucleo.pipeline import Pipeline
    from gamemind.nucleo.repositorio import Jogo

    jogo = Jogo(dados / "duplicados")
    try:
        ia = "" if a.ia == "nenhuma" else a.ia
        rel = Pipeline(jogo, Config(ia=ia, aprender_regioes=False)).processar(PASTA)
        print(f"{rel.lidas} capturas lidas, {rel.chamadas_llm} chamadas à IA, {rel.nos} nós, {rel.arestas} relações"
              + (f"; erro da IA: {rel.erro_llm}" if rel.erro_llm else ""))
        grafo = json.loads(jogo.caminho_grafo.read_text(encoding="utf-8"))
    finally:
        jogo.fechar()
    resultado = conferir(grafo, esperado)
    for ok, txt in resultado:
        print({True: "OK  ", False: "FALHA", None: "?   "}[ok], txt)
    falhas = sum(1 for ok, _ in resultado if ok is False)
    print(f"\n{sum(1 for ok, _ in resultado if ok)} ok, {falhas} falha(s), {sum(1 for ok, _ in resultado if ok is None)} inconclusiva(s)")
    if a.manter:
        print("dados em", dados)
    else:
        shutil.rmtree(dados, ignore_errors=True)
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
