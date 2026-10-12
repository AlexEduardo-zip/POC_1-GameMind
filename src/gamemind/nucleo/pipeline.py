"""Orquestra uma rodada de processamento de um jogo: pasta de capturas -> leitura -> LLM -> consolidação -> grafo -> vault.
Sem interface gráfica: a janela e a CLI só chamam `Pipeline` e recebem o progresso por callback.
Pode ser interrompido entre mídias (`cancelar`); o que já foi lido fica no banco e não é refeito."""
import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from collections import Counter

from extracao.gazetteer import Gazetteer
from extracao.ia_publica import ErroConector, criar_backend
from exportar_vault import PASTAS, arquivo, exportar
from grafo import fundir
from schema import Anotacao

from .config import Config
from .canvas import gerar as gerar_canvas
from .consolidacao import consolidar_base, entrada_llm, somar_llm, validar_llm
from .dicionario import aprender, carregar_manual, para_gazetteer, salvar
from .leitura import VERSAO_LEITURA, ler
from . import regioes as regioes_mod
from .recursos import EXT_CLIPE, EXT_IMAGEM
from .repositorio import Midia, Jogo

log = logging.getLogger("gamemind")
MANIFESTO = ".gamemind-notas.json"  # arquivos que o GameMind gerou no vault (só esses são apagados quando somem do grafo)


@dataclass
class Progresso:
    etapa: str          # registro, regioes, leitura, llm, grafo, vault, fim
    feito: int = 0
    total: int = 0
    mensagem: str = ""
    arquivo: str = ""   # leitura: mídia que acabou de começar a ser lida; vault: nota ou canvas que acabou de ser gravado


@dataclass
class Relatorio:
    novas: int = 0
    lidas: int = 0
    erros: int = 0
    chamadas_llm: int = 0
    tokens: dict = field(default_factory=lambda: {"entrada": 0, "saida": 0})
    erro_llm: str = ""
    nos: int = 0
    arestas: int = 0
    notas: int = 0
    tempo_s: float = 0.0
    cancelado: bool = False


def tipo_midia(caminho: Path) -> str | None:
    s = caminho.suffix.lower()
    return "imagem" if s in EXT_IMAGEM else "clipe" if s in EXT_CLIPE else None


class Pipeline:
    def __init__(self, jogo: Jogo, config: Config, ao_progredir: Callable[[Progresso], None] | None = None):
        self.jogo, self.config = jogo, config
        self.ao_progredir = ao_progredir or (lambda p: None)
        self.forcar_regioes = False
        self._cancelar = threading.Event()
        self.entidades: dict[str, dict] = {}   # dicionário de nomes do jogo (aprendido; ver dicionario.py)
        self.gaz = Gazetteer()
        self.regioes = regioes_mod.carregar(jogo.pasta)   # regiões de leitura do jogo (padrões genéricos, refinados pela IA; regioes.py)
        self.lang = config.idioma_ocr

    def aprender_regioes(self, forcar: bool = False) -> bool:
        """Refina as regiões de leitura com a IA local, uma vez por jogo (ou sempre, com `forcar`), quando o jogo já tem mídias
        suficientes. Devolve True se tentou aprender e conseguiu gravar o resultado."""
        ja = self.regioes.aprendida
        if (ja and not forcar) or not self.config.ia or not self.config.aprender_regioes:
            return False
        midias = self.jogo.midias()
        if len(midias) < regioes_mod.MINIMO_MIDIAS and not forcar:
            return False
        try:
            backend = criar_backend(self.config.ia)
            amostras, nomes = [], []
            self.ao_progredir(Progresso("regioes", mensagem="aprendendo onde ficam legenda, objetivo e avisos"))
            for m in regioes_mod.escolher_amostras(midias):
                quadro = regioes_mod.quadro_da_midia(Path(m.caminho), m.tipo)
                if quadro is not None:
                    amostras.append(regioes_mod.linhas_com_posicao(quadro, self.lang))
                    nomes.append(m.nome)
            self.regioes = regioes_mod.aprender(amostras, backend, self.regioes, nomes)
        except (ErroConector, NotImplementedError, OSError) as e:
            log.warning("não foi possível aprender as regiões (ficam as atuais): %s", e)
            return False
        regioes_mod.salvar(self.jogo.pasta, self.regioes)
        log.info("regiões do jogo: %s", ", ".join(f"{n} ({o})" for n, o in self.regioes.origem.items()))
        return True

    def _dicionario(self, extra: list[list[dict]] = ()) -> Gazetteer:
        """Reaprende o dicionário com o texto de todas as mídias do jogo (mais o das que acabaram de ser lidas) e o guarda
        em `dicionario.json`. Nomes de `dicionario_manual.json`, se o usuário o criou, são somados."""
        quadros = [l["quadros"] for _, l in self.jogo.leituras()] + list(extra)
        ent = aprender(quadros) if self.config.aprender_dicionario else {}
        ent.update(carregar_manual(self.jogo.pasta))
        self.entidades = ent
        salvar(self.jogo.pasta, ent)
        self.gaz = para_gazetteer(ent)
        log.info("dicionário do jogo: %d nomes", len(ent))
        return self.gaz

    def cancelar(self) -> None:
        self._cancelar.set()

    # ---- registro
    def registrar_pasta(self, pasta: Path | None = None, recursivo: bool = False) -> int:
        pasta = Path(pasta or self.jogo.get("pasta_capturas") or "")
        if not pasta.is_dir():
            raise FileNotFoundError(f"pasta de capturas não encontrada: {pasta}")
        novas = 0
        for p in sorted(pasta.rglob("*") if recursivo else pasta.iterdir()):
            t = tipo_midia(p) if p.is_file() else None
            if t and self.jogo.registrar(p, t):
                novas += 1
        log.info("%d mídia(s) nova(s) em %s", novas, pasta)
        return novas

    # ---- rodada completa
    def processar(self, pasta: Path | None = None) -> Relatorio:
        t0 = time.perf_counter()
        self._cancelar.clear()
        rel = Relatorio()
        self.ao_progredir(Progresso("registro", mensagem="procurando capturas novas"))
        if pasta or self.jogo.get("pasta_capturas"):
            rel.novas = self.registrar_pasta(pasta)
        self.aprender_regioes(self.forcar_regioes)
        self.jogo.marcar_para_reler(VERSAO_LEITURA)
        self._ler_pendentes(rel)
        if not self._cancelar.is_set():
            self._gerar(rel)
        rel.cancelado = self._cancelar.is_set()
        rel.tempo_s = round(time.perf_counter() - t0, 1)
        self.ao_progredir(Progresso("fim", mensagem="cancelado" if rel.cancelado else "concluído"))
        return rel

    def _ler_pendentes(self, rel: Relatorio) -> None:
        pendentes = self.jogo.midias("pendente")
        if not pendentes:
            return
        total, feito = len(pendentes), 0
        cfg = self.config
        self.ao_progredir(Progresso("leitura", 0, total, "lendo o texto das capturas"))

        def uma(m: Midia):
            if self._cancelar.is_set():
                return m, None, 0.0, None
            self.ao_progredir(Progresso("leitura", feito, total, m.nome, m.caminho))
            try:
                leitura, dt = ler(Path(m.caminho), m.tipo, cfg.intervalo_video_s, cfg.workers, cfg.idioma_ocr, self.regioes.caixas)
                return m, leitura, dt, None
            except Exception as e:  # noqa: BLE001 - a mídia vira 'erro' e a rodada continua
                return m, None, 0.0, e

        def registrar(m, leitura, dt, erro):
            nonlocal feito
            feito += 1
            if erro is not None:
                rel.erros += 1
                self.jogo.gravar_erro(m.id, f"{type(erro).__name__}: {erro}")
                log.warning("erro ao ler %s: %s", m.nome, erro)
            elif leitura is not None:
                rel.lidas += 1
                self.jogo.gravar_leitura(m.id, leitura, VERSAO_LEITURA, dt)
                log.info("lida %s (%.1f s)", m.nome, dt)
            self.ao_progredir(Progresso("leitura", feito, total, m.nome))

        # imagens em paralelo; clipes um por vez (cada clipe já paraleliza os próprios quadros)
        imagens = [m for m in pendentes if m.tipo == "imagem"]
        with ThreadPoolExecutor(max_workers=max(1, cfg.workers)) as ex:
            for f in as_completed([ex.submit(uma, m) for m in imagens]):
                registrar(*f.result())
        for m in (m for m in pendentes if m.tipo == "clipe"):
            registrar(*uma(m))

    def _gerar(self, rel: Relatorio) -> None:
        leituras = self.jogo.leituras()
        self.ao_progredir(Progresso("grafo", mensagem="consolidando o jogo"))
        gaz = self._dicionario()
        base = consolidar_base(leituras, gaz)
        respostas = self._llm(leituras, base, rel) if self.config.ia else {}
        if respostas:
            gaz = self._aprender_com_ia(base, leituras, respostas, gaz)
            base = consolidar_base(leituras, gaz)
        anotacoes = somar_llm(base, leituras, respostas, gaz) if respostas else base
        self.jogo.gravar_anotacoes(anotacoes)

        validas = []
        for m, _ in leituras:
            try:
                validas.append(Anotacao(**anotacoes[m.id]))
            except ValueError as e:
                log.warning("anotação inválida de %s ignorada: %s", m.nome, e)
        g = fundir(validas, self.entidades)
        dados = json.loads(g.model_dump_json())
        self.jogo.caminho_grafo.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
        rel.nos, rel.arestas = len(g.nos), len(g.arestas)
        rel.notas = self._exportar_vault(dados, {m.nome: (Path(m.caminho), m.tipo, l) for m, l in leituras})
        log.info("grafo: %d nós, %d arestas; vault em %s", rel.nos, rel.arestas, self.jogo.pasta_vault)

    def _aprender_com_ia(self, base, leituras, respostas, gaz: Gazetteer) -> Gazetteer:
        """Nomes que o LLM achou (e a validação aceitou) em duas ou mais mídias entram no dicionário, para serem reconhecidos
        também nas capturas onde o LLM não foi chamado ou não os viu."""
        achados: dict[str, Counter] = {}
        for r in validar_llm(base, leituras, respostas, gaz).values():
            for e in r.entidades:
                if e["tipo"] in ("personagem", "criatura", "local", "faccao") and e["nome"] not in gaz.tipo:
                    achados.setdefault(e["nome"], Counter())[e["tipo"]] += 1
        novos = {n: {"tipo": c.most_common(1)[0][0], "aliases": [], "midias": sum(c.values()), "origem": "ia"}
                 for n, c in achados.items() if sum(c.values()) >= 2}
        if not novos:
            return gaz
        self.entidades.update(novos)
        salvar(self.jogo.pasta, self.entidades)
        log.info("a IA acrescentou %d nomes ao dicionário", len(novos))
        self.gaz = para_gazetteer(self.entidades)
        return self.gaz

    def _llm(self, leituras: list[tuple[Midia, dict]], base: dict[int, dict], rel: Relatorio) -> dict[int, dict]:
        """Respostas do LLM por mídia; só chama para as que ainda não têm resposta guardada desta IA."""
        try:
            backend = criar_backend(self.config.ia)
        except ErroConector as e:
            rel.erro_llm = str(e)
            log.error("IA indisponível, grafo gerado sem LLM: %s", e)
            return {}
        respostas, faltam = {}, []
        for m, l in leituras:
            r = self.jogo.llm(m.id, backend.nome)
            if r is None:
                faltam.append((m, l))
            else:
                respostas[m.id] = r
        for i, (m, l) in enumerate(faltam, 1):
            if self._cancelar.is_set():
                break
            self.ao_progredir(Progresso("llm", i - 1, len(faltam), f"{backend.nome}: {m.nome}", m.caminho))
            secoes, detectado = entrada_llm(l, base[m.id])
            try:
                saida, meta = backend.extrair(secoes, detectado)
            except (ErroConector, OSError) as e:
                rel.erro_llm = str(e)
                log.error("LLM parou em %s (o restante fica para a próxima rodada): %s", m.nome, e)
                break
            self.jogo.gravar_llm(m.id, backend.nome, saida, meta)
            respostas[m.id] = saida
            rel.chamadas_llm += 1
            rel.tokens["entrada"] += meta.get("tokens_entrada", 0)
            rel.tokens["saida"] += meta.get("tokens_saida", 0)
        return respostas

    def _exportar_vault(self, grafo: dict, midias: dict) -> int:
        """Gera canvas, miniaturas e notas, e apaga só o que o GameMind gerou antes e não existe mais (o resto do vault fica)."""
        vault = self.jogo.pasta_vault
        vault.mkdir(parents=True, exist_ok=True)
        try:
            antes = set(json.loads((vault / MANIFESTO).read_text(encoding="utf-8")))
        except (OSError, ValueError):
            antes = set()
        self.ao_progredir(Progresso("grafo", mensagem="desenhando os canvas"))
        def gravado(caminho: Path) -> None:
            self.ao_progredir(Progresso("vault", mensagem=caminho.name, arquivo=str(caminho)))

        anexos, extras = gerar_canvas(grafo, vault, midias, gravado)
        n = exportar(grafo, vault, anexos, gravado)
        geradas = {(Path(PASTAS[e["tipo"]]) / f"{arquivo(e['nome'])}.md").as_posix() for e in grafo["nos"]} | extras
        for velha in antes - geradas:
            (vault / velha).unlink(missing_ok=True)
        (vault / MANIFESTO).write_text(json.dumps(sorted(geradas), ensure_ascii=False, indent=0), encoding="utf-8")
        return n
