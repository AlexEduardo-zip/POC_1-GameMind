"""Janela de espera: enquanto algo demorado roda (testar a IA, procurar o modelo de imagem, verificar o computador, terminar a
leitura ao sair), uma janela modal mostra o que está sendo feito, passo a passo, e nada mais pode ser clicado. Assim não há duas
ações ao mesmo tempo nem a interface parada esperando: o trabalho roda numa thread e a janela fecha sozinha ao terminar."""
import html

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QVBoxLayout

from . import aparencia
from .aparencia import Carregando, brilhar
from .tarefas import Funcao, em_thread
from .temas import valores


class Espera(QDialog):
    """`Espera(pai, titulo, passos).executar(funcao, *args, avisar=False)` -> (deu certo, resultado ou mensagem de erro).
    Com `avisar=True`, a função recebe `avisar(i)` e o passo i aparece em andamento (os anteriores, feitos)."""

    def __init__(self, pai, titulo: str, passos: list[str] | tuple[str, ...], explicacao: str = ""):
        super().__init__(pai)
        self.setModal(True)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)   # só o painel arredondado aparece
        self.setMinimumWidth(440)
        self.passos, self.atual, self.resultado = list(passos), 0, (False, "interrompido")
        self._terminou = False
        painel = QFrame(objectName="painel")
        lay = QVBoxLayout(painel)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(8)
        topo = QHBoxLayout()
        self.girando = Carregando(22)
        topo.addWidget(self.girando)
        topo.addSpacing(8)
        topo.addWidget(QLabel(titulo, objectName="pergunta", wordWrap=True), 1)
        lay.addLayout(topo)
        if explicacao:
            lay.addWidget(QLabel(explicacao, objectName="apagado", wordWrap=True))
        lay.addSpacing(8)
        self.rotulos = [QLabel(textFormat=Qt.RichText, wordWrap=True) for _ in self.passos]
        for r in self.rotulos:
            lay.addWidget(r)
        fora = QVBoxLayout(self)
        fora.setContentsMargins(16, 16, 16, 16)   # espaço para o brilho do painel
        fora.addWidget(painel)
        brilhar(painel)
        self._desenhar()

    def executar(self, funcao, *args, avisar: bool = False) -> tuple[bool, object]:
        f = Funcao(funcao, *args, avisar=avisar)
        f.passo.connect(self._passo)        # métodos (não lambdas): rodam na thread da interface
        f.concluido.connect(self._concluido)
        f.falhou.connect(self._falhou)
        em_thread(f)
        self.girando.iniciar()
        self.exec()
        self.girando.parar()
        self.deleteLater()
        return self.resultado

    def _desenhar(self) -> None:
        v = valores(aparencia.ATUAL) if aparencia.ATUAL else None
        for i, (rotulo, passo) in enumerate(zip(self.rotulos, self.passos)):
            if i < self.atual:
                marca, cor = "✓", v and v["hover"]
            elif i == self.atual:
                marca, cor = "●", v and v["destaque"]
            else:
                marca, cor = "○", v and v["apagado"]
            estilo = f' style="color:{cor}"' if cor else ""
            texto = f"<b>{html.escape(passo)}</b>" if i == self.atual else html.escape(passo)
            rotulo.setText(f"<span{estilo}>{marca}</span>&nbsp;&nbsp;{texto}")

    @Slot(int)
    def _passo(self, i: int) -> None:
        self.atual = max(self.atual, i)
        self._desenhar()

    @Slot(object)
    def _concluido(self, r) -> None:
        self._fim((True, r))

    @Slot(str)
    def _falhou(self, erro: str) -> None:
        self._fim((False, erro))

    def _fim(self, resultado) -> None:
        self.resultado, self._terminou = resultado, True
        self.atual = len(self.passos)
        self._desenhar()
        self.accept()

    def reject(self):   # Esc e o fechar da janela não interrompem: o trabalho termina sozinho
        if self._terminou:
            super().reject()

    def done(self, r):
        if self._terminou:
            super().done(r)


__all__ = ["Espera"]
