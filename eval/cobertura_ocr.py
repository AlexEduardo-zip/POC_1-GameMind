"""Mede o OCR sem depender de dicionário: para cada entidade do gabarito, o nome (ou um alias) aparece no texto do OCR?
Uso: python eval/cobertura_ocr.py --pred eval/predicoes/<estrategia> [--gab data/gabarito] [--fuzzy 0.85]
Lê <pred>/_texto/<item>.txt (gravado por scripts/rodar_extracao.py). Relata, por tipo de tela e de entidade,
a fração de entidades achadas no texto (exata, e com tolerância a erro de OCR)."""
import argparse
import json
import re
import sys
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^a-z0-9' ]", " ", s.lower()).split())


def achou(termo, texto, palavras, fuzzy):
    if re.search(rf"(?<![a-z0-9]){re.escape(termo)}(?![a-z0-9])", texto):
        return "exata"
    if fuzzy and len(termo) >= 5:
        k = len(termo.split())
        for i in range(len(palavras) - k + 1):
            j = " ".join(palavras[i:i + k])
            if abs(len(j) - len(termo)) <= 2 and SequenceMatcher(None, j, termo).ratio() >= fuzzy:
                return "aprox"
    return ""


ap = argparse.ArgumentParser()
ap.add_argument("--pred", required=True)
ap.add_argument("--gab", default="data/gabarito")
ap.add_argument("--fuzzy", type=float, default=0.85)
a = ap.parse_args()

gab = Path(a.gab)
ents = json.loads((gab / "entidades.json").read_text(encoding="utf-8"))
aliases = {c: [c, *v.get("aliases", [])] for c, v in ents.items()}
por_tela, por_tipo, total = defaultdict(lambda: [0, 0, 0]), defaultdict(lambda: [0, 0, 0]), [0, 0, 0]
for g in sorted(gab.glob("*.json")):
    t = Path(a.pred) / "_texto" / f"{g.stem}.txt"
    if g.name == "entidades.json" or not t.exists():
        continue
    texto = norm(t.read_text(encoding="utf-8"))
    palavras = texto.split()
    d = json.loads(g.read_text(encoding="utf-8"))
    for e in d["entidades"]:
        nomes = [norm(x) for x in aliases.get(e["nome"], [e["nome"]])]
        r = next((x for x in (achou(n, texto, palavras, 0) for n in nomes) if x), "") or next((x for x in (achou(n, texto, palavras, a.fuzzy) for n in nomes) if x), "")
        for acc in (por_tela[d["tipo_tela"]], por_tipo[e["tipo"]], total):
            acc[0] += 1
            acc[1] += r == "exata"
            acc[2] += r in ("exata", "aprox")


def mostra(titulo, dic):
    print(f"\n{titulo}\n  {'':<14}{'entidades':>10}{'exata':>8}{'com aprox.':>12}")
    for k in sorted(dic):
        n, ex, ap_ = dic[k]
        print(f"  {k:<14}{n:>10}{ex / n:>8.2f}{ap_ / n:>12.2f}")


mostra("Cobertura por tipo de tela", por_tela)
mostra("Cobertura por tipo de entidade", por_tipo)
n, ex, ap_ = total
print(f"\nTOTAL: {n} entidades; no texto do OCR: exata {ex / n:.2f}, com aproximação {ap_ / n:.2f}")
