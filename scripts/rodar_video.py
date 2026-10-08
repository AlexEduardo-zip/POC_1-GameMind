"""Etapa B4: o mesmo pipeline sobre quadros de vídeo, agregado por clipe.
Fase 1 (cache): amostra um quadro por segundo de cada clipe do gabarito e roda OCR, dicionário e extração estruturada em cada quadro.
Fase 2: agrega os quadros de cada clipe (a cada `--intervalo` segundos, ou só o quadro do meio) e, opcionalmente, passa o texto
agregado a um LLM local (uma chamada por clipe).
Uso: python scripts/rodar_video.py --estrategia video_2s --intervalo 2 [--llm qwen2.5:7b] [--quadro-unico]
Saída: eval/predicoes/<estrategia>/<clipe>.json e _execucao.json. Avalie com: python eval/avaliar.py --pred eval/predicoes/<estrategia>"""
import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))
from extracao.estruturada import Cand, Rel, candidatos, consolidar  # noqa: E402
from extracao.gazetteer import Gazetteer, norm  # noqa: E402
from extracao.llm import OllamaBackend, normalizar  # noqa: E402
from extracao.ocr import ocr_secoes_img  # noqa: E402
from extracao.video import amostrar  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--estrategia", default="video_2s")
ap.add_argument("--intervalo", type=int, default=2, help="segundos entre quadros usados (múltiplo de 1)")
ap.add_argument("--quadro-unico", action="store_true", help="usa só o quadro do meio de cada clipe (equivale a uma screenshot)")
ap.add_argument("--min-quadros", type=int, default=1, help="quadros em que um nome do dicionário precisa aparecer")
ap.add_argument("--llm", default="", help="modelo do Ollama para relações e itens (vazio = sem LLM)")
ap.add_argument("--workers", type=int, default=4)
ap.add_argument("--gab", default=str(RAIZ / "data" / "gabarito"))
ap.add_argument("--raw", default=str(RAIZ / "data" / "raw"))
ap.add_argument("--gazetteer", default=str(RAIZ / "data" / "gazetteer" / "witcher3_ptbr.json"))
a = ap.parse_args()

gaz = Gazetteer(Path(a.gazetteer))
cache_dir = RAIZ / "eval" / "cache_video"
cache_dir.mkdir(parents=True, exist_ok=True)
clipes = []
for g in sorted(Path(a.gab).glob("vid_*.json")):
    midia = next((p for p in Path(a.raw).glob(g.stem + ".*") if p.suffix.lower() == ".mp4"), None)
    if midia:
        clipes.append((g.stem, midia))


def proc_quadro(args):
    t, img = args
    t0 = time.perf_counter()
    secoes = ocr_secoes_img(img)
    texto = "\n".join(secoes.values())
    cands, rels = candidatos(img, texto, gaz)
    idx = {id(c): i for i, c in enumerate(cands)}
    return {"t": t, "secoes": secoes, "dic": gaz.buscar_filtrado(texto), "tempo_s": round(time.perf_counter() - t0, 2),
            "cands": [vars(c) for c in cands],
            "rels": [{"s": idx[id(r.sujeito)] if isinstance(r.sujeito, Cand) else r.sujeito, "sc": isinstance(r.sujeito, Cand),
                      "p": r.predicado, "o": idx[id(r.objeto)] if isinstance(r.objeto, Cand) else r.objeto, "oc": isinstance(r.objeto, Cand),
                      "ev": r.evidencia} for r in rels]}


# ---- fase 1: quadros a 1 s, com cache
for stem, midia in clipes:
    c = cache_dir / f"{stem}.json"
    if c.exists():
        continue
    t0 = time.perf_counter()
    quadros = amostrar(midia, 1.0)
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        res = list(ex.map(proc_quadro, quadros))
    c.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    print(f"{stem}: {len(res)} quadros em {time.perf_counter() - t0:.0f}s", flush=True)

# ---- fase 2: agregação por clipe
selec = {}
for stem, _ in clipes:
    qs = json.loads((cache_dir / f"{stem}.json").read_text(encoding="utf-8"))
    selec[stem] = [qs[len(qs) // 2]] if a.quadro_unico else qs[:: a.intervalo]

cands_q, rels_q = {}, {}
for stem, qs in selec.items():
    for i, q in enumerate(qs):
        cs = [Cand(**d) for d in q["cands"]]
        key = f"{stem}#{i}"
        cands_q[key] = cs
        rels_q[key] = [Rel(cs[r["s"]] if r["sc"] else r["s"], r["p"], cs[r["o"]] if r["oc"] else r["o"], r["ev"]) for r in q["rels"]]
cands_f, rels_f = consolidar(cands_q, gaz, rels_q)

backend = OllamaBackend(a.llm) if a.llm else None
saida = RAIZ / "eval" / "predicoes" / a.estrategia
saida.mkdir(parents=True, exist_ok=True)
tempo_quadros, tempo_llm, resumo = 0.0, 0.0, {}
for stem, qs in selec.items():
    ents: dict[str, dict] = {}
    # dicionário: o nome precisa aparecer em `min-quadros` quadros
    votos: dict[str, int] = {}
    for q in qs:
        for nome in q["dic"]:
            votos[nome] = votos.get(nome, 0) + 1
    for nome, v in votos.items():
        if v >= a.min_quadros:
            ents[nome] = {"nome": nome, "tipo": gaz.tipo[nome], "evidencia": f"OCR em {v} quadro(s)"}
    # estrutura: missões, decisões e itens; variações de decisão do mesmo clipe viram a mais frequente
    contagem: dict[tuple, int] = {}
    for i in range(len(qs)):
        for c in cands_f[f"{stem}#{i}"]:
            k = (c.nome, c.tipo, c.estado, c.subtipo)
            contagem[k] = contagem.get(k, 0) + 1
    dec = sorted([k for k in contagem if k[1] == "decisao"], key=lambda k: -contagem[k])
    descartada = set()
    for i, k in enumerate(dec):
        for m in dec[:i]:
            if m not in descartada and SequenceMatcher(None, norm(k[0]), norm(m[0])).ratio() >= 0.8:
                descartada.add(k)
    for k, v in contagem.items():
        if k in descartada or (k[1] == "decisao" and v < 2 and not a.quadro_unico):
            continue  # opção de diálogo lida em um quadro só costuma ser ruído de legenda
        e = {"nome": k[0], "tipo": k[1], "evidencia": f"estrutura em {v} quadro(s)"}
        if k[2]:
            e["estado"] = k[2]
        if k[3]:
            e["subtipo"] = k[3]
        ents.setdefault(k[0], e)
    rels, vistas = [], set()
    for i in range(len(qs)):
        for r in rels_f.get(f"{stem}#{i}", []):
            t = (r["sujeito"], r["predicado"], r["objeto"])
            if t not in vistas and r["sujeito"] in ents and r["objeto"] in ents:
                vistas.add(t)
                rels.append({k: r[k] for k in ("sujeito", "predicado", "objeto", "evidencia")})
    tempo_quadros += sum(q["tempo_s"] for q in qs)
    # LLM: uma chamada por clipe, com as linhas distintas de todos os quadros usados
    if backend:
        agg: dict[str, list[str]] = {}
        visto: set = set()
        for q in qs:
            for sec, txt in q["secoes"].items():
                for l in txt.splitlines():
                    k = (sec, norm(l))
                    if l.strip() and len(norm(l)) >= 4 and k not in visto:
                        visto.add(k)
                        agg.setdefault(sec, []).append(l.strip())
        secoes = {sec: "\n".join(ls[:60]) for sec, ls in agg.items()}
        base = [(e["nome"], e["tipo"]) for e in ents.values()]
        out, meta = backend.extrair(secoes, [f"{t}: {n}" for n, t in base])
        res = normalizar(out, gaz, base, "\n".join(secoes.values()))
        tempo_llm += meta["tempo_s"]
        for e in res.entidades:
            ents.setdefault(e["nome"], {**e, "evidencia": "LLM"})
        for r in res.relacoes:
            t = (r["sujeito"], r["predicado"], r["objeto"])
            if t not in vistas:
                vistas.add(t)
                rels.append(r)
    pred = {"arquivo": next(m.name for s, m in clipes if s == stem), "tipo_tela": "outro", "entidades": list(ents.values()), "relacoes": rels, "observacoes": ""}
    (saida / f"{stem}.json").write_text(json.dumps(pred, ensure_ascii=False, indent=2), encoding="utf-8")
    resumo[stem] = {"quadros": len(qs), "entidades": len(ents), "relacoes": len(rels)}
n_q = sum(len(q) for q in selec.values())
(saida / "_execucao.json").write_text(json.dumps({
    "estrategia": a.estrategia, "intervalo_s": a.intervalo, "quadro_unico": a.quadro_unico, "min_quadros": a.min_quadros,
    "llm": a.llm, "clipes": len(clipes), "quadros": n_q, "tempo_quadros_s": round(tempo_quadros, 1), "tempo_llm_s": round(tempo_llm, 1),
    "tempo_por_quadro_s": round(tempo_quadros / max(n_q, 1), 2), "por_clipe": resumo}, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"{len(clipes)} clipes, {n_q} quadros; OCR e regras {tempo_quadros:.0f}s, LLM {tempo_llm:.0f}s -> {saida}")
