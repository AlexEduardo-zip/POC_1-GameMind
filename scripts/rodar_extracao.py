"""Roda uma estratégia de extração sobre as imagens dos itens do gabarito e grava as previsões.
Uso: python scripts/rodar_extracao.py --estrategia ocr_gazetteer [--fuzzy 0.88]
Saída: eval/predicoes/<estrategia>/<item>.json (mesmo nome do gabarito) e _execucao.json com os tempos.
Depois: python eval/avaliar.py --pred eval/predicoes/<estrategia>"""
import argparse
import json
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))
from extracao.gazetteer import Gazetteer  # noqa: E402
from extracao.ocr import ocr_imagem  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--estrategia", default="ocr_gazetteer")
ap.add_argument("--gab", default=str(RAIZ / "data" / "gabarito"))
ap.add_argument("--raw", default=str(RAIZ / "data" / "raw"))
ap.add_argument("--gazetteer", default=str(RAIZ / "data" / "gazetteer" / "witcher3_ptbr.json"))
ap.add_argument("--lang", default="por+eng")
ap.add_argument("--fuzzy", type=float, default=0.0, help="similaridade mínima para tolerar erro de OCR (0 desliga, ex.: 0.88)")
a = ap.parse_args()

gaz = Gazetteer(Path(a.gazetteer))
saida = RAIZ / "eval" / "predicoes" / a.estrategia
saida.mkdir(parents=True, exist_ok=True)
tempos, t0 = {}, time.perf_counter()
for g in sorted(Path(a.gab).glob("*.json")):
    if g.name == "entidades.json":
        continue
    midia = next((p for p in Path(a.raw).glob(g.stem + ".*") if p.suffix.lower() in {".jpg", ".png"}), None)
    if not midia:
        continue  # clipes ficam para a etapa de vídeo
    texto, dt = ocr_imagem(midia, a.lang)
    achados = gaz.buscar(texto, a.fuzzy)
    pred = {"arquivo": midia.name, "tipo_tela": "outro",
            "entidades": [{"nome": c, "tipo": gaz.tipo[c], "evidencia": f"OCR: '{t}'"} for c, t in achados.items()],
            "relacoes": [], "observacoes": ""}
    (saida / g.name).write_text(json.dumps(pred, ensure_ascii=False, indent=2), encoding="utf-8")
    tempos[g.stem] = round(dt, 2)
total = time.perf_counter() - t0
(saida / "_execucao.json").write_text(json.dumps({"estrategia": a.estrategia, "fuzzy": a.fuzzy, "lang": a.lang, "itens": len(tempos),
                                                  "tempo_total_s": round(total, 1), "tempo_ocr_medio_s": round(sum(tempos.values()) / max(len(tempos), 1), 2),
                                                  "tempos": tempos}, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"{len(tempos)} imagens em {total:.1f}s ({sum(tempos.values()) / max(len(tempos), 1):.2f}s de OCR por imagem) -> {saida}")
