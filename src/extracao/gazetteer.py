"""Busca de nomes de um dicionário (gazetteer) em um texto de OCR.
Compara sem acento nem maiúsculas, em fronteira de palavra; com `fuzzy` aceita pequenos erros de OCR."""
import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^a-z0-9' ]", " ", s.lower()).split())


class Gazetteer:
    def __init__(self, caminho: Path):
        dados = json.loads(Path(caminho).read_text(encoding="utf-8"))["entidades"]
        self.tipo = {c: v["tipo"] for c, v in dados.items()}
        # termo normalizado -> nome canônico; termos longos primeiro evitam que "Peter Saar" vença "Peter Saar Gwynleve"
        termos = {norm(n): c for c, v in dados.items() for n in [c, *v.get("aliases", [])]}
        self.termos = dict(sorted(termos.items(), key=lambda x: -len(x[0])))
        self.grafia = {norm(n): n for c, v in dados.items() for n in [c, *v.get("aliases", [])]}

    def buscar(self, texto: str, fuzzy: float = 0.0) -> dict[str, str]:
        """Devolve {canônico: trecho encontrado}. `fuzzy` é a razão mínima de similaridade (0 desliga)."""
        t = norm(texto)
        achados: dict[str, str] = {}
        consumido = [False] * len(t)
        for termo, canon in self.termos.items():
            for m in re.finditer(rf"(?<![a-z0-9]){re.escape(termo)}(?![a-z0-9])", t):
                if not any(consumido[m.start():m.end()]):
                    achados.setdefault(canon, m.group())
                    for i in range(m.start(), m.end()):
                        consumido[i] = True
        if fuzzy:
            palavras = t.split()
            for termo, canon in self.termos.items():
                if canon in achados or len(termo) < 6:
                    continue
                k = len(termo.split())
                for i in range(len(palavras) - k + 1):
                    janela = " ".join(palavras[i:i + k])
                    if abs(len(janela) - len(termo)) <= 2 and SequenceMatcher(None, janela, termo).ratio() >= fuzzy:
                        achados[canon] = janela
                        break
        return achados

    def buscar_filtrado(self, texto: str, fuzzy: float = 0.0) -> dict[str, str]:
        """Como `buscar`, mas item do dicionário só vale em linha de título (maiúsculas): em minúsculas é o rótulo
        do equipamento em uso no inventário."""
        achados = self.buscar(texto, fuzzy)
        caixa_alta = [norm(l) for l in texto.splitlines()
                      if sum(c.isalpha() for c in l) >= 4 and sum(c.isupper() for c in l) >= 0.7 * sum(c.isalpha() for c in l)]
        return {c: t for c, t in achados.items() if self.tipo[c] != "item" or any(norm(t) in l for l in caixa_alta)}

    def corrigir(self, texto: str, limiar: float = 0.85) -> str:
        """Corrige erro de OCR em trechos que lembram um nome do dicionário (ex.: "Kaey Morhen" -> "Kaer Morhen")."""
        palavras = texto.split()
        for termo, canon in self.termos.items():
            if len(termo) < 6:
                continue
            k = len(termo.split())
            for i in range(len(palavras) - k + 1):
                trecho = " ".join(palavras[i:i + k])
                n = norm(trecho)
                if n != termo and abs(len(n) - len(termo)) <= 2 and SequenceMatcher(None, n, termo).ratio() >= limiar:
                    palavras[i:i + k] = [self.grafia.get(termo, canon)]
                    break
        return " ".join(palavras)
