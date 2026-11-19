"""Revisão de cada entidade pela IA, com o texto lido de todas as capturas dela: uma frase de resumo, o tipo certo (ou "não é
entidade": palavra comum, papel genérico, rótulo da interface, lixo do OCR) e, se for outra grafia de um nome parecido do
grafo, qual. Olhar uma captura por vez não basta para isso; aqui a IA vê o que o jogo inteiro diz sobre a entidade.
Opcional: só com uma IA que responde perguntas livres (`Backend.perguntar`, o Ollama local ou o Claude Code). Vai em lotes (LOTE entidades
por chamada) e fica guardada em `resumos.json` com uma chave do que foi perguntado: só é refeita quando aparece texto novo.
Travas: só descarta entidade vista em poucas capturas, só junta com um nome que estava na lista de parecidos enviada, e nunca
mexe num nome do dicionário manual."""
import hashlib
import json
import logging
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Callable

from extracao.gazetteer import norm
from extracao.llm import TIPOS

log = logging.getLogger("gamemind")
ARQUIVO = "resumos.json"
VERSAO = 2                # suba quando as instruções mudarem: as revisões guardadas são refeitas
LOTE = 6                  # entidades por chamada à IA
MAX_TEXTO = 900           # caracteres de texto lido por entidade
MAX_RESUMO = 240
NENHUM = "nenhum"         # tipo que a IA dá ao que não é entidade
DESCARTE_ATE = 2          # só descarta o que foi visto em até isto de capturas (o que aparece muito, o jogo afirma)
PARECIDO = 0.75           # nomes com grafia a pelo menos isto de semelhança vão como candidatos a "mesmo que"
MAX_PARECIDOS = 3
INSTRUCOES = (
    "Você revisa entidades que um programa extraiu, por OCR, das capturas de tela de um jogo. Para cada entidade você recebe o "
    "nome, o tipo atual, nomes parecidos de outras entidades e as linhas de texto lidas (com erros de OCR) que a citam.\n"
    "Para cada entidade, responda:\n"
    f"- tipo: o tipo certo pelo texto ({', '.join(TIPOS)}), ou \"{NENHUM}\" se não é uma entidade do jogo: palavra comum, "
    "profissão ou papel genérico sem nome próprio (ex.: \"ferreiro\", \"soldado\"), adjetivo de origem, rótulo da interface, "
    "lixo do OCR ou o título do próprio jogo;\n"
    "- mesmo_que: se o nome é outra grafia (erro de leitura, forma curta ou longa) de um dos nomes parecidos listados, esse nome "
    "exatamente como listado; senão, vazio;\n"
    "- resumo: uma frase, em português, de no máximo 200 caracteres, com o que o texto diz da entidade (quem ou o que é, onde, "
    "com quem se relaciona). Se o texto não diz nada além de citar o nome, deixe vazio: não escreva frases como \"X é "
    "mencionado\" ou \"nome de um item\".\n"
    "Use só o texto dado; não use conhecimento de fora e não invente. Responda todas as entidades, com o nome como recebido.")
ESQUEMA = {"type": "object", "properties": {"entidades": {"type": "array", "items": {"type": "object", "properties": {
    "nome": {"type": "string"}, "tipo": {"type": "string", "enum": [*TIPOS, NENHUM]}, "mesmo_que": {"type": "string"},
    "resumo": {"type": "string"}}, "required": ["nome", "tipo", "mesmo_que", "resumo"]}}}, "required": ["entidades"]}
NOME_PROPRIO = re.compile(r"(?<=[^.!?\s]\s)([A-ZÀ-Ý][a-zà-ÿ]{3,})")


def carregar(pasta: Path) -> dict[str, dict]:
    try:
        return json.loads((Path(pasta) / ARQUIVO).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def trechos(no: dict, leituras: dict[str, dict], maximo: int = MAX_TEXTO) -> str:
    """Linhas lidas nas capturas da entidade que citam o nome (ou um apelido), palavra inteira, sem repetição, até `maximo`."""
    chaves = [norm(x) for x in [no["nome"], *no.get("aliases", [])] if len(norm(x)) >= 3]
    cita = re.compile(r"\b(?:" + "|".join(re.escape(c) for c in chaves) + r")\b") if chaves else None
    vistas, saida, total = set(), [], 0
    for arq in dict.fromkeys(f["arquivo"] for f in no.get("fontes", [])):
        for q in (leituras.get(arq) or {}).get("quadros", []):
            for txt in q.get("secoes", {}).values():
                for l in txt.splitlines():
                    k = norm(l)
                    if k in vistas or not cita or not cita.search(k):
                        continue
                    vistas.add(k)
                    saida.append(l.strip())
                    total += len(l)
                    if total >= maximo:
                        return "\n".join(saida)
    return "\n".join(saida)


def parecidos(no: dict, nos: list[dict]) -> list[str]:
    """Nomes de outras entidades (de qualquer tipo) que podem ser outra grafia deste: grafia parecida, ou um contido no outro."""
    k = norm(no["nome"]).replace(" ", "")
    pontos = []
    for o in nos:
        ko = norm(o["nome"]).replace(" ", "")
        if o is no or not ko or not k:
            continue
        r = SequenceMatcher(None, k, ko).ratio()
        if r >= PARECIDO or (min(len(k), len(ko)) >= 4 and (k in ko or ko in k)):
            pontos.append((r, o["nome"]))
    return [n for _, n in sorted(pontos, reverse=True)[:MAX_PARECIDOS]]


def aterrado(resumo: str, texto: str) -> bool:
    """O resumo só cita nomes próprios que estão no texto lido (fora do começo de frase): nome inventado descarta o resumo."""
    t = norm(texto)
    return all(norm(n) in t for n in NOME_PROPRIO.findall(resumo))


def _capturas(no: dict) -> int:
    return len({f["arquivo"] for f in no.get("fontes", [])})


def revisar(grafo: dict, leituras: dict[str, dict], backend, pasta: Path,
            ao_progredir: Callable[[int, int, str], None] = lambda i, n, nome: None, cancelado: Callable[[], bool] = lambda: False) -> int:
    """Revisa as entidades do grafo (ainda não revisado) cujo pedido mudou desde a última revisão. Devolve quantas chamadas fez."""
    cache = carregar(pasta)
    pendentes = []
    for no in sorted(grafo["nos"], key=lambda n: -_capturas(n)):   # as mais vistas primeiro
        par = parecidos(no, grafo["nos"])
        texto = trechos(no, leituras)
        chave = hashlib.sha1(json.dumps([VERSAO, backend.nome, no["nome"], no["tipo"], texto, par], ensure_ascii=False).encode()).hexdigest()[:16]
        if cache.get(no["nome"], {}).get("chave") != chave:
            pendentes.append((no, par, texto, chave))
    chamadas = 0
    for i in range(0, len(pendentes), LOTE):
        if cancelado():
            break
        lote = pendentes[i:i + LOTE]
        ao_progredir(i, len(pendentes), ", ".join(no["nome"] for no, *_ in lote))
        pedido = "\n\n".join(f"### {no['nome']}\ntipo atual: {no['tipo']}\nparecidos: {'; '.join(par) or 'nenhum'}\n"
                             f"texto lido:\n{texto or '(só o nome)'}" for no, par, texto, _ in lote)
        try:
            resp = backend.perguntar(INSTRUCOES, pedido, ESQUEMA)
        except NotImplementedError:
            log.info("a IA %s não responde perguntas livres; as entidades ficam sem revisão e o quadro usa o resumo do GameMind", backend.nome)
            break
        except (OSError, ValueError) as e:
            log.warning("revisão das entidades parou (o restante fica para a próxima rodada): %s", e)
            break
        chamadas += 1
        lista = [r for r in resp.get("entidades", []) if isinstance(r, dict)]
        pelo_nome = {norm(r.get("nome", "")): r for r in lista}
        for k, (no, par, texto, chave) in enumerate(lote):
            r = pelo_nome.get(norm(no["nome"])) or (lista[k] if k < len(lista) else {})   # pelo nome; senão, pela posição
            resumo = " ".join(str(r.get("resumo", "")).split())[:MAX_RESUMO]
            if resumo and not aterrado(resumo, texto):
                resumo = ""   # citou nome que não está no texto lido
            tipo = r.get("tipo") if r.get("tipo") in (*TIPOS, NENHUM) else no["tipo"]
            mesmo = r.get("mesmo_que") if r.get("mesmo_que") in par else ""   # só um nome que estava na lista enviada
            cache[no["nome"]] = {"chave": chave, "tipo_atual": no["tipo"], "tipo": tipo, "mesmo_que": mesmo, "resumo": resumo}
    if chamadas:
        (Path(pasta) / ARQUIVO).write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
        log.info("IA: %d entidade(s) revisada(s) em %d chamada(s)", min(len(pendentes), chamadas * LOTE), chamadas)
    return chamadas


def aplicar(grafo: dict, cache: dict[str, dict], manuais: set[str] = frozenset()) -> dict:
    """Aplica as revisões guardadas ao grafo (no lugar) e o devolve: resumo vira a descrição; "mesmo que" junta os nós; "não é
    entidade" tira o nó (só se visto em até DESCARTE_ATE capturas); tipo novo troca o tipo. Uma revisão feita para outro tipo
    (o grafo mudou desde então) não vale."""
    por_nome = {n["nome"]: n for n in grafo["nos"]}
    validas = {nome: r for nome, r in cache.items() if nome in por_nome and r.get("tipo_atual") == por_nome[nome]["tipo"]}
    # "mesmo que": o nome mais visto fica e absorve a variante, que precisa ser rara (a IA não junta dois nomes que o jogo
    # mostra bem, cada um em várias capturas; e a resposta pode vir nos dois sentidos, "A é B" e "B é A")
    renomear: dict[str, str] = {}
    for nome, r in validas.items():
        alvo = r.get("mesmo_que")
        if not alvo or alvo not in por_nome or alvo == nome or {nome, alvo} & set(manuais) or {nome, alvo} & set(renomear):
            continue
        fica, sai = sorted((nome, alvo), key=lambda n: (-_capturas(por_nome[n]), -len(n)))
        if _capturas(por_nome[sai]) > DESCARTE_ATE:
            continue
        destino, no = por_nome[fica], por_nome[sai]
        vistos = {f["arquivo"] for f in destino["fontes"]}
        destino["fontes"] += [f for f in no["fontes"] if f["arquivo"] not in vistos]
        destino["aliases"] = list(dict.fromkeys([*destino.get("aliases", []), sai, *no.get("aliases", [])]))
        renomear[sai] = fica
    fora: set[str] = set()
    for nome, r in validas.items():
        no = por_nome[nome]
        if r.get("resumo") and not no.get("descricao"):
            no["descricao"] = r["resumo"]
        if nome in manuais or nome in renomear:
            continue
        if r.get("tipo") == NENHUM and _capturas(no) <= DESCARTE_ATE:
            fora.add(nome)
        elif r.get("tipo") in TIPOS and r["tipo"] != no["tipo"]:
            no["tipo"] = r["tipo"]
    grafo["nos"] = [n for n in grafo["nos"] if n["nome"] not in renomear and n["nome"] not in fora]
    arestas: dict[tuple, dict] = {}
    for a in grafo["arestas"]:
        s, o = renomear.get(a["sujeito"], a["sujeito"]), renomear.get(a["objeto"], a["objeto"])
        if s == o or s in fora or o in fora:
            continue
        chave = (s, a["predicado"], o)
        if chave in arestas:
            arestas[chave]["fontes"] += a.get("fontes", [])
        else:
            arestas[chave] = {**a, "sujeito": s, "objeto": o}
    grafo["arestas"] = list(arestas.values())
    if renomear or fora:
        log.info("revisão: %d nome(s) juntado(s) a outro, %d descartado(s)", len(renomear), len(fora))
    return grafo


__all__ = ["ARQUIVO", "carregar", "trechos", "parecidos", "aterrado", "revisar", "aplicar"]
