"""Extração de entidades e relações com LLM (etapa B3b).
O back-end é plugável: `Backend.extrair()` recebe o texto lido da tela e devolve o JSON do esquema do GameMind.
Padrão: modelo local via Ollama (privacidade e sem custo recorrente). A IA pública entra depois, como outra subclasse.
O resultado passa por `normalizar()`: nomes resolvidos pelo dicionário, tipos e predicados validados pela ontologia."""
import json
import time
import urllib.request
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from .gazetteer import Gazetteer, norm

ONT = json.loads((Path(__file__).resolve().parent.parent / "ontologia.json").read_text(encoding="utf-8"))
TIPOS = list(ONT["tipos"])
PREDICADOS = ONT["predicados"]

ESQUEMA = {
    "type": "object",
    "properties": {
        "entidades": {"type": "array", "items": {"type": "object", "properties": {
            "nome": {"type": "string"}, "tipo": {"type": "string", "enum": TIPOS}, "subtipo": {"type": "string"}},
            "required": ["nome", "tipo"]}},
        "relacoes": {"type": "array", "items": {"type": "object", "properties": {
            "sujeito": {"type": "string"}, "predicado": {"type": "string", "enum": list(PREDICADOS)}, "objeto": {"type": "string"}},
            "required": ["sujeito", "predicado", "objeto"]}},
    },
    "required": ["entidades", "relacoes"],
}


def instrucoes() -> str:
    tipos = "\n".join(f"- {t}: {d}" for t, d in ONT["tipos"].items())
    preds = "\n".join(f"- {p}: {' ou '.join(v['dominio'])} -> {' ou '.join(v['alcance'])}" for p, v in PREDICADOS.items())
    return f"""Você extrai entidades e relações do texto lido (por OCR) de uma tela do jogo The Witcher 3 em português do Brasil.
O texto tem ruído de OCR (letras trocadas, linhas soltas): ignore o que não faz sentido.

TIPOS DE ENTIDADE:
{tipos}

RELAÇÕES (sujeito -> objeto), só estas:
{preds}

REGRAS:
1. Anote só o que está escrito no texto. Não use conhecimento do jogo, não complete nem invente nomes, e não crie entidade que não apareça no texto.
2. Personagem só com nome próprio escrito (legenda "Nome: fala", objetivo, entrada de glossário). Citar o nome já conta.
3. Relação só se uma frase do texto a afirma com clareza; na dúvida, não crie. Sujeito e objeto precisam estar entre as entidades da lista "JÁ DETECTADO" ou entre as que você listou, com a mesma grafia.
   - Aparecer na mesma lista, tela ou entrada NÃO é relação. Por exemplo, a lista de personagens de um glossário não relaciona os personagens entre si.
   - membro_de só se o texto diz que a pessoa pertence ao grupo ("membro da Escola do Lobo").
   - participa_de: personagem que o objetivo ou a frase liga à missão ("Siga o Vesemir" na missão X). ocorre_em: missão ou evento que o texto situa num local. obtido_em: item que o texto dá como recompensa de uma missão.
4. Item: só com nome próprio em destaque (ficha com título em maiúsculas, recompensa ou objetivo). Nunca anote rótulos de espaço de equipamento (Armadura de Peito, Luvas, Botas, Virotes, Bombas, Máscaras), atributos (Vitalidade, Toxicidade, dano), botões, nem a arma equipada.
5. Não anote: categorias do bestiário (Necrófagos, Híbridos), Gwent e cartas, controles e dicas de tutorial, nem grupos de pessoas genéricos ("recrutas", "povo", "bruxos").
6. Em "JÁ DETECTADO" estão as entidades que outras etapas já acharam na tela (tipo: nome). Não as repita; use-as nas relações quando o texto permitir.
Exemplo (texto inventado): "MISSÃO ATUALIZADA! O CAMPO DE FEIRA. Fale com Lena na estalagem de Vale Claro." com JÁ DETECTADO "missao: O Campo de Feira" deve gerar as entidades Lena (personagem), Vale Claro (local), estalagem de Vale Claro (local) e as relações Lena participa_de O Campo de Feira, O Campo de Feira ocorre_em Vale Claro.
Responda só com o JSON pedido."""


def montar_pedido(secoes: dict[str, str], detectado: list[str]) -> str:
    blocos = [f"[{k.upper()}]\n{v.strip()}" for k, v in secoes.items() if v.strip()]
    return "JÁ DETECTADO: " + ("; ".join(detectado) or "nada") + "\n\nTEXTO DA TELA:\n" + "\n\n".join(blocos)


class Backend:
    nome = "base"

    def extrair(self, secoes: dict[str, str], detectado: list[str]) -> tuple[dict, dict]:
        raise NotImplementedError


class OllamaBackend(Backend):
    def __init__(self, modelo: str = "qwen2.5:7b", url: str = "http://localhost:11434", num_ctx: int = 4096):
        self.modelo, self.url, self.num_ctx = modelo, url, num_ctx
        self.nome = f"ollama:{modelo}"

    def extrair(self, secoes, detectado):
        corpo = {"model": self.modelo, "stream": False, "format": ESQUEMA, "keep_alive": "10m",
                 "options": {"temperature": 0, "seed": 0, "num_ctx": self.num_ctx, "num_predict": 700},
                 "messages": [{"role": "system", "content": instrucoes()},
                              {"role": "user", "content": montar_pedido(secoes, detectado)}]}
        req = urllib.request.Request(self.url + "/api/chat", data=json.dumps(corpo).encode(), headers={"Content-Type": "application/json"})
        t0 = time.perf_counter()
        with urllib.request.urlopen(req, timeout=600) as r:
            resp = json.load(r)
        try:
            saida = json.loads(resp["message"]["content"])
        except (KeyError, json.JSONDecodeError):
            saida = {"entidades": [], "relacoes": []}
        meta = {"tempo_s": round(time.perf_counter() - t0, 2), "tokens_entrada": resp.get("prompt_eval_count", 0),
                "tokens_saida": resp.get("eval_count", 0), "tempo_geracao_s": round(resp.get("eval_duration", 0) / 1e9, 2)}
        return saida, meta


@dataclass
class Resultado:
    entidades: list[dict]
    relacoes: list[dict]
    descartes: list[str]


# rótulos da interface que não são itens do jogo (espaços de equipamento, atributos e abas do inventário)
ROTULOS_UI = {"armadura de peito", "luvas", "calcas", "botas", "virotes", "bombas", "viseiras", "mascaras", "utilitarios", "troféu", "trofeu", "sela",
              "alforjes", "viveiras", "vitalidade", "toxicidade", "carpeado", "oleos", "pocoes", "armas", "armadura", "outros", "comestiveis",
              "arma de aco", "arma de prata", "espada de prata", "espada de aco", "sentidos de bruxo", "garrafa d agua", "tocha", "chave"}


def _janelas(texto: str) -> tuple[str, list[str], list[str]]:
    n = norm(texto)
    caixa_alta = [norm(l) for l in texto.splitlines() if sum(c.isalpha() for c in l) >= 4 and
                  sum(c.isupper() for c in l) >= 0.7 * sum(c.isalpha() for c in l)]
    return n, n.split(), caixa_alta


def _presente(nome: str, n: str, palavras: list[str], limiar: float = 0.85) -> bool:
    k = norm(nome)
    if not k:
        return False
    if k in n:
        return True
    if len(k) < 5:
        return False
    w = len(k.split())
    return any(abs(len(j) - len(k)) <= 2 and SequenceMatcher(None, j, k).ratio() >= limiar
               for j in (" ".join(palavras[i:i + w]) for i in range(len(palavras) - w + 1)))


GENERICOS = {"missao", "personagem", "serio", "ela", "ele", "oleo", "herbalista", "cacador", "bruxo", "bruxos", "recrutas", "povo", "demonio",
             "jogador", "heroi", "inimigo", "aliado", "npc", "guarda", "guardas", "soldado", "soldados", "alistamento", "objetivo"}
CUES_MEMBRO = ("membro", "colega", "pertenc", "parte d", "integr", "alistad", "recruta", "escola do", "filiad")


def _maiuscula_inicial(nome: str, texto: str) -> bool:
    """Alguma ocorrência do nome no texto começa com maiúscula (nome próprio, não substantivo comum)."""
    alvo = norm(nome).split()
    palavras = texto.split()
    nm = [norm(w) for w in palavras]
    for i in range(len(palavras) - len(alvo) + 1):
        if all(nm[i + j] == alvo[j] or (len(alvo[j]) >= 5 and SequenceMatcher(None, nm[i + j], alvo[j]).ratio() >= 0.85) for j in range(len(alvo))):
            return palavras[i][:1].isupper()
    return False


def _coocorre(a: str, b: str, linhas: list[str], base: set[str], janela: int = 4) -> tuple[bool, str]:
    """Os dois nomes estão em até `janela` linhas seguidas do texto (nomes já detectados por estrutura contam como presentes)."""
    for i in range(len(linhas)):
        trecho = " ".join(linhas[i:i + janela])
        n, ws = trecho, trecho.split()
        ok_a = norm(a) in base or _presente(a, n, ws)
        ok_b = norm(b) in base or _presente(b, n, ws)
        if ok_a and ok_b and (norm(a) not in base or norm(b) not in base or True):
            return True, trecho
    return False, ""


def normalizar(saida: dict, gaz: Gazetteer, nomes_base: list[tuple[str, str]], texto: str = "") -> Resultado:
    """Resolve nomes pelo dicionário e pelos títulos já detectados (`nomes_base`: lista de (nome, tipo)),
    valida tipos e predicados (domínio e alcance) e descarta o que a ontologia não aceita."""
    alias = {k: c for k, c in gaz.termos.items()}
    tipo_base = {norm(n): (n, t) for n, t in nomes_base}
    descartes: list[str] = []

    def resolve(nome: str, tipo: str) -> tuple[str, str]:
        k = norm(nome)
        if k in alias:
            return alias[k], gaz.tipo[alias[k]]
        if k in tipo_base:
            return tipo_base[k]
        for kb, (nb, tb) in tipo_base.items():  # variação de um título detectado (ex.: sem o artigo)
            if len(k) >= 8 and SequenceMatcher(None, k, kb).ratio() >= 0.85:
                return nb, tb
        return nome.strip(), tipo

    tn, palavras, caixa_alta = _janelas(texto)
    linhas_n = [norm(l) for l in texto.splitlines() if l.strip()]
    base_nomes = {norm(n) for n, _ in nomes_base}

    def aterrada(nome: str, tipo: str) -> bool:
        """O nome precisa estar no texto da tela; item, em linha de título (maiúsculas), e fora dos rótulos de interface."""
        if norm(nome) in base_nomes:
            return True
        if not texto:
            return True
        if tipo == "item":
            if norm(nome) in ROTULOS_UI:
                return False
            return any(_presente(nome, c, c.split()) for c in caixa_alta)
        return _presente(nome, tn, palavras)

    ents: dict[str, str] = {}
    for e in saida.get("entidades", []):
        nome = (e.get("nome") or "").strip()
        if not nome or len(nome.split()) > 8 or e.get("tipo") not in TIPOS:
            descartes.append(f"entidade inválida: {nome!r}")
            continue
        n, t = resolve(nome, e["tipo"])
        if not aterrada(n, t) and not aterrada(nome, t):
            descartes.append(f"sem lastro no texto: {nome!r} ({t})")
            continue
        if norm(n) not in base_nomes and n not in gaz.tipo and texto:
            # nome novo (fora do dicionário e das etapas estruturadas): precisa ser nome próprio, não palavra comum
            if norm(n) in GENERICOS or not n[:1].isupper() or (t != "item" and not _maiuscula_inicial(n, texto)):
                descartes.append(f"nome comum, não próprio: {n!r}")
                continue
        ents.setdefault(n, t)
    rels, vistos = [], set()
    for r in saida.get("relacoes", []):
        s_, o_ = (r.get("sujeito") or "").strip(), (r.get("objeto") or "").strip()
        p = r.get("predicado")
        if p not in PREDICADOS or not s_ or not o_:
            descartes.append(f"relação inválida: {r}")
            continue
        s, ts = resolve(s_, ents.get(s_, ""))
        o, to = resolve(o_, ents.get(o_, ""))
        ts, to = ents.get(s, ts), ents.get(o, to)
        if s == o or ts not in PREDICADOS[p]["dominio"] or to not in PREDICADOS[p]["alcance"]:
            descartes.append(f"fora do domínio ou alcance: {s} {p} {o}")
            continue
        if texto:
            a_, b_ = s.replace(" (missão)", ""), o.replace(" (missão)", "")
            ok, trecho = _coocorre(a_, b_, linhas_n, base_nomes)
            if not ok:
                descartes.append(f"nomes longe um do outro no texto: {s} {p} {o}")
                continue
            if p == "membro_de" and not any(c in trecho for c in CUES_MEMBRO):
                descartes.append(f"membro_de sem indício de pertencimento: {s} {o}")
                continue
        ents.setdefault(s, ts)
        ents.setdefault(o, to)
        if (s, p, o) not in vistos:
            vistos.add((s, p, o))
            rels.append({"sujeito": s, "predicado": p, "objeto": o})
    return Resultado([{"nome": n, "tipo": t} for n, t in ents.items()], rels, descartes)
