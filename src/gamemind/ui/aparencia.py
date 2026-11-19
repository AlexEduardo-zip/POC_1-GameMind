"""Aplica um tema (temas.py) à janela e oferece o seletor de tema. O mesmo código para todo tema: só os valores mudam."""
from PySide6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, QRectF, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QFrame, QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QMenu, QWidget

from .temas import TEMAS, Tema, folha, painel_visto

ATUAL: Tema | None = None   # o tema aplicado (os desenhos feitos em código, como o spinner e o olho, usam as cores dele)


def aplicar(janela: QWidget, t: Tema) -> None:
    """Folha de estilo do tema na aplicação inteira e o brilho dos painéis (cor e opacidade do tema; 0 = sem brilho)."""
    global ATUAL
    ATUAL = t
    QApplication.instance().setStyleSheet(folha(t))
    for painel in janela.findChildren(QFrame, "painel"):
        brilhar(painel, t)
    if hasattr(janela, "ao_mudar_tema"):   # a janela redesenha o que ela pinta em código (ícones)
        janela.ao_mudar_tema(t)


def brilhar(painel: QWidget, t: Tema | None = None) -> None:
    """O brilho em volta de um painel, na cor e opacidade do tema (0 = sem brilho)."""
    t = t or ATUAL
    if t is None:
        return
    cor = QColor(t.brilho)
    cor.setAlphaF(t.brilho_opacidade)
    efeito = painel.graphicsEffect()
    if not isinstance(efeito, QGraphicsDropShadowEffect):
        efeito = QGraphicsDropShadowEffect(painel)
        efeito.setOffset(0, 0)
        efeito.setBlurRadius(18)
        painel.setGraphicsEffect(efeito)
    efeito.setColor(cor)
    efeito.setEnabled(t.brilho_opacidade > 0)


def icone(t: Tema, largura: int = 64, altura: int = 36) -> QIcon:
    """Miniatura do tema: o fundo, um painel com a borda, uma faixa de destaque e um "Aa" na cor do texto."""
    pix = QPixmap(largura, altura)
    pix.fill(QColor(t.fundo))
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    caixa = QRectF(5, 5, largura - 10, altura - 10)
    p.setPen(QColor(t.borda))
    p.setBrush(QColor(painel_visto(t)))
    p.drawRoundedRect(caixa, min(t.raio, 6), min(t.raio, 6))
    p.fillRect(QRectF(caixa.left() + 4, caixa.bottom() - 7, caixa.width() * 0.5, 3), QColor(t.destaque))
    fonte = QFont()
    fonte.setPixelSize(11)
    fonte.setBold(True)
    p.setFont(fonte)
    p.setPen(QColor(t.texto))
    p.drawText(caixa.adjusted(4, 1, -4, -8), Qt.AlignLeft | Qt.AlignVCenter, "Aa")
    p.end()
    return QIcon(pix)


def arredondar(menu: QMenu) -> QMenu:
    """Menus são janelas próprias: sem fundo transparente, os cantos arredondados da folha de estilo ficariam com o fundo quadrado
    aparecendo. Chame logo ao criar o menu (antes de ele aparecer)."""
    menu.setWindowFlags(menu.windowFlags() | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
    menu.setAttribute(Qt.WA_TranslucentBackground)
    return menu


class MenuTemas(QMenu):
    """Submenu com os temas e a miniatura de cada um. Passar o mouse num tema já o mostra na janela; ao fechar o menu sem
    escolher, volta ao tema escolhido. `ao_mudar(chave, definitivo)` aplica o tema (e o grava quando `definitivo`)."""

    def __init__(self, pai: QWidget, atual: str, ao_mudar):
        super().__init__("Tema", pai)
        arredondar(self)
        self.ao_mudar, self.escolhido = ao_mudar, atual
        grupo = QActionGroup(self)
        for chave, t in TEMAS.items():
            a = QAction(icone(t), t.nome, self, checkable=True, checked=chave == atual)
            a.setData(chave)
            grupo.addAction(a)
            self.addAction(a)
        self.hovered.connect(lambda a: self.ao_mudar(a.data(), False))
        self.triggered.connect(self._escolher)
        # ao fechar, volta ao escolhido; depois do clique (o menu fecha antes de avisar a escolha), para não piscar o tema antigo
        self.aboutToHide.connect(lambda: QTimer.singleShot(0, lambda: self.ao_mudar(self.escolhido, False)))

    def _escolher(self, a: QAction):
        self.escolhido = a.data()
        self.ao_mudar(self.escolhido, True)


# ---------------------------------------------------------------- movimento e ícones (os mesmos para todo tema)
def aparecer(w: QWidget, ms: int = 220) -> None:
    """Transição: o widget surge esmaecendo (opacidade de 0 a 1). Use em telas e páginas, não num painel (que tem o brilho)."""
    efeito = QGraphicsOpacityEffect(w)
    w.setGraphicsEffect(efeito)
    anim = QPropertyAnimation(efeito, b"opacity", w)
    anim.setDuration(ms)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.OutCubic)
    anim.finished.connect(lambda: w.setGraphicsEffect(None))
    anim.start()
    w._transicao = anim   # mantém a animação viva


class Carregando(QWidget):
    """Indicador de "trabalhando": um arco girando na cor de destaque do tema. `iniciar()` mostra e gira; `parar()` esconde."""

    def __init__(self, tamanho: int = 18):
        super().__init__()
        self.setFixedSize(tamanho, tamanho)
        self._angulo = 0
        self._timer = QTimer(self, interval=16)
        self._timer.timeout.connect(self._girar)
        self.hide()

    def _girar(self):
        self._angulo = (self._angulo + 8) % 360
        self.update()

    def iniciar(self):
        self.show()
        self._timer.start()

    def parar(self):
        self._timer.stop()
        self.hide()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        caneta = QPen(QColor(ATUAL.destaque if ATUAL else "#3DA9FF"), 2.5)
        caneta.setCapStyle(Qt.RoundCap)
        p.setPen(caneta)
        p.drawArc(QRectF(2, 2, self.width() - 4, self.height() - 4), -self._angulo * 16, 270 * 16)
        p.end()


def logo(t: Tema, tamanho: int = 22) -> QPixmap:
    """O logo do GameMind: um "G" desenhado como um pequeno grafo (um arco com nós nas pontas e no meio, ligado a um nó central),
    em cima de um quadrado arredondado no destaque do tema. As cores vêm do tema, então o logo acompanha a troca de tema."""
    from .temas import texto_sobre_destaque
    escala = 4
    s = tamanho * escala
    pix = QPixmap(s, s)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(t.destaque))
    p.drawRoundedRect(QRectF(0, 0, s, s), s * 0.24, s * 0.24)
    frente = QColor(texto_sobre_destaque(t))
    c, r = s / 2, s * 0.29
    caneta = QPen(frente, s * 0.07)
    caneta.setCapStyle(Qt.RoundCap)
    p.setPen(caneta)
    p.setBrush(Qt.NoBrush)
    caixa = QRectF(c - r, c - r, 2 * r, 2 * r)
    p.drawArc(caixa, 40 * 16, 320 * 16)                       # o "G": da ponta de cima, pela esquerda, até a direita
    p.drawLine(QPointF(c + r, c), QPointF(c + r * 0.12, c))   # a barra do "G", até o nó central
    p.setPen(Qt.NoPen)
    from math import cos, radians, sin
    nos = ((c + r * cos(radians(40)), c - r * sin(radians(40)), 0.09),   # ponta de cima do arco
           (c - r * cos(radians(35)), c + r * sin(radians(35)), 0.075),  # embaixo, à esquerda
           (c + r * 0.12, c, 0.105))                                      # nó central
    for cor, folga in ((QColor(t.destaque), 0.035), (frente, 0.0)):       # um respiro em volta de cada nó, depois o nó
        p.setBrush(cor)
        for x, y, raio in nos:
            p.drawEllipse(QPointF(x, y), s * (raio + folga), s * (raio + folga))
    p.end()
    pix.setDevicePixelRatio(escala)
    return pix


def icone_olho(cor: str, tamanho: int = 20) -> QIcon:
    """Um olho desenhado na cor dada (nítido em telas de alta densidade)."""
    escala = 3
    w, h = tamanho * escala, tamanho * escala
    pix = QPixmap(w, h)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor(cor), 1.8 * escala))
    olho = QPainterPath(QPointF(w * 0.06, h * 0.5))
    olho.cubicTo(w * 0.3, h * 0.12, w * 0.7, h * 0.12, w * 0.94, h * 0.5)
    olho.cubicTo(w * 0.7, h * 0.88, w * 0.3, h * 0.88, w * 0.06, h * 0.5)
    p.drawPath(olho)
    p.setBrush(QColor(cor))
    p.drawEllipse(QPointF(w * 0.5, h * 0.5), w * 0.13, h * 0.13)
    p.end()
    pix.setDevicePixelRatio(escala)
    return QIcon(pix)


__all__ = ["aplicar", "brilhar", "icone", "arredondar", "MenuTemas", "aparecer", "Carregando", "logo", "icone_olho"]
