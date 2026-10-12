"""Busca de nomes de um dicionário (gazetteer) em um texto de OCR: sem acento nem maiúsculas, em fronteira de palavra."""
import re
import unicodedata


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^a-z0-9' ]", " ", s.lower()).split())


class Gazetteer:
    def __init__(self, dados: dict | None = None):
        """Dicionário `{nome: {tipo, aliases}}`; sem nada, vazio."""
        dados = dados or {}
        self.tipo = {c: v["tipo"] for c, v in dados.items()}
        # termo normalizado -> nome canônico; termos longos primeiro evitam que "Aldric" vença "Aldric Voss"
        termos = {norm(n): c for c, v in dados.items() for n in [c, *v.get("aliases", [])]}
        self.termos = dict(sorted(termos.items(), key=lambda x: -len(x[0])))

    @classmethod
    def de_dados(cls, dados: dict) -> "Gazetteer":
        return cls(dados=dados)

    def buscar(self, texto: str) -> dict[str, str]:
        """Devolve {canônico: trecho encontrado}."""
        t = norm(texto)
        achados: dict[str, str] = {}
        consumido = [False] * len(t)
        for termo, canon in self.termos.items():
            for m in re.finditer(rf"(?<![a-z0-9]){re.escape(termo)}(?![a-z0-9])", t):
                if not any(consumido[m.start():m.end()]):
                    achados.setdefault(canon, m.group())
                    for i in range(m.start(), m.end()):
                        consumido[i] = True
        return achados
