"""Orquestra uma rodada de processamento de um jogo: pasta de capturas -> leitura -> LLM -> consolidação -> grafo -> vault.
Sem interface gráfica: a janela e a CLI só chamam `Pipeline` e recebem o progresso por callback.
Pode ser interrompido entre mídias (`cancelar`); o que já foi lido fica no banco e não é refeito."""
import json
import logging
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from collections import Counter

from extracao.gazetteer import Gazetteer, norm
from extracao.ia_publica import ErroConector, criar_backend
from extracao.llm import OllamaBackend
from exportar_vault import PASTAS, arquivo, exportar
from grafo import fundir
from schema import Anotacao

from .config import Config
from .canvas import gerar as gerar_canvas
from .consolidacao import EVIDENCIA_LISTA, consolidar_base, entrada_llm, somar_llm, validar_llm
from .dicionario import aprender, carregar_manual, para_gazetteer, salvar, unificar
from .leitura import VERSAO_LEITURA, ler, recortes_desatualizados, reler_regioes
from . import chat, regioes as regioes_mod, resumos, visao
from .recursos import EXT_CLIPE, EXT_IMAGEM
from .repositorio import Midia, Jogo

log = logging.getLogger("gamemind")
MANIFESTO = ".gamemind-notas.json"  # arquivos que o GameMind gerou no vault (só esses são apagados quando somem do grafo)
TEMPO_CHAMADA_VISAO_S = 90.0        # uma captura que o modelo de imagem não responde nisso é deixada de lado
PRAZO_REGIOES_S = 120.0             # tempo total para aprender as regiões com o modelo de imagem (uma vez por jogo)
INTERVALO_PARCIAL_S = 5.0           # intervalo mínimo entre duas atualizações do vault no meio da rodada


@dataclass
class Progresso:
    etapa: str          # registro, regioes, leitura, llm, grafo, resumos, vault, fim
    feito: int = 0
    total: int = 0
    mensagem: str = ""
    arquivo: str = ""   # leitura: mídia que acabou de começar a ser lida; vault: nota ou canvas que acabou de ser gravado
    parcial: bool = False   # vault: gravado por uma atualização no meio da rodada (a etapa em andamento continua sendo outra)


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


def _apagar_do_vault(vault: Path, rel: str) -> bool:
    """Apaga um arquivo gerado (caminho relativo ao vault, nunca fora dele) e as pastas que ficarem vazias."""
    alvo = (vault / rel).resolve()
    if not alvo.is_relative_to(vault.resolve()) or not alvo.is_file():
        return False
    alvo.unlink()
    pasta = alvo.parent
    while pasta != vault.resolve() and pasta.is_dir() and not any(pasta.iterdir()):
        pasta.rmdir()
        pasta = pasta.parent
    return True


PASTAS_GERADAS = ("_midia", "_canvas")   # pastas que só o GameMind escreve no vault (_canvas: versões antigas)


def limpar(jogo: Jogo, tudo: bool = False) -> int:
    """Apaga do vault só o que o GameMind gerou (notas, canvas e miniaturas listados no manifesto) e o grafo; notas do usuário e a
    configuração do Obsidian (.obsidian) ficam. A próxima rodada refaz o vault com as leituras e respostas da IA já guardadas.
    `tudo`: volta o jogo ao estado de recém-criado (só a pasta de capturas fica): esquece mídias, leituras, respostas da IA,
    nomes aprendidos, resumos e regiões aprendidas, e apaga as pastas que só o GameMind usa no vault; a próxima rodada começa
    do zero, como num jogo novo. Só o que foi escrito à mão (`dicionario_manual.json`, região com "origem": "manual") fica.
    Devolve quantos arquivos do vault apagou."""
    vault = jogo.pasta_vault
    try:
        geradas = json.loads((vault / MANIFESTO).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        geradas = []
    n = sum(_apagar_do_vault(vault, rel) for rel in geradas)
    (vault / MANIFESTO).unlink(missing_ok=True)
    jogo.caminho_grafo.unlink(missing_ok=True)
    if tudo:
        for nome in PASTAS_GERADAS:
            pasta = vault / nome
            if pasta.is_dir():
                n += sum(1 for p in pasta.rglob("*") if p.is_file())
                shutil.rmtree(pasta)
        jogo.reiniciar()
        regioes_mod.esquecer_aprendidas(jogo.pasta)
        for nome in ("dicionario.json", resumos.ARQUIVO, chat.ARQUIVO):
            (jogo.pasta / nome).unlink(missing_ok=True)
    log.info("vault limpo: %d arquivo(s) gerados apagados%s", n, "; jogo reiniciado do zero" if tudo else "")
    return n


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
        self._ultimo_parcial = 0.0

    def _aprendiz(self, forcar: bool = False) -> regioes_mod.Aprendiz | None:
        """O aprendiz das regiões de leitura nesta rodada, se for o caso: uma vez por jogo (ou sempre, com `forcar`), só na rodada
        com IA. Com um modelo de imagem no Ollama (visao.py), ele vê cada captura com as linhas do OCR marcadas; sem ele, só se
        `aprender_regioes` estiver ligado, com a IA de texto. O resultado fica só no regioes.json deste jogo."""
        if (self.regioes.aprendida and not forcar) or not self.config.ia:
            return None   # "Processar só OCR" não usa IA nenhuma, nem a de imagem
        if len(self.jogo.midias()) < regioes_mod.MINIMO_CONVERGIR and not forcar:
            return None   # capturas de menos para concluir: nem carrega o modelo
        modelo = visao.escolher(self.config.modelo_visao) if self.config.regioes_por_imagem else ""
        if not modelo and not self.config.aprender_regioes:
            return None
        try:
            if modelo:
                backend = OllamaBackend(modelo)
                backend.timeout = TEMPO_CHAMADA_VISAO_S
                # o modelo (~6 GB) leva uns 20 s para carregar: carrega enquanto o OCR das primeiras capturas roda
                threading.Thread(target=backend.carregar, args=(True,), daemon=True).start()
            else:
                backend = criar_backend(self.config.ia)
        except (ErroConector, NotImplementedError) as e:
            log.warning("não foi possível aprender as regiões (ficam as atuais): %s", e)
            return None
        self._regioes_concluidas = False
        return regioes_mod.Aprendiz(backend, self.regioes, self.lang, visao.imagem_marcada if modelo else None,
                                    PRAZO_REGIOES_S if modelo else 0)

    def _alimentar(self, aprendiz: regioes_mod.Aprendiz, m: Midia, leitura: dict) -> None:
        """Passa uma captura recém-lida ao aprendiz; quando ele conclui, as regiões novas já valem para o que falta ler."""
        if aprendiz.terminou or not regioes_mod.parece_cena(leitura):
            return
        self.ao_progredir(Progresso("regioes", mensagem=f"aprendendo onde fica o texto com {m.nome}", arquivo=m.caminho))
        if aprendiz.considerar(m, leitura) and aprendiz.terminou:
            self._concluir_regioes(aprendiz)

    def _concluir_regioes(self, aprendiz: regioes_mod.Aprendiz) -> None:
        if self._regioes_concluidas:
            return
        self._regioes_concluidas = True
        r = aprendiz.resultado()
        if r is None:
            log.info("regiões: %d captura(s) de cena por enquanto; aprende numa próxima rodada", len(aprendiz.nomes))
            return
        self.regioes = r
        regioes_mod.salvar(self.jogo.pasta, r)
        log.info("regiões do jogo (%s, %d capturas, %s s%s): %s", r.meta.get("modelo"), r.meta.get("capturas_lidas"), r.meta.get("tempo_s"),
                 "" if r.meta.get("convergiu") else ", sem convergir", ", ".join(f"{n} ({o})" for n, o in r.origem.items()))

    def _atualizar_recortes(self) -> None:
        """Relê só os recortes que foram feitos com uma região que depois mudou (a tela inteira, a parte cara, fica)."""
        caixas = self.regioes.caixas
        faltam = [(m, l, n) for m, l in self.jogo.leituras() if (n := recortes_desatualizados(l, caixas))]
        if not faltam:
            return
        log.info("regiões mudaram: relendo os recortes de %d mídia(s)", len(faltam))

        def uma(item):
            m, l, nomes = item
            nova = None if self._cancelar.is_set() else reler_regioes(Path(m.caminho), m.tipo, l, {n: caixas[n] for n in nomes}, self.lang)
            return m, nova

        with ThreadPoolExecutor(max_workers=max(1, self.config.workers)) as ex:
            for feito, (m, nova) in enumerate(ex.map(uma, faltam), 1):
                if nova is not None:
                    self.jogo.gravar_leitura(m.id, nova, VERSAO_LEITURA, m.tempo_leitura_s)
                self.ao_progredir(Progresso("leitura", feito, len(faltam), f"relendo recortes: {m.nome}"))

    def _dicionario(self, extra: list[list[dict]] = (), guardar: bool = True) -> Gazetteer:
        """Reaprende o dicionário com o texto de todas as mídias do jogo (mais o das que acabaram de ser lidas) e o guarda
        em `dicionario.json` (se `guardar`). Nomes de `dicionario_manual.json`, se o usuário o criou, são somados."""
        quadros = [l["quadros"] for _, l in self.jogo.leituras()] + list(extra)
        ent = aprender(quadros) if self.config.aprender_dicionario else {}
        ent.update(carregar_manual(self.jogo.pasta))
        self.entidades = ent
        self.gaz = para_gazetteer(ent)
        if guardar:
            salvar(self.jogo.pasta, ent)
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
        self._ultimo_parcial = time.monotonic()
        self.ao_progredir(Progresso("registro", mensagem="procurando capturas novas"))
        for p in [Path(pasta)] if pasta else self.jogo.pastas():   # screenshots e vídeos
            if pasta or p.is_dir():
                rel.novas += self.registrar_pasta(p)
            else:
                log.warning("pasta de capturas não encontrada: %s", p)
        # OCR, com as regiões aprendidas durante a própria leitura (quando necessário) -> recortes desatualizados -> IA
        self.jogo.marcar_para_reler(VERSAO_LEITURA)
        aprendiz = self._aprendiz(self.forcar_regioes)
        self._ler_pendentes(rel, aprendiz)
        if aprendiz and not self._cancelar.is_set():
            if not aprendiz.terminou:   # o que foi lido agora não bastou: as leituras guardadas do jogo, em ordem sorteada
                leituras = self.jogo.leituras()
                for m, l in regioes_mod.ordem_sorteada(leituras, self.jogo.nome):
                    if aprendiz.terminou or self._cancelar.is_set():
                        break
                    self._alimentar(aprendiz, m, l)
            self._concluir_regioes(aprendiz)
        if not self._cancelar.is_set():
            self._atualizar_recortes()
        if not self._cancelar.is_set():
            self._gerar(rel)
        rel.cancelado = self._cancelar.is_set()
        rel.tempo_s = round(time.perf_counter() - t0, 1)
        self.ao_progredir(Progresso("fim", mensagem="cancelado" if rel.cancelado else "concluído"))
        return rel

    def _ler_pendentes(self, rel: Relatorio, aprendiz: regioes_mod.Aprendiz | None = None) -> None:
        """OCR das mídias pendentes. Com um `aprendiz`, cada captura lida que parece cena vai para ele logo em seguida, e a
        leitura segue em ordem sorteada (as primeiras amostras não vêm todas do mesmo trecho do jogo)."""
        pendentes = self.jogo.midias("pendente")
        if not pendentes:
            return
        if aprendiz:
            pendentes = regioes_mod.ordem_sorteada(pendentes, self.jogo.nome)
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
                if aprendiz:
                    self._alimentar(aprendiz, m, leitura)
            self.ao_progredir(Progresso("leitura", feito, total, m.nome))
            if leitura is not None:
                self._parcial()

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
        bruto = self._grafo(leituras, anotacoes, revisado=False)
        if self.config.ia and self.config.revisar_entidades and not self._cancelar.is_set():
            self._revisar(bruto, leituras, rel)
        dados = resumos.aplicar(bruto, resumos.carregar(self.jogo.pasta), set(carregar_manual(self.jogo.pasta)))
        self.jogo.caminho_grafo.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
        rel.nos, rel.arestas = len(dados["nos"]), len(dados["arestas"])
        rel.notas = self._exportar_vault(dados, self._midias_vault(leituras))
        log.info("grafo: %d nós, %d arestas; vault em %s", rel.nos, rel.arestas, self.jogo.pasta_vault)

    def _grafo(self, leituras: list[tuple[Midia, dict]], anotacoes: dict[int, dict], avisar: bool = True, revisado: bool = True) -> dict:
        """O grafo do jogo; `revisado`: com as revisões da IA já guardadas (resumos.py) aplicadas."""
        validas = []
        for m, _ in leituras:
            try:
                validas.append(Anotacao(**anotacoes[m.id]))
            except ValueError as e:
                if avisar:
                    log.warning("anotação inválida de %s ignorada: %s", m.nome, e)
        # formas do mesmo nome que só a IA trouxe, numa mídia cada ("Grifo" e "Grifos", "Capitão X" e "Comandante X"),
        # viram um nó só; o dicionário guardado não muda por isso
        canonicos = unificar(self.entidades, Counter(n for a in validas for n in {(e.nome, e.tipo) for e in a.entidades}),
                             set(carregar_manual(self.jogo.pasta)))
        dados = json.loads(fundir(validas, canonicos).model_dump_json())
        # relação vinda só de telas de lista, numa captura só: estar na mesma lista não basta
        dados["arestas"] = [a for a in dados["arestas"] if any(f["evidencia"] != EVIDENCIA_LISTA for f in a["fontes"])
                            or len({f["arquivo"] for f in a["fontes"]}) >= 2]
        if revisado:   # as revisões já guardadas; novas só na geração final (_revisar)
            resumos.aplicar(dados, resumos.carregar(self.jogo.pasta), set(carregar_manual(self.jogo.pasta)))
        return dados

    def _revisar(self, bruto: dict, leituras: list[tuple[Midia, dict]], rel: Relatorio) -> None:
        """Revisão e resumo de cada entidade pela IA, com o texto de todas as capturas dela (opcional; ver resumos.py)."""
        try:
            backend = criar_backend(self.config.ia)
        except (ErroConector, NotImplementedError):
            return
        rel.chamadas_llm += resumos.revisar(bruto, {m.nome: l for m, l in leituras}, backend, self.jogo.pasta,
                                            lambda i, n, nomes: self.ao_progredir(Progresso("resumos", i, n, f"{backend.nome}: {nomes}")),
                                            self._cancelar.is_set)

    @staticmethod
    def _midias_vault(leituras: list[tuple[Midia, dict]]) -> dict:
        return {m.nome: (Path(m.caminho), m.tipo, l) for m, l in leituras}

    def _parcial(self, respostas: dict[int, dict] | None = None) -> None:
        """Atualiza o vault no meio da rodada com o que já foi lido (e as respostas da IA que já existem), para as notas irem
        aparecendo enquanto o processamento anda. No máximo uma vez a cada INTERVALO_PARCIAL_S; nada é apagado aqui (a limpeza
        fica para a geração final) e uma falha só é registrada, sem interromper a rodada."""
        if self._cancelar.is_set() or time.monotonic() - self._ultimo_parcial < INTERVALO_PARCIAL_S:
            return
        try:
            leituras = self.jogo.leituras()
            if not leituras:
                return
            gaz = self._dicionario(guardar=False)
            base = consolidar_base(leituras, gaz)
            if respostas is None:
                respostas = self._respostas_guardadas(leituras)
            anotacoes = somar_llm(base, leituras, respostas, gaz) if respostas else base
            self._exportar_vault(self._grafo(leituras, anotacoes, avisar=False), self._midias_vault(leituras), parcial=True)
        except Exception as e:  # noqa: BLE001 - a prévia nunca derruba a rodada
            log.warning("não foi possível atualizar o vault no meio da rodada: %s", e)
        finally:
            self._ultimo_parcial = time.monotonic()

    def _respostas_guardadas(self, leituras: list[tuple[Midia, dict]]) -> dict[int, dict]:
        """Respostas que a IA configurada já deu em rodadas anteriores (sem chamar a IA)."""
        if not self.config.ia:
            return {}
        try:
            nome = criar_backend(self.config.ia).nome
        except (ErroConector, NotImplementedError):
            return {}
        return {m.id: r for m, _ in leituras if (r := self.jogo.llm(m.id, nome)) is not None}

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
        retipados = self._tipos_da_ia(respostas, gaz)
        if not novos and not retipados:
            return gaz
        self.entidades.update(novos)
        # a IA costuma trazer a forma completa de um nome que o dicionário já tem (ou que ela mesma trouxe noutra captura):
        # "Ravena" e "Ravena de Altamira" ficam um nome só, com a outra forma como apelido
        antes = len(self.entidades)
        self.entidades = unificar(self.entidades, {(n, v["tipo"]): v.get("midias", 1) for n, v in self.entidades.items()},
                                  set(carregar_manual(self.jogo.pasta)))
        salvar(self.jogo.pasta, self.entidades)
        log.info("a IA acrescentou %d nomes ao dicionário (%d juntados a outro nome)", len(novos), antes - len(self.entidades))
        self.gaz = para_gazetteer(self.entidades)
        return self.gaz

    def _tipos_da_ia(self, respostas: dict[int, dict], gaz: Gazetteer) -> dict[str, str]:
        """Corrige o tipo de nomes que o dicionário aprendeu pelo texto (indícios como "com X" erram: "sonhei com <lugar>") quando
        a IA dá outro tipo para o mesmo nome em duas ou mais capturas, na maioria delas. A resposta crua da IA é usada porque a
        validação já troca o tipo pelo do dicionário. Nomes do dicionário manual nunca mudam. Devolve {nome: tipo novo}."""
        manual = set(carregar_manual(self.jogo.pasta))
        votos: dict[str, Counter] = {}
        for saida in respostas.values():
            vistos = {}
            for e in saida.get("entidades", []):
                nome = gaz.termos.get(norm(e.get("nome") or ""))
                if nome and e.get("tipo") in ("personagem", "criatura", "local", "faccao"):
                    vistos.setdefault(nome, e["tipo"])   # um voto por captura
            for nome, tipo in vistos.items():
                votos.setdefault(nome, Counter())[tipo] += 1
        mudados = {}
        for nome, c in votos.items():
            tipo, n = c.most_common(1)[0]
            atual = self.entidades.get(nome, {}).get("tipo")
            if nome in self.entidades and nome not in manual and tipo != atual and n >= 2 and n > sum(c.values()) / 2:
                self.entidades[nome] = {**self.entidades[nome], "tipo": tipo, "tipo_pelo_texto": atual}
                mudados[nome] = tipo
        if mudados:
            log.info("a IA corrigiu o tipo de %d nome(s) do dicionário: %s", len(mudados), ", ".join(f"{n} -> {t}" for n, t in mudados.items()))
        return mudados

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
            self._parcial(respostas)
        return respostas

    def _exportar_vault(self, grafo: dict, midias: dict, parcial: bool = False) -> int:
        """Gera canvas, miniaturas e notas, e apaga só o que o GameMind gerou antes e não existe mais (o resto do vault fica).
        `parcial`: atualização no meio da rodada; não apaga nada, só acrescenta ao manifesto o que gravou."""
        vault = self.jogo.pasta_vault
        vault.mkdir(parents=True, exist_ok=True)
        try:
            antes = set(json.loads((vault / MANIFESTO).read_text(encoding="utf-8")))
        except (OSError, ValueError):
            antes = set()
        if not parcial:
            self.ao_progredir(Progresso("grafo", mensagem="desenhando o mundo da partida"))

        def gravado(caminho: Path) -> None:
            self.ao_progredir(Progresso("vault", mensagem=caminho.name, arquivo=str(caminho), parcial=parcial))

        anexos, secoes, extras = gerar_canvas(grafo, vault, midias, gravado)
        n = exportar(grafo, vault, anexos, gravado, secoes)
        geradas = {(Path(PASTAS[e["tipo"]]) / f"{arquivo(e['nome'])}.md").as_posix() for e in grafo["nos"]} | extras
        if parcial:
            geradas |= antes
        for velha in antes - geradas:
            _apagar_do_vault(vault, velha)   # e a pasta que ficou vazia (ex.: _canvas/ antigo)
        (vault / MANIFESTO).write_text(json.dumps(sorted(geradas), ensure_ascii=False, indent=0), encoding="utf-8")
        return n
