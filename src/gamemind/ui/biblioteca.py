"""Tela inicial: a biblioteca de jogos. Um cartão por jogo (capa = o ícone do .exe ou a captura mais recente do vault; o "⋯" abre
ou apaga o jogo) e, do mesmo tamanho, o cartão de adicionar jogo."""
from pathlib import Path

from PySide6.QtCore import QEvent, QFileInfo, QPoint, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QFileIconProvider, QGridLayout, QLabel, QMenu, QPushButton, QScrollArea, QVBoxLayout, QWidget

from ..nucleo.repositorio import Jogo
from . import aparencia
from .aparencia import arredondar

LARGURA, ALTURA = 220, 270   # todo cartão tem este tamanho, inclusive o de adicionar
CAPA = (188, 140)
ESPACO = 16          # grade de 8 px (Hydra Launcher)


def icone_do_exe(exe: str, tamanho: int = 128) -> QPixmap | None:
    """O ícone do executável do jogo, no maior tamanho que ele tiver (até `tamanho`)."""
    if not exe or not Path(exe).is_file():
        return None
    icone = QFileIconProvider().icon(QFileInfo(exe))
    tamanhos = [s for s in icone.availableSizes() if s.width() <= tamanho] or icone.availableSizes()
    lado = max((s.width() for s in tamanhos), default=tamanho)
    pix = icone.pixmap(lado, lado)
    if pix.isNull():
        return None
    # o Windows entrega até 48 px: ampliado com suavização para ter presença no cartão
    return pix.scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation) if pix.width() < 96 else pix


def capa(jogo: Jogo) -> QPixmap | None:
    """A capa do cartão: o ícone do .exe do jogo, se ele foi escolhido; senão, a miniatura mais recente que o GameMind gravou
    no vault (pasta _midia)."""
    exe = icone_do_exe(jogo.get("executavel", ""))
    if exe:
        return exe
    midia = jogo.pasta_vault / "_midia"
    imagens = sorted(midia.glob("*.jpg"), key=lambda p: p.stat().st_mtime, reverse=True) if midia.is_dir() else []
    pix = QPixmap(str(imagens[0])) if imagens else QPixmap()
    return None if pix.isNull() else pix.scaled(*CAPA, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation).copy(0, 0, *CAPA)


class Capa(QLabel):
    """A capa: a imagem recortada com os cantos do tema (raio_cartao), que a folha de estilo sozinha não arredonda; sem imagem,
    um símbolo."""

    def __init__(self, imagem: QPixmap | None, simbolo: str):
        super().__init__(objectName="capa", alignment=Qt.AlignCenter)
        self.setFixedSize(*CAPA)
        self.imagem = imagem
        if not imagem:
            self.setText(simbolo)

    def paintEvent(self, ev):
        super().paintEvent(ev)   # o fundo da folha de estilo (e o símbolo)
        if not self.imagem:
            return
        raio = aparencia.ATUAL.raio_cartao if aparencia.ATUAL else 4
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        contorno = QPainterPath()
        contorno.addRoundedRect(QRectF(self.rect()), raio, raio)
        p.setClipPath(contorno)
        x, y = (self.width() - self.imagem.width()) // 2, (self.height() - self.imagem.height()) // 2
        p.drawPixmap(x, y, self.imagem)
        p.end()


class Cartao(QPushButton):
    """Cartão da biblioteca: uma capa (imagem ou um símbolo), o nome e uma linha de detalhe. Com `acoes` [(texto, função)], um
    botão "⋯" no canto (e o clique com o botão direito) abre o menu delas."""

    def __init__(self, nome: str, detalhe: str, imagem: QPixmap | None = None, simbolo: str = "", acoes=()):
        super().__init__(objectName="cartao")
        self.setFixedSize(LARGURA, ALTURA)
        self.setCursor(Qt.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(8)
        self.capa = Capa(imagem, simbolo or nome[:1].upper())
        self.nome = QLabel(nome, objectName="pergunta", wordWrap=True)
        self.detalhe = QLabel(detalhe, objectName="apagado", wordWrap=True)
        for w in (self.capa, self.nome, self.detalhe):
            w.setAttribute(Qt.WA_TransparentForMouseEvents)   # o clique é do cartão
            lay.addWidget(w)
        lay.addStretch()
        self.menu = None
        if acoes:
            self.menu = arredondar(QMenu(self))
            for texto, funcao in acoes:
                if texto == "-":
                    self.menu.addSeparator()
                else:
                    self.menu.addAction(texto, funcao)
            self.mais = QPushButton("⋯", self, objectName="mais", toolTip="Mais opções")
            self.mais.setFixedSize(32, 24)
            self.mais.setCursor(Qt.PointingHandCursor)
            self.mais.move(LARGURA - 16 - 32 - 8, 16 + 8)   # sobre o canto de cima da capa
            self.mais.clicked.connect(lambda: self.menu.exec(self.mais.mapToGlobal(QPoint(0, self.mais.height() + 4))))

    def contextMenuEvent(self, ev):
        if self.menu:
            self.menu.exec(ev.globalPos())

    # a folha de estilo dá aos botões uma altura mínima (a de um botão comum), que desfaria o tamanho fixo do cartão
    def sizeHint(self):
        return QSize(LARGURA, ALTURA)

    def minimumSizeHint(self):
        return QSize(LARGURA, ALTURA)

    def event(self, ev):
        feito = super().event(ev)
        if ev.type() in (QEvent.Polish, QEvent.StyleChange):   # a folha de estilo acabou de ser aplicada: o tamanho volta
            self.setFixedSize(LARGURA, ALTURA)
        return feito


class Biblioteca(QWidget):
    abrir = Signal(str)
    adicionar = Signal()
    apagar = Signal(str)

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(QLabel("[ BIBLIOTECA ]", objectName="secao"))
        lay.addWidget(QLabel("Escolha um jogo para continuar, ou adicione um novo.", objectName="apagado"))
        self.rolagem = QScrollArea(widgetResizable=True)
        self.grade_w = QWidget(objectName="grade")
        self.grade_w.setAttribute(Qt.WA_TranslucentBackground)
        self.grade = QGridLayout(self.grade_w)
        self.grade.setSpacing(ESPACO)
        self.grade.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.rolagem.setWidget(self.grade_w)
        self.rolagem.viewport().setAutoFillBackground(False)
        self.grade_w.setAutoFillBackground(False)
        lay.addWidget(self.rolagem, 1)
        self.cartoes: list[Cartao] = []
        self.recarregar()

    def recarregar(self) -> None:
        for c in self.cartoes:
            c.setParent(None)
            c.deleteLater()
        self.cartoes = []
        for nome in Jogo.listar():
            jogo = Jogo.abrir(nome)
            try:
                r = jogo.resumo()
                detalhe = f"{r['lida']} captura(s) lida(s)" + (f", {r['pendente']} nova(s)" if r["pendente"] else "")
                c = Cartao(jogo.nome, detalhe, capa(jogo), acoes=[("Abrir", lambda _=False, n=nome: self.abrir.emit(n)), ("-", None),
                                                                  ("Apagar jogo...", lambda _=False, n=nome: self.apagar.emit(n))])
            finally:
                jogo.fechar()
            c.clicked.connect(lambda _=False, n=nome: self.abrir.emit(n))
            self.cartoes.append(c)
        mais = Cartao("Adicionar jogo", "Pastas e leitura", simbolo="+")
        mais.clicked.connect(self.adicionar.emit)
        self.cartoes.append(mais)
        self._distribuir()

    def _distribuir(self) -> None:
        # pela largura da própria biblioteca: a da área de rolagem ainda não foi ajustada quando esta é redimensionada
        colunas = max(1, (self.width() - 40 + ESPACO) // (LARGURA + ESPACO))
        for i, c in enumerate(self.cartoes):
            self.grade.addWidget(c, i // colunas, i % colunas)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._distribuir()


__all__ = ["Biblioteca", "Cartao", "capa"]
