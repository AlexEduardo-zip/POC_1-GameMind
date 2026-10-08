"""Linha de base: OCR da imagem inteira + busca de nomes e aliases de data/gabarito/entidades.json.
Teste ponta a ponta do avaliador (não é o extrator final). Só imagens; clipes ficam sem previsão.
Uso: python scripts/baseline_ocr.py [--gab data/gabarito] [--raw data/raw] [--saida eval/predicoes/baseline_ocr]"""
import argparse
import json
import re
import time
import unicodedata
from pathlib import Path

import pytesseract
from PIL import Image


def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return " ".join(s.lower().split())


ap = argparse.ArgumentParser()
ap.add_argument("--gab", default="data/gabarito")
ap.add_argument("--raw", default="data/raw")
ap.add_argument("--saida", default="eval/predicoes/baseline_ocr")
ap.add_argument("--lang", default="por+eng")
a = ap.parse_args()

ents = json.loads((Path(a.gab) / "entidades.json").read_text(encoding="utf-8"))
nomes = [(norm(n), canon) for canon, v in ents.items() for n in [canon, *v.get("aliases", [])]]
nomes.sort(key=lambda x: -len(x[0]))  # nomes longos primeiro
saida = Path(a.saida)
saida.mkdir(parents=True, exist_ok=True)

t0 = time.time()
for g in sorted(Path(a.gab).glob("*.json")):
    if g.name == "entidades.json":
        continue
    midia = next((p for p in Path(a.raw).glob(g.stem + ".*") if p.suffix.lower() in {".jpg", ".png"}), None)
    if not midia:
        continue
    texto = norm(pytesseract.image_to_string(Image.open(midia), lang=a.lang))
    achados = {}
    for n, canon in nomes:
        if re.search(rf"\b{re.escape(n)}\b", texto):
            achados[canon] = {"nome": canon, "tipo": ents[canon]["tipo"], "evidencia": f"OCR contém '{n}'"}
    pred = {"arquivo": midia.name, "tipo_tela": json.loads(g.read_text(encoding="utf-8")).get("tipo_tela", ""),
            "entidades": list(achados.values()), "relacoes": []}
    (saida / g.name).write_text(json.dumps(pred, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{g.name}: {len(achados)} entidades")
print(f"tempo total: {time.time() - t0:.1f}s")
