"""Compara previsões com o gabarito (precisão, revocação e F1 de entidades e relações).
Uso: python eval/avaliar.py --gab data/gabarito --pred eval/predicoes [--sem-tipo] [--csv eval/resultados.csv] [--csv-quebras eval/quebras.csv]
Cada arquivo de previsão deve ter o mesmo nome do arquivo do gabarito e o mesmo formato (src/schema.py).

Relatório: total (micro) sem os elementos em reserva (ver "reserva" em src/ontologia.json), e quebras por
tipo de entidade, por predicado e por tipo de tela, com a média simples entre tipos (macro) para o glossário
não dominar o número. Os elementos em reserva (evento, gera) são relatados à parte."""
import argparse
import csv
import json
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


SIMETRICOS = {"relacionado_a"}  # igual a src/schema.py


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
    def rel(r):
        a, b = c(r["sujeito"]), c(r["objeto"])
        if r["predicado"] in SIMETRICOS and a > b:  # (A, B) e (B, A) são a mesma relação
            a, b = b, a
        return (a, r["predicado"], b)
    rels = {rel(r) for r in ann.get("relacoes", [])}
    return ents, rels


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


def soma(d, chave, tp, fp, fn):
    for i, v in enumerate((tp, fp, fn)):
        d[chave][i] += v


def tabela(titulo, d, csv_linhas, grupo):
    print(f"\n{titulo}")
    print(f"  {'':<16}{'gab':>5}{'prev':>6}{'acertos':>9}{'precisão':>10}{'revocação':>11}{'F1':>6}")
    fs = []
    for k in sorted(d):
        tp, fp, fn = d[k]
        p, r, f = prf(tp, fp, fn)
        if tp + fn:  # só entra na média quem tem algo no gabarito
            fs.append((p, r, f))
        print(f"  {k:<16}{tp + fn:>5}{tp + fp:>6}{tp:>9}{p:>10.2f}{r:>11.2f}{f:>6.2f}")
        csv_linhas.append({"grupo": grupo, "chave": k, "gabarito": tp + fn, "previsto": tp + fp, "acertos": tp,
                           "precisao": round(p, 3), "revocacao": round(r, 3), "f1": round(f, 3)})
    if fs:
        n = len(fs)
        mp, mr, mf = (sum(x[i] for x in fs) / n for i in range(3))
        print(f"  {'média simples':<16}{'':>5}{'':>6}{'':>9}{mp:>10.2f}{mr:>11.2f}{mf:>6.2f}")
        csv_linhas.append({"grupo": grupo, "chave": "macro", "gabarito": "", "previsto": "", "acertos": "",
                           "precisao": round(mp, 3), "revocacao": round(mr, 3), "f1": round(mf, 3)})


ap = argparse.ArgumentParser()
ap.add_argument("--gab", default="data/gabarito")
ap.add_argument("--pred", default="eval/predicoes")
ap.add_argument("--sem-tipo", action="store_true", help="ignora o tipo da entidade (avaliação branda)")
ap.add_argument("--csv", default="")
ap.add_argument("--csv-quebras", default="", help="grava as quebras por tipo de entidade, predicado e tipo de tela")
ap.add_argument("--sem-quebras", action="store_true", help="só o total")
a = ap.parse_args()

gab, pred = Path(a.gab), Path(a.pred)
raiz = Path(__file__).resolve().parent.parent
ont = json.loads((raiz / "src" / "ontologia.json").read_text(encoding="utf-8"))
reserva = set(ont.get("reserva", []))  # tipos e predicados em reserva
m = mapa_aliases(json.loads((gab / "entidades.json").read_text(encoding="utf-8")))

tot = {"e": [0, 0, 0], "r": [0, 0, 0]}
por_tipo = defaultdict(lambda: [0, 0, 0])
por_pred = defaultdict(lambda: [0, 0, 0])
por_tela = defaultdict(lambda: [0, 0, 0])
em_reserva = defaultdict(lambda: [0, 0, 0])
linhas = []
for g in sorted(p for p in gab.glob("*.json") if p.name != "entidades.json"):
    pp = pred / g.name
    if not pp.exists():
        print(f"[sem previsão] {g.name}")
        continue
    gj = json.loads(g.read_text(encoding="utf-8"))
    ge, gr = conjuntos(gj, m, not a.sem_tipo)
    pe, pr = conjuntos(json.loads(pp.read_text(encoding="utf-8")), m, not a.sem_tipo)
    # a quebra por tipo usa sempre o tipo, mesmo no modo brando
    gt, _ = conjuntos(gj, m, True)
    pt, _ = conjuntos(json.loads(pp.read_text(encoding="utf-8")), m, True)
    linha = {"arquivo": g.name}
    for chave, G, P in (("e", ge, pe), ("r", gr, pr)):
        # x[1] é o tipo (entidades) ou o predicado (relações); ambos podem estar em reserva
        G_, P_ = {x for x in G if x[1] not in reserva}, {x for x in P if x[1] not in reserva}
        tp, fp, fn = len(G_ & P_), len(P_ - G_), len(G_ - P_)
        soma(tot, chave, tp, fp, fn)
        p, r, f = prf(tp, fp, fn)
        linha.update({f"{chave}_precisao": round(p, 2), f"{chave}_revocacao": round(r, 2), f"{chave}_f1": round(f, 2)})
    linhas.append(linha)
    print(f"{g.name}: entidades F1={linha['e_f1']}  relações F1={linha['r_f1']}")

    tela = gj.get("tipo_tela", "outro")
    for t in {x[1] for x in gt | pt}:
        G_, P_ = {x for x in gt if x[1] == t}, {x for x in pt if x[1] == t}
        tp, fp, fn = len(G_ & P_), len(P_ - G_), len(G_ - P_)
        if t in reserva:
            soma(em_reserva, f"entidade {t}", tp, fp, fn)
        else:
            soma(por_tipo, t, tp, fp, fn)
            soma(por_tela, tela, tp, fp, fn)
    _, gr_ = conjuntos(gj, m, True)
    _, pr_ = conjuntos(json.loads(pp.read_text(encoding="utf-8")), m, True)
    for pdc in {x[1] for x in gr_ | pr_}:
        G_, P_ = {x for x in gr_ if x[1] == pdc}, {x for x in pr_ if x[1] == pdc}
        tp, fp, fn = len(G_ & P_), len(P_ - G_), len(G_ - P_)
        soma(em_reserva if pdc in reserva else por_pred, f"relação {pdc}" if pdc in reserva else pdc, tp, fp, fn)

print()
for chave, nome in (("e", "Entidades"), ("r", "Relações")):
    p, r, f = prf(*tot[chave])
    print(f"TOTAL {nome} (micro, sem reserva): precisão={p:.2f} revocação={r:.2f} F1={f:.2f}")

quebras = []
if not a.sem_quebras and linhas:
    tabela("Entidades por tipo de entidade (tipo exato)", por_tipo, quebras, "tipo_entidade")
    tabela("Relações por predicado", por_pred, quebras, "predicado")
    tabela("Entidades por tipo de tela (do gabarito)", por_tela, quebras, "tipo_tela")
    if em_reserva:
        tabela("Em reserva (relatado à parte, fora do total)", em_reserva, quebras, "reserva")
    else:
        print(f"\nEm reserva ({', '.join(sorted(reserva))}): nenhum caso no gabarito ou na previsão.")

if a.csv and linhas:
    with open(a.csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(linhas[0].keys()))
        w.writeheader()
        w.writerows(linhas)
if a.csv_quebras and quebras:
    with open(a.csv_quebras, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(quebras[0].keys()))
        w.writeheader()
        w.writerows(quebras)
