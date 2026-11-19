"""Dicionário de nomes aprendido a partir do que o jogador capturou: ninguém precisa escrever uma lista antes.
Lê o texto de todas as mídias do jogo e descobre nomes próprios (personagens, locais, facções) por indícios do próprio texto:
quem aparece antes de dois-pontos numa legenda, nomes que se repetem em várias capturas e o contexto em que aparecem
("para X", "tropas de X", "Fale com X"). Só usa convenções gerais do português; nenhum texto de interface de um jogo. A lista fica em `dicionario.json` na pasta do jogo e é
refeita a cada rodada; um `dicionario_manual.json` opcional, se existir, é somado a ela (o usuário nunca precisa criá-lo).

Uma palavra é nome próprio se aparece com inicial maiúscula e nunca em minúsculas no resto do texto lido (o que descarta
"Isso", "Tudo", "Seguindo"). O tipo vem dos votos dos indícios; sem voto suficiente o nome não entra, porque um nome sem
tipo seria chute. Criaturas e itens aparecem em minúsculas no texto, então vêm das regras de tela e do LLM, não daqui."""
import json
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

from extracao.gazetteer import Gazetteer, norm

CAP = r"[A-ZÀ-ÖØ-Ý][a-zà-öø-ÿ'’\-]{2,}"
CONECT = r"(?:de|da|do|das|dos|von|van)"
NOME = re.compile(rf"(?<![A-Za-zÀ-ÿ'’\-])({CAP}(?:\s+(?:{CONECT}\s+)?{CAP})*)")
FALANTE = re.compile(rf"^\W{{0,3}}(?:[A-Za-z]{{1,2}}\W+)?({CAP}(?:\s+(?:{CONECT}\s+)?{CAP})*)\s*:\s*\S")
# palavras de função do português: nunca começam um nome sozinhas
FUNCAO = set("""o a os as um uma uns umas de da do das dos em na no nas nos por para pra com sem sob sobre ate ao aos aquele aquela
que quem qual quais como quando onde porque mas se ou e nem ja ainda tambem so apenas mais menos muito pouco tudo nada isso isto
aquilo ele ela eles elas eu tu voce nos vos meu minha seu sua nosso nossa esse essa este esta foi era ser estar tem ter ha""".split())
LOCAL_PREP = re.compile(r"\b(?:em|na|no|nas|nos|para|até|ate|ao|à|pela|pelo)\s+$", re.I)
PESSOA_CUE = re.compile(r"\b(?:com|siga|fale com|fale|ajude|procure|encontre|pergunte ao?|diga ao?|convença|mate|salve|guie)\s+(?:o|a|os|as)?\s*$", re.I)
FACCAO_CUE = re.compile(r"\b(?:povo|tropas?|exército|soldados?|forças|império|comandante|guardas?)\s+(?:de|do|da|dos|das)\s+$", re.I)
# palavras comuns do português que costumam abrir o nome de um grupo ou de um lugar (nenhuma vem de um jogo específico)
FACCAO_CABECA = {"escola", "exercito", "ordem", "cavaleiros", "imperio", "guilda", "irmandade", "legiao", "companhia", "bando"}
LOCAL_CABECA = {"vila", "cidade", "taverna", "castelo", "fortaleza", "ponte", "floresta", "rio", "montanhas", "montanha", "porto", "forte", "reino",
                "reinos", "torre", "ilha", "ilhas", "vale", "estalagem", "mercado", "templo", "caverna", "cemiterio", "pantano", "aldeia"}
MINIMO_DOCS = 2          # um nome sem indício forte precisa aparecer em duas mídias
FORTE = 3                # voto de indício forte (falante de legenda)


def _linhas(quadros: list[dict]) -> list[tuple[str, str]]:
    """(seção, linha) distintas de todos os quadros de uma mídia."""
    vistas, saida = set(), []
    for q in quadros:
        for sec, txt in q["secoes"].items():
            for l in txt.splitlines():
                k = (sec, norm(l))
                if len(k[1]) >= 4 and k not in vistas:
                    vistas.add(k)
                    saida.append((sec, l.strip()))
    return saida


def _ruido(l: str) -> bool:
    letras = sum(c.isalpha() for c in l)
    return letras < 4 or letras / max(len(l), 1) < 0.6


def _caso(nome: str) -> str:
    return " ".join(t.lower() if t.lower() in {"de", "da", "do", "das", "dos"} else t[:1].upper() + t[1:].lower() for t in nome.split())


def _grupo(nomes: list[str], limiar: float = 0.85) -> dict[str, str]:
    """Variações de leitura do mesmo nome ("Ravena", "Ravenna") -> a grafia mais frequente."""
    cont = Counter(nomes)
    canon: dict[str, str] = {}
    for n in sorted(cont, key=lambda x: (-cont[x], -len(x))):
        for c in set(canon.values()):
            if len(n) >= 5 and SequenceMatcher(None, norm(n), norm(c)).ratio() >= limiar:
                canon[n] = c
                break
        else:
            canon[n] = n
    return canon


def aprender(midias: list[list[dict]], ignorar: frozenset = frozenset()) -> dict[str, dict]:
    """`midias`: para cada mídia, a lista de quadros lidos (cada um com `secoes`). Devolve {nome: {tipo, aliases, midias, votos}}."""
    por_midia = [_linhas(qs) for qs in midias]
    # vocabulário comum: palavras que aparecem em minúsculas em algum ponto do texto lido
    comum: set[str] = set(FUNCAO)
    for linhas in por_midia:
        for _, l in linhas:
            for t in re.findall(r"(?<![A-Za-zÀ-ÿ])[a-zà-ÿ]{3,}", l):
                comum.add(norm(t))

    docs: dict[str, set[int]] = defaultdict(set)
    votos: dict[str, Counter] = defaultdict(Counter)
    surf: list[str] = []

    def valido(nome: str, inicio: bool) -> bool:
        toks = nome.split()
        cabeca = [t for t in toks if t.lower() not in {"de", "da", "do", "das", "dos", "von", "van"}]
        if norm(nome) in ignorar or any(norm(t) in ignorar for t in cabeca):
            return False
        if len(cabeca) == 1:
            t = norm(cabeca[0])
            return len(t) >= 4 and t not in comum
        return not any(norm(t) in FUNCAO for t in cabeca[:1]) and any(norm(t) not in comum for t in cabeca)

    for i, linhas in enumerate(por_midia):
        anterior: dict[str, str] = {}   # linha anterior de cada seção: o texto quebra de linha no meio da frase
        for sec, l in linhas:
            antes_linha = anterior.get(sec, "")
            anterior[sec] = "" if _ruido(l) else l
            if _ruido(l):
                continue
            m = FALANTE.match(l) if sec in ("legenda", "tela") else None
            if m and valido(m.group(1), True):
                n = m.group(1)
                surf.append(n)
                docs[n].add(i)
                votos[n]["personagem"] += FORTE
            for m in NOME.finditer(l):
                n = m.group(1)
                antes = l[:m.start()]
                if not antes.strip():   # nome no começo da linha: o contexto está no fim da linha anterior
                    antes = antes_linha[-40:] + " "
                inicio = bool(re.search(r"[.!?…:]\s*$", antes)) or not antes.strip()
                if not valido(n, inicio):
                    continue
                surf.append(n)
                docs[n].add(i)
                if LOCAL_PREP.search(antes):
                    votos[n]["local"] += 1
                if PESSOA_CUE.search(antes):
                    votos[n]["personagem"] += 1
                if FACCAO_CUE.search(antes):
                    votos[n]["faccao"] += 2
                cab = norm(n.split()[0])
                if cab in FACCAO_CABECA:
                    votos[n]["faccao"] += 3
                elif cab in LOCAL_CABECA:
                    votos[n]["local"] += 3

    canon = _grupo(surf)
    apelidos: dict[str, list[str]] = defaultdict(list)
    d2: dict[str, set[int]] = defaultdict(set)
    v2: dict[str, Counter] = defaultdict(Counter)
    for n, c in canon.items():
        d2[c] |= docs[n]
        v2[c].update(votos[n])
    for m in sorted(d2, key=len):
        if m not in d2 or " " in m or len(m) < 4:
            continue
        alvos = [n for n in d2 if n != m and len(n) > len(m) and norm(n).split()[0].startswith(norm(m))]
        if alvos:
            n = max(alvos, key=lambda x: (len(d2[x]), len(x)))
            # a forma vista em mais mídias é o nome; a outra vira apelido ("Ravena" e não "Ravena Lis de Altamira")
            nome, outro = (m, n) if len(d2[m]) > len(d2[n]) else (n, m)
            d2[nome] |= d2.pop(outro)
            v2[nome].update(v2.pop(outro))
            apelidos[nome] += apelidos.pop(outro, []) + [outro]
    saida: dict[str, dict] = {}
    for n, ds in d2.items():
        v = v2[n]
        tipo, forca = (v.most_common(1)[0] if v else ("", 0))
        if not tipo or not (forca >= FORTE or (len(ds) >= MINIMO_DOCS and forca >= 2)):
            continue
        saida[n] = {"tipo": tipo, "aliases": sorted(apelidos[n]), "midias": len(ds), "votos": dict(v)}
    return dict(sorted(saida.items(), key=lambda kv: (-kv[1]["midias"], kv[0])))


# tratamentos que vêm antes do nome de uma pessoa ("Mestre Odo", "Capitão Brann"): não fazem parte do nome
TRATAMENTOS = set("""mestre mestra comandante capitao capita senhor senhora sir lorde lady rei rainha principe princesa barao baronesa
conde condessa duque duquesa general sargento tenente dom dona padre madre irmao irma""".split())
CONECTORES = {"de", "da", "do", "das", "dos", "von", "van", "e"}
GRAFIA_PARECIDA = 0.9   # duas grafias com esta semelhança (sem os espaços) são o mesmo nome lido com erro
TIPOS_UNIFICAVEIS = ("personagem", "criatura", "faccao", "local")   # missões, itens e decisões têm nomes longos que se repetem de propósito


def _chave(nome: str, tipo: str) -> tuple[str, ...]:
    toks = norm(nome).replace(".", " ").split()
    if tipo == "personagem":
        while len(toks) > 1 and toks[0] in TRATAMENTOS and toks[1] not in CONECTORES:
            toks = toks[1:]
    return tuple(toks)


def grupos_de_nomes(contagem: dict[tuple[str, str], int], preferidos: set[str] = frozenset()) -> dict[str, str]:
    """Junta as formas do mesmo nome (do mesmo tipo) que o OCR e a IA trazem em capturas diferentes. `contagem`: (nome, tipo) ->
    em quantas mídias aparece. Devolve {forma: nome escolhido} só para as formas que mudam. Juntam-se:
    - o mesmo nome com tratamentos diferentes: "Comandante Brann Holt" e "Capitão Brann Holt";
    - singular e plural de uma palavra: "Grifo" e "Grifos";
    - um nome e a sua forma completa, quando há uma só forma completa: "Ravena" e "Ravena de Altamira", "Guarda" e
      "Guarda Cinzenta" (com "Exército Real" e "Exército do Norte", "Exército" fica sozinho: não dá para saber qual é).
    - palavra genérica de lugar ou grupo mais o nome: "Ilhas Vorna" e "Vorna";
    - a mesma grafia sem os espaços ou com um erro de leitura (GRAFIA_PARECIDA): "Valealto" e "Vale Alto".
    O nome escolhido é o visto em mais mídias (no empate, o mais longo); um nome de `preferidos` (dicionário manual) sempre vence."""
    pai: dict[tuple[str, str], tuple[str, str]] = {}

    def raiz(x):
        while pai[x] != x:
            pai[x] = pai[pai[x]]
            x = pai[x]
        return x

    def unir(a, b):
        pai[raiz(a)] = raiz(b)

    por_tipo: dict[str, list[str]] = defaultdict(list)
    for (nome, tipo) in contagem:
        if tipo in TIPOS_UNIFICAVEIS:
            pai[(nome, tipo)] = (nome, tipo)
            por_tipo[tipo].append(nome)
    for tipo, nomes in por_tipo.items():
        chaves = {n: _chave(n, tipo) for n in nomes}
        por_chave: dict[tuple, list[str]] = defaultdict(list)
        for n, k in chaves.items():
            if k:
                por_chave[k].append(n)
        for iguais in por_chave.values():   # mesma chave: tratamento ou grafia diferente
            for n in iguais[1:]:
                unir((n, tipo), (iguais[0], tipo))
        for k, iguais in por_chave.items():   # plural de uma palavra
            if len(k) == 1 and len(k[0]) >= 4:
                for suf in ("s", "es"):
                    for n in por_chave.get((k[0] + suf,), []):
                        unir((n, tipo), (iguais[0], tipo))
        for n, k in chaves.items():   # forma curta de exatamente uma forma completa
            if not k or len(k[0]) < 4:
                continue
            completas = {raiz((m, tipo)) for m, km in chaves.items() if len(km) > len(k) and km[:len(k)] == k}
            completas.discard(raiz((n, tipo)))
            if len(completas) == 1:
                unir((n, tipo), completas.pop())
        cabecas = FACCAO_CABECA | LOCAL_CABECA
        for n, k in chaves.items():   # palavra genérica + o nome: "Ilhas Vorna" e "Vorna"
            if len(k) >= 2 and k[0] in cabecas:
                resto = k[2:] if len(k) > 2 and k[1] in CONECTORES else k[1:]
                for m in por_chave.get(resto, []):
                    unir((n, tipo), (m, tipo))
        juntas = {n: "".join(k) for n, k in chaves.items() if len("".join(k)) >= 6}
        lista = sorted(juntas)
        for i, n in enumerate(lista):   # o mesmo nome sem os espaços, ou com um erro de leitura: "Valealto", "Vale Aldo"
            for m in lista[i + 1:]:
                if raiz((n, tipo)) != raiz((m, tipo)) and SequenceMatcher(None, juntas[n], juntas[m]).ratio() >= GRAFIA_PARECIDA:
                    unir((n, tipo), (m, tipo))

    grupos: dict[tuple, list[tuple[str, str]]] = defaultdict(list)
    for x in pai:
        grupos[raiz(x)].append(x)
    mapa: dict[str, str] = {}
    for membros in grupos.values():
        if len(membros) < 2:
            continue
        nome, _ = max(membros, key=lambda x: (x[0] in preferidos, contagem[x], len(x[0]), x[0]))
        mapa.update({m: nome for m, _ in membros if m != nome})
    return mapa


def unificar(entidades: dict[str, dict], contagem: dict[tuple[str, str], int], preferidos: set[str] = frozenset()) -> dict[str, dict]:
    """Cópia de `entidades` (formato do dicionário) em que cada forma juntada por `grupos_de_nomes` vira apelido do nome escolhido.
    Nomes de `contagem` que não estão no dicionário só entram se forem o nome escolhido de um grupo."""
    alias = {}
    for c, v in entidades.items():
        for a in [c, *v.get("aliases", [])]:
            alias[norm(a)] = c
    total: Counter = Counter()
    tipo_de: dict[str, str] = {}
    for (nome, tipo), n in contagem.items():
        nome = alias.get(norm(nome), nome)
        tipo = entidades.get(nome, {}).get("tipo", tipo)
        total[(nome, tipo)] += n
        tipo_de.setdefault(nome, tipo)
    mapa = grupos_de_nomes(total, preferidos)
    if not mapa:
        return entidades
    saida = {c: {**v, "aliases": list(v.get("aliases", []))} for c, v in entidades.items()}
    for forma, nome in mapa.items():
        destino = saida.setdefault(nome, {"tipo": tipo_de[nome], "aliases": [], "origem": "unificacao"})
        antigo = saida.pop(forma, {})
        for a in [forma, *antigo.get("aliases", [])]:
            if a != nome and a not in destino["aliases"]:
                destino["aliases"].append(a)
    return saida


def para_gazetteer(entidades: dict[str, dict]) -> Gazetteer:
    return Gazetteer.de_dados({n: {"tipo": v["tipo"], "aliases": v.get("aliases", [])} for n, v in entidades.items()})


def carregar_manual(pasta: Path) -> dict[str, dict]:
    """Nomes que o usuário quiser acrescentar à mão em `dicionario_manual.json` (opcional; mesmo formato do dicionário)."""
    try:
        return json.loads((Path(pasta) / "dicionario_manual.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def salvar(pasta: Path, entidades: dict[str, dict]) -> None:
    (Path(pasta) / "dicionario.json").write_text(json.dumps(entidades, ensure_ascii=False, indent=1), encoding="utf-8")


__all__ = ["aprender", "para_gazetteer", "carregar_manual", "salvar", "grupos_de_nomes", "unificar"]
