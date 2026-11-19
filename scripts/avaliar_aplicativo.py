"""Mede o aplicativo de ponta a ponta contra o gabarito, em dados isolados (não toca nos seus jogos nem na sua configuração).
Conjuntos (pastas de data/raw, com todas as capturas e vídeos que houver nelas):
  all        data/raw/all: todas as screenshots e vídeos
  reduzido   data/raw/escopo_reduzido: 15 capturas com gabarito, mais rápido
O gabarito (data/gabarito) só cobre parte das mídias; as demais são processadas, mas não entram na nota.
Configurações (rodadas na mesma pasta de dados, a segunda reaproveita a leitura da primeira):
  sem_ia     OCR e nomes aprendidos
  com_ia     o mesmo, com a IA pedida
Uso: python scripts/avaliar_aplicativo.py [--conjunto all|reduzido] [--ia ollama:qwen2.5:7b] [--so sem_ia,com_ia] [--timeout 3600]
Saída: relatório na tela, eval/resultado_<conjunto>.json, as anotações em eval/predicoes/<conjunto>_<configuração>/ e o vault gerado de cada
configuração em eval/vaults/<conjunto>_<configuração>/ (abra uma dessas pastas no Obsidian para comparar só OCR com OCR + IA)."""
import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PY = sys.executable
EXT_MIDIA = {".jpg", ".jpeg", ".png", ".mp4", ".mkv", ".mov", ".webm"}

ap = argparse.ArgumentParser()
ap.add_argument("--conjunto", choices=["all", "reduzido"], default="all")
ap.add_argument("--ia", default="ollama:qwen2.5:7b", help="provedor[:modelo]")
ap.add_argument("--so", default="sem_ia,com_ia", help="configurações a rodar, separadas por vírgula")
ap.add_argument("--timeout", type=int, default=3600, help="tempo máximo, em segundos, de cada configuração")
a = ap.parse_args()

dados = Path(tempfile.mkdtemp(prefix="gamemind_aval_"))
capturas = dados / "capturas"
capturas.mkdir()
pasta_conjunto = RAIZ / "data" / "raw" / ("all" if a.conjunto == "all" else "escopo_reduzido")
origem = sorted(f for f in pasta_conjunto.rglob("*") if f.is_file() and f.suffix.lower() in EXT_MIDIA)
for f in origem:
    try:
        os.link(f, capturas / f.name)
    except OSError:
        shutil.copy2(f, capturas / f.name)
env = {**os.environ, "GAMEMIND_DADOS": str(dados), "PYTHONIOENCODING": "utf-8"}
print(f"conjunto {a.conjunto}: {len(origem)} mídias; IA: {a.ia}", flush=True)


def avaliar(pred: Path) -> dict:
    rel = subprocess.run([PY, str(RAIZ / "eval" / "avaliar.py"), "--pred", str(pred)], capture_output=True, text=True, encoding="utf-8", cwd=RAIZ).stdout
    res = {}
    for chave, nome in (("entidades", "Entidades"), ("relacoes", "Relações")):
        m = re.search(rf"TOTAL {nome}.*?precisão=([\d.]+) revocação=([\d.]+) F1=([\d.]+)", rel)
        res[chave] = {"precisao": float(m[1]), "revocacao": float(m[2]), "f1": float(m[3])}
    res["por_tipo"] = {}
    for l in rel.split("Entidades por tipo de entidade")[1].split("Relações por predicado")[0].splitlines():
        m = re.match(r"\s+(\w+)\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)", l)
        if m:
            res["por_tipo"][m[1]] = {"gabarito": int(m[2]), "previsto": int(m[3]), "acertos": int(m[4]), "f1": float(m[7])}
    return res


def rodar(config: str, ia: str) -> dict:
    t0 = time.perf_counter()
    try:
        r = subprocess.run([PY, str(RAIZ / "gamemind.py"), "processar", "--jogo", "medida", "--pasta", str(capturas), "--ia", ia],
                           capture_output=True, text=True, encoding="utf-8", env=env, cwd=RAIZ, timeout=a.timeout)
    except subprocess.TimeoutExpired:
        return {"interrompido_por_tempo_s": a.timeout}
    if r.returncode:
        sys.exit(f"falhou ({config}): {r.stderr[-1500:]}")
    dt = time.perf_counter() - t0
    pred = RAIZ / "eval" / "predicoes" / f"{a.conjunto}_{config}"
    shutil.rmtree(pred, ignore_errors=True)
    subprocess.run([PY, str(RAIZ / "gamemind.py"), "exportar-anotacoes", "--jogo", "medida", "--saida", str(pred)], check=True, env=env, cwd=RAIZ,
                   capture_output=True)
    bd = sqlite3.connect(dados / "jogos" / "medida" / "gamemind.db")
    leitura = bd.execute("select sum(tempo_leitura_s) from midia").fetchone()[0] or 0
    estados = dict(bd.execute("select estado, count(*) from midia group by estado").fetchall())
    bd.close()
    vault = RAIZ / "eval" / "vaults" / f"{a.conjunto}_{config}"
    shutil.rmtree(vault, ignore_errors=True)
    shutil.copytree(dados / "jogos" / "medida" / "vault", vault)   # a segunda configuração reescreve o vault: guarda uma cópia de cada
    grafo = re.search(r"grafo (\d+) nós e (\d+) arestas, (\d+) notas", r.stdout)
    nomes = json.loads((dados / "jogos" / "medida" / "dicionario.json").read_text(encoding="utf-8"))
    tok = re.search(r"tokens \{'entrada': (\d+), 'saida': (\d+)\}", r.stdout)
    return {"tempo_s": round(dt), "leitura_soma_s": round(leitura), "midias_lidas": estados.get("lida", 0), "midias_com_erro": estados.get("erro", 0),
            "entidades_no_grafo": int(grafo[1]) if grafo else 0, "relacoes_no_grafo": int(grafo[2]) if grafo else 0,
            "notas_no_vault": int(grafo[3]) if grafo else 0, "nomes_no_dicionario": len(nomes),
            "nomes_da_ia": sum(1 for v in nomes.values() if v.get("origem") == "ia"),
            "tokens_entrada": int(tok[1]) if tok else 0, "tokens_saida": int(tok[2]) if tok else 0, **avaliar(pred)}


resultado = {"data": time.strftime("%Y-%m-%d"), "conjunto": a.conjunto, "midias": len(origem), "ia": a.ia}
for config in a.so.split(","):
    print(f"{config}: rodando...", flush=True)
    resultado[config] = rodar(config, "nenhuma" if config == "sem_ia" else a.ia)
    print(json.dumps({k: v for k, v in resultado[config].items() if k != "por_tipo"}, ensure_ascii=False), flush=True)
saida = RAIZ / "eval" / f"resultado_{a.conjunto}.json"
saida.write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
shutil.rmtree(dados, ignore_errors=True)
print("resumo em", saida)
