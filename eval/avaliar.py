"""Compara previsões com o gabarito (precisão, revocação e F1 de entidades e relações).
Uso: python eval/avaliar.py --gab data/gabarito --pred eval/predicoes [--sem-tipo] [--csv eval/resultados.csv]
Cada arquivo de previsão deve ter o mesmo nome do arquivo do gabarito e o mesmo formato (src/schema.py)."""
import argparse
import csv
import json
import unicodedata
from pathlib import Path


def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return " ".join(s.lower().split())


def mapa_aliases(entidades):
    m = {}
    for canon, v in entidades.items():
        m[norm(canon)] = norm(canon)
        for a in v.get("aliases", []):
            m[norm(a)] = norm(canon)
    return m


def conjuntos(ann, m, com_tipo):
    c = lambda n: m.get(norm(n), norm(n))  # noqa: E731
    ents = {(c(e["nome"]), e["tipo"] if com_tipo else "") for e in ann.get("entidades", [])}
    rels = {(c(r["sujeito"]), r["predicado"], c(r["objeto"])) for r in ann.get("relacoes", [])}
    return ents, rels


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


ap = argparse.ArgumentParser()
ap.add_argument("--gab", default="data/gabarito")
ap.add_argument("--pred", default="eval/predicoes")
ap.add_argument("--sem-tipo", action="store_true", help="ignora o tipo da entidade (avaliação branda)")
ap.add_argument("--csv", default="")
a = ap.parse_args()

gab, pred = Path(a.gab), Path(a.pred)
m = mapa_aliases(json.loads((gab / "entidades.json").read_text(encoding="utf-8")))
tot = {"e": [0, 0, 0], "r": [0, 0, 0]}
linhas = []
for g in sorted(p for p in gab.glob("*.json") if p.name != "entidades.json"):
    pp = pred / g.name
    if not pp.exists():
        print(f"[sem previsão] {g.name}")
        continue
    ge, gr = conjuntos(json.loads(g.read_text(encoding="utf-8")), m, not a.sem_tipo)
    pe, pr = conjuntos(json.loads(pp.read_text(encoding="utf-8")), m, not a.sem_tipo)
    linha = {"arquivo": g.name}
    for chave, G, P in (("e", ge, pe), ("r", gr, pr)):
        tp, fp, fn = len(G & P), len(P - G), len(G - P)
        for i, v in enumerate((tp, fp, fn)):
            tot[chave][i] += v
        p, r, f = prf(tp, fp, fn)
        linha.update({f"{chave}_precisao": round(p, 2), f"{chave}_revocacao": round(r, 2), f"{chave}_f1": round(f, 2)})
    linhas.append(linha)
    print(f"{g.name}: entidades F1={linha['e_f1']}  relações F1={linha['r_f1']}")

for chave, nome in (("e", "Entidades"), ("r", "Relações")):
    p, r, f = prf(*tot[chave])
    print(f"TOTAL {nome}: precisão={p:.2f} revocação={r:.2f} F1={f:.2f}")

if a.csv and linhas:
    with open(a.csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(linhas[0].keys()))
        w.writeheader()
        w.writerows(linhas)
