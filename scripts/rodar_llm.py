"""Etapa B3b: relações e itens com um LLM local, em cascata sobre a extração estruturada (B3a).
Pré-requisito: `python scripts/rodar_extracao.py --estrategia estruturado --modo estruturado` e o Ollama em execução
(`ollama serve`) com o modelo baixado (`ollama pull qwen2.5:7b`).
Uso: python scripts/rodar_llm.py --modelo qwen2.5:7b --estrategia llm_qwen7b [--limite 5]
Saída: eval/predicoes/<estrategia>/ (base + LLM), <estrategia>_apenas_llm/ (só o LLM) e _execucao.json (tempos, tokens, VRAM)."""
import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))
from difflib import SequenceMatcher  # noqa: E402

from extracao.gazetteer import Gazetteer, norm  # noqa: E402
from extracao.llm import OllamaBackend, normalizar  # noqa: E402
from extracao.ocr import ocr_secoes  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--modelo", default="qwen2.5:7b")
ap.add_argument("--estrategia", default="llm_qwen7b")
ap.add_argument("--base", default="estruturado", help="estratégia em eval/predicoes/ usada como base e como dica para o LLM")
ap.add_argument("--sem-dicas", action="store_true", help="não passa ao LLM os nomes já detectados pela base")
ap.add_argument("--limite", type=int, default=0, help="processa só os N primeiros itens (teste)")
ap.add_argument("--gab", default=str(RAIZ / "data" / "gabarito"))
ap.add_argument("--raw", default=str(RAIZ / "data" / "raw"))
ap.add_argument("--gazetteer", default=str(RAIZ / "data" / "gazetteer" / "witcher3_ptbr.json"))
a = ap.parse_args()

gaz = Gazetteer(Path(a.gazetteer))
backend = OllamaBackend(a.modelo)
base_dir = RAIZ / "eval" / "predicoes" / a.base
out = RAIZ / "eval" / "predicoes" / a.estrategia
out_llm = RAIZ / "eval" / "predicoes" / f"{a.estrategia}_apenas_llm"
cache = RAIZ / "eval" / "cache_ocr"
for d in (out, out_llm, cache):
    d.mkdir(parents=True, exist_ok=True)

itens = []
for g in sorted(Path(a.gab).glob("*.json")):
    if g.name == "entidades.json":
        continue
    midia = next((p for p in Path(a.raw).glob(g.stem + ".*") if p.suffix.lower() in {".jpg", ".png"}), None)
    if midia and (base_dir / g.name).exists():
        itens.append((g, midia))
if a.limite:
    itens = itens[: a.limite]

tempos, tokens, descartes = {}, {"entrada": 0, "saida": 0}, {}
t0 = time.perf_counter()
por_item = {}
for i, (g, midia) in enumerate(itens, 1):
    c = cache / f"{g.stem}.json"
    if c.exists():
        secoes = json.loads(c.read_text(encoding="utf-8"))
    else:
        secoes = ocr_secoes(midia)
        c.write_text(json.dumps(secoes, ensure_ascii=False), encoding="utf-8")
    base = json.loads((base_dir / g.name).read_text(encoding="utf-8"))
    base_ents = [(e["nome"], e["tipo"]) for e in base["entidades"]]
    detectado = [] if a.sem_dicas else [f"{t}: {n}" for n, t in base_ents]
    saida, meta = backend.extrair(secoes, detectado)
    res = normalizar(saida, gaz, base_ents, "\n".join(secoes.values()))
    tempos[g.stem] = meta["tempo_s"]
    tokens["entrada"] += meta["tokens_entrada"]
    tokens["saida"] += meta["tokens_saida"]
    descartes[g.stem] = res.descartes
    por_item[g.stem] = (g, midia, base, res)
    print(f"[{i}/{len(itens)}] {g.stem}: {meta['tempo_s']}s, {len(res.entidades)} entidades, {len(res.relacoes)} relações", flush=True)

# variações de grafia do mesmo nome novo (ex.: "Arbustira" e "Arbusteira") viram a mais frequente do lote
conhecidos = {n for _, _, base, _ in por_item.values() for n in (e["nome"] for e in base["entidades"])} | set(gaz.tipo)
novos: dict[str, int] = {}
for _, _, _, res in por_item.values():
    for e in res.entidades:
        if e["nome"] not in conhecidos:
            novos[e["nome"]] = novos.get(e["nome"], 0) + 1
canon: dict[str, str] = {}
for n in sorted(novos, key=lambda x: (-novos[x], -len(x))):
    if n in canon:
        continue
    canon[n] = n
    for m in novos:
        if m not in canon and len(m) >= 6 and SequenceMatcher(None, norm(n), norm(m)).ratio() >= 0.85:
            canon[m] = n

for stem, (g, midia, base, res) in por_item.items():
    ents_llm, vistos = [], set()
    for e in res.entidades:
        nome = canon.get(e["nome"], e["nome"])
        if (nome, e["tipo"]) not in vistos:
            vistos.add((nome, e["tipo"]))
            ents_llm.append({"nome": nome, "tipo": e["tipo"]})
    rels_llm = [{**r, "sujeito": canon.get(r["sujeito"], r["sujeito"]), "objeto": canon.get(r["objeto"], r["objeto"])} for r in res.relacoes]
    pred_llm = {"arquivo": midia.name, "tipo_tela": "outro", "entidades": ents_llm, "relacoes": rels_llm, "observacoes": ""}
    (out_llm / g.name).write_text(json.dumps(pred_llm, ensure_ascii=False, indent=2), encoding="utf-8")
    # base + LLM: entidades somadas (a base manda no tipo), relações da base somadas às do LLM
    ents = list(base["entidades"])
    ja = {e["nome"] for e in ents}
    ents += [e for e in ents_llm if e["nome"] not in ja]
    rels = list(base.get("relacoes", []))
    ja_r = {(r["sujeito"], r["predicado"], r["objeto"]) for r in rels}
    rels += [r for r in rels_llm if (r["sujeito"], r["predicado"], r["objeto"]) not in ja_r]
    (out / g.name).write_text(json.dumps({**base, "entidades": ents, "relacoes": rels}, ensure_ascii=False, indent=2), encoding="utf-8")

vram = {}
try:
    with urllib.request.urlopen("http://localhost:11434/api/ps", timeout=10) as r:
        for m in json.load(r).get("models", []):
            if m["name"] == a.modelo:
                vram = {"modelo": m["name"], "tamanho_total_gb": round(m["size"] / 2**30, 2), "vram_gb": round(m.get("size_vram", 0) / 2**30, 2)}
except Exception:
    pass
total = time.perf_counter() - t0
(out / "_execucao.json").write_text(json.dumps({"estrategia": a.estrategia, "backend": backend.nome, "base": a.base, "dicas": not a.sem_dicas, "itens": len(tempos),
    "tempo_total_s": round(total, 1), "tempo_medio_s": round(sum(tempos.values()) / max(len(tempos), 1), 2), "tokens": tokens, "memoria": vram,
    "tempos": tempos, "descartes": descartes}, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"{len(tempos)} itens em {total:.0f}s ({sum(tempos.values()) / max(len(tempos), 1):.1f}s por item); tokens {tokens}; memória {vram}")
