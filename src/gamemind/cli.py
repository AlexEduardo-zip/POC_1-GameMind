"""Linha de comando do aplicativo: o mesmo núcleo da janela, sem interface (é também o protótipo integrado pasta -> vault).
  python gamemind.py                                   abre a janela
  python gamemind.py processar --jogo w3 --pasta "C:/.../Screenshots" [--ia ollama] [--observar]
  python gamemind.py jogos                             lista os jogos (cada um com a pasta jogos/<nome>/vault)
  python gamemind.py diagnostico [--ia claude-code]    verifica Tesseract, FFmpeg e IA
  python gamemind.py exportar-anotacoes --jogo w3 --saida eval/predicoes/app   (para eval/avaliar.py)"""
import argparse
import json
import logging
import sys
import time
from pathlib import Path

from .nucleo.config import Config
from .nucleo.diagnostico import verificar
from .nucleo.observador import Observador
from .nucleo.pipeline import Pipeline, Progresso, Relatorio, limpar
from .nucleo.repositorio import Jogo


def _progresso(p: Progresso) -> None:
    if p.parcial:   # notas gravadas no meio da rodada não interrompem a linha de progresso
        return
    if p.total:
        print(f"\r[{p.etapa}] {p.feito}/{p.total} {p.mensagem[:50]:<50}", end="", flush=True)
        if p.feito == p.total:
            print()
    elif p.etapa != "fim":
        print(f"[{p.etapa}] {p.mensagem}")


def _imprimir(rel: Relatorio) -> None:
    print(f"\nnovas {rel.novas}, lidas {rel.lidas}, erros {rel.erros}, chamadas ao LLM {rel.chamadas_llm} (tokens {rel.tokens}); "
          f"grafo {rel.nos} nós e {rel.arestas} arestas, {rel.notas} notas; {rel.tempo_s} s" + (" [CANCELADO]" if rel.cancelado else ""))
    if rel.erro_llm:
        print(f"aviso da IA: {rel.erro_llm}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="gamemind", description="GameMind: grafo de conhecimento a partir das capturas dos seus jogos")
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("processar", help="lê as capturas novas da pasta e atualiza grafo e vault")
    p.add_argument("--jogo", required=True, help="nome do jogo (criado se não existir)")
    p.add_argument("--pasta", help="pasta de capturas (fica guardada no jogo)")
    p.add_argument("--ia", help="provedor[:modelo] ou 'nenhuma' (fica guardado na configuração); ver docs/ia-publica.md")
    p.add_argument("--workers", type=int)
    p.add_argument("--aprender-regioes", action="store_true", help="refina com a IA local as regiões de leitura do jogo (por padrão ficam as genéricas)")
    p.add_argument("--reaprender-regioes", action="store_true", help="refaz com a IA as regiões de leitura do jogo (regioes.json)")
    p.add_argument("--sem-aprender", action="store_true", help="não aprende o dicionário de nomes (usa só dicionario_manual.json, se houver)")
    p.add_argument("--observar", action="store_true", help="depois de processar, observa a pasta e processa o que chegar")
    sub.add_parser("jogos", help="lista os jogos")
    d = sub.add_parser("diagnostico", help="verifica as dependências")
    d.add_argument("--ia")
    lp = sub.add_parser("limpar", help="apaga do vault o que o GameMind gerou, para refazer na próxima rodada")
    lp.add_argument("--jogo", required=True)
    lp.add_argument("--tudo", action="store_true", help="reinicia o jogo do zero: esquece mídias, leituras, respostas da IA, nomes e regiões aprendidos")
    e = sub.add_parser("exportar-anotacoes", help="grava a anotação de cada mídia em JSON (formato do gabarito)")
    e.add_argument("--jogo", required=True)
    e.add_argument("--saida", required=True)
    a = ap.parse_args(argv)

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    cfg = Config.carregar()
    if a.cmd is None:
        from .ui.janela import iniciar
        return iniciar()
    if a.cmd == "jogos":
        for n in Jogo.listar():
            print(n)
        return 0
    if a.cmd == "diagnostico":
        falta = False
        for it in verificar(a.ia if a.ia is not None else cfg.ia, cfg.idioma_ocr):
            print(f"[{'ok' if it.ok else 'FALTA' if it.obrigatorio else 'aviso'}] {it.nome}: {it.detalhe}")
            falta |= it.obrigatorio and not it.ok
        print(f"\njogos em: {Jogo.raiz()}")
        return 1 if falta else 0
    if a.cmd == "limpar":
        if a.jogo not in Jogo.listar():
            print(f"jogo não encontrado: {a.jogo}", file=sys.stderr)
            return 2
        part = Jogo.abrir(a.jogo)
        n = limpar(part, a.tudo)
        part.fechar()
        print(f"{n} arquivo(s) gerados apagados do vault" + ("; jogo reiniciado do zero (só a pasta de capturas ficou)" if a.tudo else ""))
        return 0
    if a.cmd == "exportar-anotacoes":
        part = Jogo.abrir(a.jogo)
        saida = Path(a.saida)
        saida.mkdir(parents=True, exist_ok=True)
        anotacoes = part.anotacoes()
        for m in part.midias():
            if m.id in anotacoes:
                (saida / f"{Path(m.nome).stem}.json").write_text(json.dumps(anotacoes[m.id], ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{len(anotacoes)} anotações em {saida}")
        return 0

    part = Jogo.abrir(a.jogo)
    if a.pasta:
        part.set("pasta_capturas", str(Path(a.pasta).resolve()))
    if a.ia is not None:
        cfg.ia = "" if a.ia.lower() in ("", "nenhuma", "nenhum") else a.ia
    if a.workers:
        cfg.workers = a.workers
    cfg.aprender_dicionario = not a.sem_aprender
    cfg.aprender_regioes = a.aprender_regioes or a.reaprender_regioes
    cfg.ultimo_jogo = part.nome
    cfg.salvar()
    if not part.get("pasta_capturas"):
        print("informe a pasta de capturas com --pasta na primeira vez", file=sys.stderr)
        return 2
    pipe = Pipeline(part, cfg, _progresso)
    pipe.forcar_regioes = a.reaprender_regioes
    _imprimir(pipe.processar())
    print(f"vault: {part.pasta_vault}")
    if a.observar:
        obs = Observador(Path(part.get("pasta_capturas")), intervalo_s=cfg.observar_intervalo_s,
                         ja_conhecidos={Path(m.caminho): m.tamanho for m in part.midias()})
        print(f"observando {obs.pasta} a cada {cfg.observar_intervalo_s} s (Ctrl+C para sair)")
        try:
            while True:
                time.sleep(cfg.observar_intervalo_s)
                if obs.consultar():
                    _imprimir(pipe.processar())
        except KeyboardInterrupt:
            pass
    return 0
