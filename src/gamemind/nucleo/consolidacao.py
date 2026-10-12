"""Consolidação do jogo inteiro (barata, refeita sempre que entra mídia nova ou muda a IA).
A base de cada mídia são os nomes do dicionário aprendido (dicionario.py) que aparecem no texto lido; o LLM, quando ligado, soma o que
o dicionário não alcança (criaturas, itens, missões, relações), depois da validação de `extracao.llm.normalizar`. A saída é uma
anotação (schema.py) por mídia. Nada aqui é específico de um jogo."""
from difflib import SequenceMatcher

from extracao.gazetteer import Gazetteer, norm
from extracao.llm import normalizar

from .repositorio import Midia


def _texto(q: dict) -> str:
    return "\n".join(q["secoes"].values())


def _anotar_imagem(q: dict, gaz: Gazetteer) -> dict:
    ents = [{"nome": c, "tipo": gaz.tipo[c], "evidencia": f"OCR: '{t}'"} for c, t in gaz.buscar(_texto(q)).items()]
    return {"entidades": ents, "relacoes": []}


def _anotar_clipe(qs: list[dict], gaz: Gazetteer) -> dict:
    votos: dict[str, int] = {}
    for q in qs:
        for nome in gaz.buscar(_texto(q)):   # o dicionário vale para o jogo todo, mesmo para o que foi lido antes dele
            votos[nome] = votos.get(nome, 0) + 1
    return {"entidades": [{"nome": n, "tipo": gaz.tipo[n], "evidencia": f"OCR em {v} quadro(s)"} for n, v in votos.items()], "relacoes": []}


def consolidar_base(leituras: list[tuple[Midia, dict]], gaz: Gazetteer) -> dict[int, dict]:
    """Anotação de cada mídia sem LLM: os nomes do dicionário que aparecem no texto."""
    saida = {}
    for m, l in leituras:
        an = _anotar_imagem(l["quadros"][0], gaz) if l["tipo"] == "imagem" else _anotar_clipe(l["quadros"], gaz)
        saida[m.id] = {"arquivo": m.nome, "tipo_tela": "outro", **an, "observacoes": ""}
    return saida


def entrada_llm(leitura: dict, anotacao: dict) -> tuple[dict[str, str], list[str]]:
    """Texto por região e nomes já detectados que vão ao LLM. Clipe: linhas distintas de todos os quadros (até 60 por região)."""
    qs = leitura["quadros"]
    if leitura["tipo"] == "imagem":
        secoes = qs[0]["secoes"]
    else:
        agg: dict[str, list[str]] = {}
        visto: set = set()
        for q in qs:
            for sec, txt in q["secoes"].items():
                for l in txt.splitlines():
                    k = (sec, norm(l))
                    if l.strip() and len(norm(l)) >= 4 and k not in visto:
                        visto.add(k)
                        agg.setdefault(sec, []).append(l.strip())
        secoes = {sec: "\n".join(ls[:60]) for sec, ls in agg.items()}
    return secoes, [f"{e['tipo']}: {e['nome']}" for e in anotacao["entidades"]]


def validar_llm(base: dict[int, dict], leituras: list[tuple[Midia, dict]], respostas: dict[int, dict], gaz: Gazetteer) -> dict:
    """Resposta do LLM de cada mídia depois da validação (`normalizar`): entidades com lastro no texto e relações permitidas."""
    lidos = {m.id: l for m, l in leituras}
    res = {}
    for mid, saida in respostas.items():
        secoes, _ = entrada_llm(lidos[mid], base[mid])
        base_ents = [(e["nome"], e["tipo"]) for e in base[mid]["entidades"]]
        res[mid] = normalizar(saida, gaz, base_ents, "\n".join(secoes.values()), criaturas_minusculas=True)
    return res


def somar_llm(base: dict[int, dict], leituras: list[tuple[Midia, dict]], respostas: dict[int, dict], gaz: Gazetteer) -> dict[int, dict]:
    """Soma às anotações base o que o LLM achou (entidades novas e relações), depois da validação por `normalizar`."""
    res = validar_llm(base, leituras, respostas, gaz)
    # variações de grafia do mesmo nome novo (ex.: "Arbustira" e "Arbusteira") viram a mais frequente da partida
    conhecidos = {e["nome"] for an in base.values() for e in an["entidades"]} | set(gaz.tipo)
    novos: dict[str, int] = {}
    for r in res.values():
        for e in r.entidades:
            if e["nome"] not in conhecidos:
                novos[e["nome"]] = novos.get(e["nome"], 0) + 1
    canon: dict[str, str] = {}
    for n in sorted(novos, key=lambda x: (-novos[x], -len(x))):
        if n in canon:
            continue
        canon[n] = n
        for m in novos:
            if m not in canon and len(m) >= 6 and SequenceMatcher(None, norm(n), norm(m)).ratio() >= 0.85:
                canon[m] = n
    saida = {mid: {**an, "entidades": list(an["entidades"]), "relacoes": list(an["relacoes"])} for mid, an in base.items()}
    for mid, r in res.items():
        an = saida[mid]
        ja = {e["nome"] for e in an["entidades"]}
        for e in r.entidades:
            nome = canon.get(e["nome"], e["nome"])
            if nome not in ja:
                ja.add(nome)
                an["entidades"].append({"nome": nome, "tipo": e["tipo"], "evidencia": "LLM"})
        ja_r = {(x["sujeito"], x["predicado"], x["objeto"]) for x in an["relacoes"]}
        for x in r.relacoes:
            t = (canon.get(x["sujeito"], x["sujeito"]), x["predicado"], canon.get(x["objeto"], x["objeto"]))
            if t not in ja_r:
                ja_r.add(t)
                an["relacoes"].append({"sujeito": t[0], "predicado": t[1], "objeto": t[2], "evidencia": "LLM"})
    return saida
