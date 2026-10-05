"""Valida os arquivos do gabarito. Uso: python scripts/validar_gabarito.py [pasta]
Verifica formato, nomes conhecidos em entidades.json e domínio/alcance dos predicados (src/ontologia.json)."""
import json
import sys
import unicodedata
from pathlib import Path
from typing import get_args

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))
from schema import Anotacao, Predicado, TipoEntidade  # noqa: E402

ONT = json.loads((RAIZ / "src" / "ontologia.json").read_text(encoding="utf-8"))
assert set(get_args(Predicado)) == set(ONT["predicados"]), "schema.py e ontologia.json divergem nos predicados"
assert set(get_args(TipoEntidade)) == set(ONT["tipos"]), "schema.py e ontologia.json divergem nos tipos"


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return " ".join(s.lower().split())


pasta = Path(sys.argv[1] if len(sys.argv) > 1 else "data/gabarito")
entidades = json.loads((pasta / "entidades.json").read_text(encoding="utf-8"))
tipo_de = {}
for nome, v in entidades.items():
    tipo_de[norm(nome)] = v.get("tipo")
    for a in v.get("aliases", []):
        tipo_de[norm(a)] = v.get("tipo")

problemas = 0
arquivos = sorted(p for p in pasta.glob("*.json") if p.name != "entidades.json")
for p in arquivos:
    try:
        ann = Anotacao(**json.loads(p.read_text(encoding="utf-8")))
    except Exception as e:  # noqa: BLE001
        print(f"[ERRO] {p.name}: {e}")
        problemas += 1
        continue
    for e in ann.entidades:
        t = tipo_de.get(norm(e.nome))
        if t is None:
            print(f"[AVISO] {p.name}: '{e.nome}' não está em entidades.json")
            problemas += 1
        elif t != e.tipo:
            print(f"[AVISO] {p.name}: '{e.nome}' tem tipo '{e.tipo}' mas entidades.json diz '{t}'")
            problemas += 1
    for r in ann.relacoes:
        ts, to = tipo_de.get(norm(r.sujeito)), tipo_de.get(norm(r.objeto))
        if ts is None or to is None:
            print(f"[AVISO] {p.name}: relação com nome desconhecido ({r.sujeito} -> {r.objeto})")
            problemas += 1
            continue
        regra = ONT["predicados"][r.predicado]
        if ts not in regra["dominio"] or to not in regra["alcance"]:
            print(f"[AVISO] {p.name}: {r.sujeito} ({ts}) {r.predicado} {r.objeto} ({to}) fora do domínio/alcance")
            problemas += 1
print(f"{len(arquivos)} arquivo(s) verificados, {problemas} problema(s).")
