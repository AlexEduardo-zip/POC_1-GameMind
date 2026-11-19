"""Ponte entre o núcleo (threads comuns, callbacks) e o Qt (sinais na thread da interface).
O processamento roda numa QThread; a interface só recebe sinais e nunca toca no banco durante a rodada."""
import logging
from dataclasses import asdict

from PySide6.QtCore import QObject, QThread, Signal

from ..nucleo.pipeline import Pipeline, Progresso


class Trabalhador(QObject):
    progresso = Signal(object)    # Progresso
    concluido = Signal(dict)      # Relatorio como dict
    falhou = Signal(str)

    def __init__(self, pipeline: Pipeline):
        super().__init__()
        self.pipeline = pipeline
        pipeline.ao_progredir = self.progresso.emit

    def rodar(self) -> None:
        try:
            self.concluido.emit(asdict(self.pipeline.processar()))
        except Exception as e:  # noqa: BLE001 - qualquer falha vira mensagem na janela
            logging.getLogger("gamemind").exception("falha no processamento")
            self.falhou.emit(f"{type(e).__name__}: {e}")


_VIVAS: list[QThread] = []   # as threads ficam referenciadas aqui até terminar: quem as criou pode sumir (uma janela que fechou)
#                              sem esperar por elas e sem que o Python destrua uma thread em andamento


def em_andamento() -> list[QThread]:
    return [t for t in _VIVAS if t.isRunning()]


def em_thread(trabalho: QObject, metodo: str = "rodar") -> QThread:
    """Move `trabalho` para uma QThread nova, roda `metodo` e encerra a thread quando ele emitir concluido/falhou.
    Ligue os sinais de `trabalho` a métodos de um QObject (não a lambdas), para que rodem na thread da interface."""
    _VIVAS[:] = [x for x in _VIVAS if not x.isFinished()]
    t = QThread()
    _VIVAS.append(t)
    t._trabalho = trabalho   # mantém o objeto Python vivo enquanto a thread existir
    trabalho.moveToThread(t)
    t.started.connect(getattr(trabalho, metodo))
    for nome in ("concluido", "falhou"):
        if hasattr(trabalho, nome):
            getattr(trabalho, nome).connect(t.quit)
    t.finished.connect(trabalho.deleteLater)
    t.start()
    return t


class Funcao(QObject):
    """Roda uma função qualquer fora da thread da interface (ex.: teste de conexão com a IA). Com `avisar=True`, a função recebe
    `avisar(i)` e cada passo vira o sinal `passo`."""
    concluido = Signal(object)
    falhou = Signal(str)
    passo = Signal(int)

    def __init__(self, f, *args, avisar: bool = False):
        super().__init__()
        self.f, self.args, self.avisar = f, args, avisar

    def rodar(self) -> None:
        try:
            self.concluido.emit(self.f(*self.args, **({"avisar": self.passo.emit} if self.avisar else {})))
        except Exception as e:  # noqa: BLE001
            self.falhou.emit(f"{type(e).__name__}: {e}")


class _Emissor(QObject):
    linha = Signal(str)


class PonteLog(logging.Handler):
    """Encaminha o logging do núcleo (qualquer thread) para a aba Registro, pelo sinal `linha`."""

    def __init__(self):
        super().__init__(logging.INFO)
        self.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M:%S"))
        self._emissor = _Emissor()
        self.linha = self._emissor.linha

    def emit(self, record):
        self.linha.emit(self.format(record))


__all__ = ["Trabalhador", "Funcao", "PonteLog", "Progresso", "em_thread", "em_andamento"]
