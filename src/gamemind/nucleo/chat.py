"""Chat com a IA sobre o jogo: responde só com o que o GameMind leu das capturas.
A base de conhecimento junta o grafo do jogo (entidades com tipo, resumo, outros nomes e relações; `grafo.json`) e o texto
lido de cada captura (banco do jogo). Para cada pergunta, a busca escolhe as entidades citadas (pelo nome, por outro nome ou
por uma grafia parecida) e os trechos de captura que mais combinam com ela, até um limite de tamanho que caiba na IA. Sem
nada de jogo aqui: a busca é por palavras e nomes, e os nomes vêm do que foi aprendido na leitura."""
import json
import math
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime
from difflib import SequenceMatcher

from extracao.gazetteer import norm
from extracao.ia_publica import ErroConector, criar_backend

from . import visao

# palavras da língua que não ajudam a achar nada (português e inglês, as línguas dos textos lidos)
VAZIAS = set("""a o as os um uma uns umas de do da dos das em no na nos nas num numa por pelo pela pelos pelas para pra com sem
que quem qual quais quanto quantos quando onde como porque e ou se ao aos e foi era sao ser estar esta estao tem ter ha havia me te
lhe eu tu ele ela eles elas nos voce voces isso isto aquilo esse essa esses essas este estes aquele aquela meu minha meus minhas
seu sua seus suas dele dela deles delas mais menos muito muita pouco ja ainda tambem so sobre entre ate depois antes jogo fala falar
sabe saber conte diga me mim algum alguma alguns algumas tudo todo toda todos todas nada coisa coisas aqui ali la entao
the of and to in is are was were an what who whom where when how which why do does did it its this that these those with for on""".split())
LIMITE_TRECHO = 600          # caracteres de cada captura no contexto
PARTE_ENTIDADES = 0.4        # fração do limite para as entidades; o resto, para os trechos
MAX_JUNTAS = 6               # entidades que só dividem capturas com as citadas (contexto, não o assunto)
GRAFIA_PARECIDA = 0.8        # palavra da pergunta tão parecida com um nome que é ele escrito de outro jeito (1 letra em 6)


@dataclass
class Entidade:
    nome: str
    tipo: str
    resumo: str = ""
    aliases: list[str] = field(default_factory=list)
    capturas: list[str] = field(default_factory=list)
    relacoes: list[str] = field(default_factory=list)   # "Aldric membro de Ordem do Corvo"

    def texto(self) -> str:
        outros = f"; também: {', '.join(self.aliases)}" if self.aliases else ""
        partes = [f"- {self.nome} ({self.tipo}{outros})"]
        if self.resumo:
            partes.append(f": {self.resumo}")
        if self.relacoes:
            partes.append(f" Relações: {'; '.join(self.relacoes[:6])}.")
        partes.append(f" Aparece em {len(self.capturas)} captura(s).")
        return "".join(partes)


@dataclass
class Trecho:
    arquivo: str
    texto: str


@dataclass
class Contexto:
    """O que vai para a IA: entidades e trechos. Os trechos são numerados (C1, C2...) para a resposta citar a captura."""
    entidades: list[Entidade]
    trechos: list[Trecho]

    @property
    def fontes(self) -> dict[str, str]:
        return {f"C{i}": t.arquivo for i, t in enumerate(self.trechos, 1)}

    def texto(self) -> str:
        partes = []
        if self.entidades:
            partes += ["## Entidades do jogo"] + [e.texto() for e in self.entidades]
        if self.trechos:
            partes += ["", "## Trechos lidos das capturas"] + [f"[C{i}] ({t.arquivo})\n{t.texto}" for i, t in enumerate(self.trechos, 1)]
        return "\n".join(partes)


def _palavras(texto: str) -> list[str]:
    return [p for p in norm(texto).split() if len(p) >= 3 and p not in VAZIAS]


def _linhas_boas(texto: str) -> list[str]:
    """Linhas do OCR que parecem texto: letras na maior parte, ao menos uma palavra de verdade (o resto é ruído da interface)."""
    boas = []
    for linha in texto.splitlines():
        linha = " ".join(linha.split())
        visiveis = linha.replace(" ", "")
        letras = sum(c.isalpha() for c in visiveis)
        if letras >= 4 and letras >= 0.6 * len(visiveis) and any(len(p) >= 3 for p in norm(linha).split()):
            boas.append(linha)
    return boas


def trecho_da_leitura(arquivo: str, leitura: dict) -> Trecho | None:
    """O texto de uma captura (ou de um clipe, quadro a quadro): as regiões primeiro, depois a tela inteira, sem linhas repetidas."""
    vistas, linhas = set(), []
    for quadro in leitura.get("quadros", []):
        secoes = quadro.get("secoes", {})
        for nome in sorted(secoes, key=lambda s: s == "tela"):   # "tela" (a tela inteira) por último
            for linha in _linhas_boas(secoes[nome] or ""):
                if norm(linha) not in vistas:
                    vistas.add(norm(linha))
                    linhas.append(linha)
    texto = "\n".join(linhas)
    if not texto:
        return None
    return Trecho(arquivo, texto[:LIMITE_TRECHO].rsplit("\n", 1)[0] if len(texto) > LIMITE_TRECHO else texto)


class Base:
    """O que o jogo sabe, pronto para a busca."""

    def __init__(self, entidades: list[Entidade], trechos: list[Trecho]):
        self.entidades, self.trechos = entidades, trechos
        self._termos = [(e, [norm(t) for t in [e.nome, *e.aliases] if norm(t)]) for e in entidades]
        self._palavras_trecho = [Counter(_palavras(t.texto)) for t in trechos]
        n = len(trechos) or 1
        df = Counter(p for c in self._palavras_trecho for p in c)
        self._idf = {p: math.log(1 + n / f) for p, f in df.items()}

    @classmethod
    def de_dados(cls, grafo: dict, leituras: dict[str, dict]) -> "Base":
        """`grafo`: o `grafo.json` do jogo; `leituras`: {arquivo: leitura}."""
        ents = {}
        for no in grafo.get("nos", []):
            ents[no["nome"]] = Entidade(no["nome"], no.get("tipo", ""), (no.get("descricao") or "").strip(),
                                        [a for a in no.get("aliases", []) if a != no["nome"]],
                                        sorted({f["arquivo"] for f in no.get("fontes", [])}))
        for a in grafo.get("arestas", []):
            frase = f"{a['sujeito']} {a['predicado'].replace('_', ' ')} {a['objeto']}"
            for nome in (a["sujeito"], a["objeto"]):
                if nome in ents:
                    ents[nome].relacoes.append(frase)
        trechos = [t for arq, l in sorted(leituras.items()) if (t := trecho_da_leitura(arq, l))]
        return cls(list(ents.values()), trechos)

    @classmethod
    def do_jogo(cls, jogo) -> "Base":
        """Do que o jogo já tem: o grafo da última leitura e o texto de todas as capturas lidas."""
        try:
            grafo = json.loads(jogo.caminho_grafo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            grafo = {}
        return cls.de_dados(grafo, {m.nome: l for m, l in jogo.leituras()})

    @property
    def vazia(self) -> bool:
        return not self.entidades and not self.trechos

    # ---------------------------------------------------------------- busca
    def citadas(self, pergunta: str) -> list[Entidade]:
        """Entidades que a pergunta cita: o nome inteiro, outro nome, uma palavra marcante do nome ou uma grafia parecida."""
        q = norm(pergunta)
        palavras = set(_palavras(pergunta))
        pontos = []
        for e, termos in self._termos:
            p = 0.0
            for i, t in enumerate(termos):
                if re.search(rf"\b{re.escape(t)}\b", q):
                    p = max(p, 3.0 if i == 0 else 2.5)
                    continue
                for parte in (x for x in t.split() if len(x) >= 4 and x not in VAZIAS):
                    if parte in palavras:
                        p = max(p, 1.5)
                    elif len(parte) >= 5 and any(SequenceMatcher(None, parte, w).ratio() >= GRAFIA_PARECIDA for w in palavras):
                        p = max(p, 1.0)
            if p:
                pontos.append((p, len(e.capturas), e))
        return [e for *_, e in sorted(pontos, key=lambda x: (-x[0], -x[1]))]

    def assunto_novo(self, pergunta: str) -> bool:
        """A pergunta traz um nome que a base não conhece (palavra com maiúscula fora do começo): é outro assunto, e ela não
        herda as entidades da pergunta anterior. Palavras comuns desconhecidas não contam: "e o que ela procura?" continua."""
        conhecidas = set(self._idf) | {p for _, termos in self._termos for t in termos for p in t.split()}
        palavras = re.findall(r"\w+", pergunta)
        nomes = [w for w in palavras[1:] if w[:1].isupper() and len(w) >= 3]
        return any(norm(w) not in conhecidas for w in nomes)

    def buscar(self, pergunta: str, anteriores: list[str] = (), limite: int = 8000) -> Contexto:
        """As entidades e os trechos para responder `pergunta`. `anteriores`: perguntas anteriores da conversa, para as de
        continuação ("e onde ele mora?") herdarem as entidades da última. `limite`: tamanho do contexto, em caracteres."""
        citadas = self.citadas(pergunta)
        if not citadas and anteriores and not self.assunto_novo(pergunta):
            citadas = self.citadas(list(anteriores)[-1])
        geral = not citadas
        nomes_citados = {e.nome for e in citadas}
        vizinhas = [e for e in self.entidades if e.nome not in nomes_citados
                    and any(n in r for r in e.relacoes for n in nomes_citados)]
        if geral:   # pergunta geral ("quem são os personagens?"): as entidades mais vistas
            resto = sorted(self.entidades, key=lambda e: -len(e.capturas))
        else:       # as que aparecem nas mesmas capturas das citadas, das que mais dividem tela para as que menos
            caps = {c for e in citadas for c in e.capturas}
            juntas = [(len(caps & set(e.capturas)), e) for e in self.entidades if e.nome not in nomes_citados]
            resto = [e for n, e in sorted(juntas, key=lambda x: (-x[0], -len(x[1].capturas))) if n][:MAX_JUNTAS]
        entidades, usado = [], 0
        for e in [*citadas, *vizinhas, *resto]:
            tam = len(e.texto()) + 1
            if e in entidades:
                continue
            if usado + tam > limite * PARTE_ENTIDADES:
                if e not in citadas:
                    break
                continue
            entidades.append(e)
            usado += tam
        trechos = self._trechos(pergunta, citadas, limite - usado, geral)
        return Contexto(entidades, trechos)

    def _trechos(self, pergunta: str, citadas: list[Entidade], espaco: int, geral: bool) -> list[Trecho]:
        palavras = set(_palavras(pergunta)) | {p for e in citadas for p in _palavras(e.nome)}
        nomes = [norm(e.nome) for e in citadas]
        pontos = []
        for i, (t, conta) in enumerate(zip(self.trechos, self._palavras_trecho)):
            p = sum(self._idf.get(w, 0) for w in palavras if w in conta)
            texto = norm(t.texto)
            p += sum(2.0 for n in nomes if n and n in texto)
            if p > 0 or geral:
                pontos.append((p, -i, t))
        escolhidos, usado = [], 0
        for _, _, t in sorted(pontos, key=lambda x: (-x[0], x[1])):
            tam = len(t.texto) + len(t.arquivo) + 12
            if usado + tam > espaco:
                continue
            escolhidos.append(t)
            usado += tam
        return escolhidos


# ---------------------------------------------------------------- conversa
ARQUIVO = "chat.json"        # a conversa do jogo, na pasta dele
HISTORICO = 3                # perguntas e respostas anteriores que vão junto (para as perguntas de continuação)
GUARDADAS = 200              # mensagens guardadas no máximo
MAX_CITADAS = 5              # capturas do campo "capturas" por resposta (as primeiras, as mais importantes para a IA)
LIMITE_OLLAMA = 12000        # caracteres de contexto: cabem no contexto de 8 mil tokens do Ollama com o histórico e a resposta
CONTEXTO_OLLAMA = 8192       # tokens de contexto do modelo local no chat (a leitura usa menos)
LIMITE_CLAUDE = 30000
INSTRUCOES = """Você é o assistente do GameMind e responde perguntas sobre o jogo que o usuário está jogando.
Use SOMENTE as informações enviadas, que vieram das capturas de tela do próprio usuário: as entidades do jogo (com resumo e
relações) e os trechos lidos das capturas (texto de OCR, que pode ter erros de leitura e pedaços sem sentido).
Regras:
- Responda no idioma da pergunta, de forma direta e curta (até 6 frases), a não ser que peçam detalhes.
- Em "capturas", liste as marcas (C1, C2...) dos trechos de onde tirou a resposta, do mais importante para o menos. Pode
  citar no texto também, como [C2]. Se a informação não estiver nas capturas, deixe "capturas" vazio.
- Se as informações enviadas não bastarem, diga que isso ainda não apareceu nas capturas lidas. Não invente e não use o que
  você saiba do jogo por fora: o usuário quer só o que ele mesmo viu.
- Ignore pedaços sem sentido dos trechos (ruído do OCR)."""
# a lista de capturas é campo obrigatório: modelos pequenos esquecem de citar no texto, mas preenchem o campo pedido
ESQUEMA = {"type": "object", "properties": {"resposta": {"type": "string"}, "capturas": {"type": "array", "items": {"type": "string"}}},
           "required": ["resposta", "capturas"]}
SEM_RESPOSTA = "Não consegui uma resposta da IA. Tente perguntar de outro jeito."


@dataclass
class Mensagem:
    pergunta: str
    resposta: str
    fontes: dict[str, str] = field(default_factory=dict)   # marca citada na resposta ("C2") -> captura
    ia: str = ""
    quando: str = ""


def citar(resposta: str, fontes: dict[str, str]) -> tuple[str, dict[str, str]]:
    """As marcas [C2] da resposta que existem no contexto (e só elas: uma marca inventada sai do texto). "[C1, C3]" vira
    "[C1] [C3]"."""
    usadas = {}

    def trocar(m):
        marcas = [x.strip().upper() for x in m.group(1).split(",")]
        validas = [x for x in marcas if x in fontes]
        usadas.update({x: fontes[x] for x in validas})
        return " ".join(f"[{x}]" for x in validas)
    texto = re.sub(r"\[\s*(C\d+(?:\s*,\s*C\d+)*)\s*\]", trocar, resposta, flags=re.IGNORECASE)
    return re.sub(r" +([.,;:!?])", r"\1", re.sub(r"  +", " ", texto)).strip(), usadas


class Conversa:
    """A conversa de um jogo: as mensagens (guardadas em `chat.json`) e a base onde as respostas se apoiam."""

    def __init__(self, pasta, base: Base):
        self.arquivo = pasta / ARQUIVO
        self.base = base
        try:
            self.mensagens = [Mensagem(**m) for m in json.loads(self.arquivo.read_text(encoding="utf-8"))]
        except (OSError, ValueError, TypeError):
            self.mensagens = []

    def pedido(self, pergunta: str, limite: int) -> tuple[str, Contexto]:
        anteriores = self.mensagens[-HISTORICO:]
        ctx = self.base.buscar(pergunta, [m.pergunta for m in anteriores], limite)
        conversa = "".join(f"Usuário: {m.pergunta}\nAssistente: {m.resposta[:400]}\n" for m in anteriores)
        partes = [ctx.texto() or "(o jogo ainda não tem nada lido)"]
        if conversa:
            partes.append(f"## Conversa até aqui\n{conversa}")
        partes.append(f"## Pergunta\n{pergunta}")
        return "\n\n".join(partes), ctx

    def perguntar(self, pergunta: str, backend) -> Mensagem:
        """Pergunta à IA com o que a busca achou, guarda e devolve a mensagem. Levanta o erro da IA (ErroConector, OSError)."""
        texto, ctx = self.pedido(pergunta, limite_para(backend))
        resp = backend.perguntar(INSTRUCOES, texto, ESQUEMA)
        resp = resp if isinstance(resp, dict) else {}
        resposta, fontes = citar(str(resp.get("resposta", "")).strip(), ctx.fontes)
        for marca in (resp.get("capturas") or [])[:MAX_CITADAS]:   # as do campo, além das citadas no texto
            marca = str(marca).strip(" []").upper()
            if marca in ctx.fontes:
                fontes.setdefault(marca, ctx.fontes[marca])
        m = Mensagem(pergunta, resposta or SEM_RESPOSTA, fontes, backend.nome, datetime.now().isoformat(timespec="seconds"))
        self.mensagens.append(m)
        self.salvar()
        return m

    def salvar(self) -> None:
        self.arquivo.write_text(json.dumps([asdict(m) for m in self.mensagens[-GUARDADAS:]], ensure_ascii=False, indent=1),
                                encoding="utf-8")

    def limpar(self) -> None:
        self.mensagens = []
        self.arquivo.unlink(missing_ok=True)


def limite_para(backend) -> int:
    return LIMITE_OLLAMA if hasattr(backend, "num_ctx") else LIMITE_CLAUDE


def backend_do_chat(ia: str):
    """A IA do jogo, preparada para o chat: o modelo local com contexto maior (a base vai inteira no pedido)."""
    b = criar_backend(ia)
    if hasattr(b, "num_ctx"):
        b.num_ctx = CONTEXTO_OLLAMA
        b.timeout = 300.0
    return b


# ---------------------------------------------------------------- disponibilidade
def disponibilidade(jogo, config) -> tuple[bool, str]:
    """(dá para conversar, motivo para o usuário). O chat precisa de uma IA escolhida para o jogo, funcionando, e de algo lido.
    Consulta o Ollama (até 3 s): rode fora da interface."""
    cfg = config.do_jogo(jogo)
    if not cfg.ia:
        return False, "Este jogo é lido só com OCR. Para conversar, escolha uma IA (Ollama ou Claude) em Jogo > Configurar jogo."
    if not jogo.resumo()["lida"]:
        return False, "Ainda não há nada lido deste jogo. Clique em Iniciar leitura e volte aqui."
    try:
        b = backend_do_chat(cfg.ia)
    except ErroConector as e:
        return False, str(e)
    if hasattr(b, "num_ctx"):   # Ollama: aberto e com o modelo baixado
        try:
            instalados = {m["name"] for m in visao._json("/api/tags").get("models", [])}
        except (OSError, ValueError):
            return False, "O Ollama não está aberto. Abra o Ollama (ou rode `ollama serve`) e tente de novo."
        if b.modelo not in instalados and f"{b.modelo}:latest" not in instalados:
            return False, f"O modelo {b.modelo} não está no Ollama. Baixe com: ollama pull {b.modelo}"
    return True, b.nome


__all__ = ["Base", "Contexto", "Conversa", "Entidade", "Mensagem", "Trecho", "backend_do_chat", "citar", "disponibilidade",
           "trecho_da_leitura"]
