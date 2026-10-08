"""Roda uma estratégia de extração sobre as imagens dos itens do gabarito e grava as previsões.
Uso: python scripts/rodar_extracao.py --estrategia ocr_gaz_rois_brilho --modo rois_brilho [--workers 1]
     python scripts/rodar_extracao.py --estrategia estruturado --modo estruturado
Modos de OCR: completo, inteira_cinza, rois_cinza, rois_otsu, rois_brilho, rois_mix (src/extracao/ocr.py).
O modo `estruturado` (B3a) usa `rois_brilho` + dicionário e soma missões e decisões lidas da estrutura da tela.
Saída: eval/predicoes/<estrategia>/<item>.json (mesmo nome do gabarito), _texto/ e _execucao.json com os tempos.
Depois: python eval/avaliar.py --pred eval/predicoes/<estrategia>"""
import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))
from extracao.estruturada import candidatos, consolidar  # noqa: E402
from extracao.gazetteer import Gazetteer  # noqa: E402
from extracao.ocr import _ler, ocr_imagem  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--estrategia", default="ocr_gazetteer")
ap.add_argument("--gab", default=str(RAIZ / "data" / "gabarito"))
ap.add_argument("--raw", default=str(RAIZ / "data" / "raw"))
ap.add_argument("--gazetteer", default=str(RAIZ / "data" / "gazetteer" / "witcher3_ptbr.json"))
ap.add_argument("--lang", default="por+eng")
ap.add_argument("--modo", default="completo", help="modo de OCR ou `estruturado` (ver acima)")
ap.add_argument("--workers", type=int, default=1, help="OCR em paralelo; para medir tempo use 1")
ap.add_argument("--fuzzy", type=float, default=0.0, help="similaridade mínima do dicionário para tolerar erro de OCR (0 desliga)")
a = ap.parse_args()

gaz = Gazetteer(Path(a.gazetteer))
estruturado = a.modo == "estruturado"
saida = RAIZ / "eval" / "predicoes" / a.estrategia
saida.mkdir(parents=True, exist_ok=True)
texto_dir = saida / "_texto"  # texto bruto do OCR, usado por eval/cobertura_ocr.py
texto_dir.mkdir(exist_ok=True)
itens = []
for g in sorted(Path(a.gab).glob("*.json")):
    if g.name == "entidades.json":
        continue
    midia = next((p for p in Path(a.raw).glob(g.stem + ".*") if p.suffix.lower() in {".jpg", ".png"}), None)
    if midia:  # clipes ficam para a etapa de vídeo
        itens.append((g, midia))


def processa(gm):
    midia = gm[1]
    texto, dt = ocr_imagem(midia, a.lang, "rois_brilho" if estruturado else a.modo)
    t0 = time.perf_counter()
    cands = candidatos(_ler(midia), texto, gaz) if estruturado else []
    return texto, dt + time.perf_counter() - t0, cands


t0 = time.perf_counter()
with ThreadPoolExecutor(max_workers=a.workers) as ex:
    res = list(ex.map(processa, itens))
cands = consolidar({g.stem: r[2] for (g, _), r in zip(itens, res)}, gaz) if estruturado else {}

tempos = {}
for (g, midia), (texto, dt, _) in zip(itens, res):
    achados = gaz.buscar(texto, a.fuzzy)
    ents = [{"nome": c, "tipo": gaz.tipo[c], "evidencia": f"OCR: '{t}'"} for c, t in achados.items()]
    for c in cands.get(g.stem, []):
        if not any(e["nome"] == c.nome and e["tipo"] == c.tipo for e in ents):
            e = {"nome": c.nome, "tipo": c.tipo, "evidencia": c.evidencia}
            if c.subtipo:
                e["subtipo"] = c.subtipo
            if c.estado:
                e["estado"] = c.estado
            ents.append(e)
    pred = {"arquivo": midia.name, "tipo_tela": "outro", "entidades": ents, "relacoes": [], "observacoes": ""}
    (saida / g.name).write_text(json.dumps(pred, ensure_ascii=False, indent=2), encoding="utf-8")
    tempos[g.stem] = round(dt, 2)
    (texto_dir / f"{g.stem}.txt").write_text(texto, encoding="utf-8")
total = time.perf_counter() - t0
(saida / "_execucao.json").write_text(json.dumps({"estrategia": a.estrategia, "fuzzy": a.fuzzy, "lang": a.lang, "modo": a.modo, "workers": a.workers, "itens": len(tempos),
                                                  "tempo_total_s": round(total, 1), "tempo_medio_s": round(sum(tempos.values()) / max(len(tempos), 1), 2),
                                                  "tempos": tempos}, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"{len(tempos)} imagens em {total:.1f}s ({sum(tempos.values()) / max(len(tempos), 1):.2f}s por imagem) -> {saida}")
