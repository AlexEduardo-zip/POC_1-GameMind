"""Temas da janela. Um tema é só um conjunto de atributos visuais (cores, opacidades, arredondamento); a mesma folha de estilo
(FOLHA) e o mesmo código valem para todos. Para criar um tema, acrescente um `Tema` em TEMAS com todos os campos."""
from dataclasses import dataclass, fields

PADRAO = "hydra"


@dataclass(frozen=True)
class Tema:
    nome: str                # como aparece no seletor
    fundo: str               # fundo da janela
    painel: str              # fundo dos painéis
    painel_opacidade: float
    destaque: str            # botões, aba ativa, seleção, barra de progresso, cabeçalhos [ ... ]
    hover: str               # destaque sob o mouse e foco
    texto: str
    borda: str
    borda_opacidade: float
    borda_luz: str           # lados de cima e da esquerda (relevo); igual à borda num tema sem relevo
    borda_sombra: str        # lados de baixo e da direita
    raio: int                # cantos de botões, campos, menus e painéis, em px (itens internos usam raio - 2)
    raio_cartao: int         # cantos dos cartões da biblioteca e das capas (o Hydra usa cantos menores nos cartões)
    brilho: str              # brilho em volta dos painéis
    brilho_opacidade: float  # 0 = sem brilho


TEMAS = {
    # inspirado no Hydra Launcher (globals.scss): fundo #121212, barras #0d0d0d, texto #d0d1d7, botão principal claro #f0f1f7,
    # borda branca a 8%, marca verde-azulada #16b195 (aqui no hover e no foco), cantos de 8 px, sombra preta nos cartões
    "hydra": Tema("Hydra", fundo="#121212", painel="#0D0D0D", painel_opacidade=1.0, destaque="#F0F1F7", hover="#16B195",
                  texto="#D0D1D7", borda="#FFFFFF", borda_opacidade=0.08, borda_luz="#FFFFFF", borda_sombra="#FFFFFF", raio=8, raio_cartao=4,
                  brilho="#000000", brilho_opacidade=0.6),
    "sistema": Tema("Sistema", fundo="#05070F", painel="#0B1B33", painel_opacidade=0.70, destaque="#3DA9FF", hover="#7FD0FF",
                    texto="#E6F4FF", borda="#3DA9FF", borda_opacidade=0.80, borda_luz="#3DA9FF", borda_sombra="#3DA9FF", raio=2, raio_cartao=2,
                    brilho="#3DA9FF", brilho_opacidade=0.55),
    "anos90": Tema("Anos 90", fundo="#008080", painel="#C0C0C0", painel_opacidade=1.0, destaque="#000080", hover="#00CED1",
                   texto="#000000", borda="#808080", borda_opacidade=1.0, borda_luz="#FFFFFF", borda_sombra="#404040", raio=0, raio_cartao=0,
                   brilho="#000000", brilho_opacidade=0.0),
    "retro": Tema("Old / Retrô", fundo="#E9DCC3", painel="#F4EAD5", painel_opacidade=0.95, destaque="#7A4B2A", hover="#A0683D",
                  texto="#3B2A1A", borda="#B89B72", borda_opacidade=1.0, borda_luz="#B89B72", borda_sombra="#B89B72", raio=2, raio_cartao=2,
                  brilho="#7A4B2A", brilho_opacidade=0.0),
    "clean": Tema("Clean Minimalist", fundo="#FAFAFA", painel="#FFFFFF", painel_opacidade=1.0, destaque="#18181B", hover="#52525B",
                  texto="#18181B", borda="#E4E4E7", borda_opacidade=1.0, borda_luz="#E4E4E7", borda_sombra="#E4E4E7", raio=8, raio_cartao=8,
                  brilho="#000000", brilho_opacidade=0.0),
    "cyberpunk": Tema("Cyberpunk", fundo="#0A0014", painel="#1A0B2E", painel_opacidade=0.80, destaque="#FF2A6D", hover="#05D9E8",
                      texto="#F5F5FF", borda="#FF2A6D", borda_opacidade=0.70, borda_luz="#FF2A6D", borda_sombra="#05D9E8", raio=3, raio_cartao=3,
                      brilho="#FF2A6D", brilho_opacidade=0.45),
    "terminal": Tema("Terminal", fundo="#000000", painel="#0A0F0A", painel_opacidade=0.90, destaque="#00FF41", hover="#7DFF9A",
                     texto="#B6FFB6", borda="#00FF41", borda_opacidade=0.60, borda_luz="#00FF41", borda_sombra="#00FF41", raio=0, raio_cartao=0,
                     brilho="#00FF41", brilho_opacidade=0.35),
    "dark": Tema("Dark Elegante", fundo="#0E0E10", painel="#18181B", painel_opacidade=0.95, destaque="#C9A227", hover="#E3C45A",
                 texto="#EDE7D9", borda="#3F3A2A", borda_opacidade=1.0, borda_luz="#3F3A2A", borda_sombra="#3F3A2A", raio=6, raio_cartao=6,
                 brilho="#C9A227", brilho_opacidade=0.0),
}


def tema(nome: str) -> Tema:
    return TEMAS.get(nome) or TEMAS[PADRAO]


# ---------------------------------------------------------------- cores derivadas (a mesma conta para todo tema)
def _rgb(cor: str) -> tuple[int, int, int]:
    return tuple(int(cor[i:i + 2], 16) for i in (1, 3, 5))


def rgba(cor: str, opacidade: float) -> str:
    r, g, b = _rgb(cor)
    return f"rgba({r}, {g}, {b}, {round(opacidade * 255)})"


def misturar(frente: str, fundo: str, opacidade: float) -> str:
    """A cor que se vê de `frente` com essa opacidade sobre `fundo`."""
    f, b = _rgb(frente), _rgb(fundo)
    return "#" + "".join(f"{round(x * opacidade + y * (1 - opacidade)):02X}" for x, y in zip(f, b))


def _luminancia(cor: str) -> float:
    def canal(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (canal(c) for c in _rgb(cor))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(a: str, b: str) -> float:
    """Razão de contraste WCAG entre duas cores (1 a 21; texto comum pede 4,5)."""
    la, lb = sorted((_luminancia(a), _luminancia(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def painel_visto(t: Tema) -> str:
    return misturar(t.painel, t.fundo, t.painel_opacidade)


def texto_sobre_destaque(t: Tema) -> str:
    """Texto legível sobre o destaque (item selecionado, barra de progresso): o texto ou o fundo do tema, o que contrastar mais."""
    return max((t.texto, t.fundo, "#FFFFFF", "#000000"), key=lambda c: contraste(c, t.destaque))


def texto_apagado(t: Tema) -> str:
    """Texto secundário (abas inativas, desabilitado): o texto misturado ao painel, o mínimo para ainda ter contraste 4,5."""
    p = painel_visto(t)
    for opacidade in (0.6, 0.7, 0.8, 0.9):
        cor = misturar(t.texto, p, opacidade)
        if contraste(cor, p) >= 4.5:
            return cor
    return t.texto


def valores(t: Tema) -> dict:
    """Os valores que a FOLHA usa: os atributos do tema e cores derivadas deles."""
    v = {f.name: getattr(t, f.name) for f in fields(t)}
    v.update(painel_rgba=rgba(t.painel, t.painel_opacidade), borda_rgba=rgba(t.borda, t.borda_opacidade),
             luz_rgba=rgba(t.borda_luz, t.borda_opacidade), sombra_rgba=rgba(t.borda_sombra, t.borda_opacidade),
             campo=misturar(t.fundo, painel_visto(t), 0.35), apagado=texto_apagado(t),
             destaque_suave=rgba(t.destaque, 0.18), hover_suave=rgba(t.hover, 0.22), sobre_destaque=texto_sobre_destaque(t),
             raio_menor=max(0, t.raio - 2), raio_barra=min(4, t.raio))   # a barra de rolagem tem 8 px: no máximo meia altura
    return v


# Uma folha só, para todos os temas: só os valores entre chaves mudam.
FOLHA = """
QMainWindow, QDialog, QMessageBox, QInputDialog, QFileDialog {{ background: {fundo}; }}
QWidget {{ color: {texto}; font-family: "Segoe UI", "Noto Sans", sans-serif; font-size: 14px; }}
QToolTip {{ background: {campo}; color: {texto}; border: 1px solid {borda_rgba}; padding: 4px 8px; }}

QFrame#painel {{ background: {painel_rgba}; border: 1px solid {borda_rgba}; border-top-color: {luz_rgba};
    border-left-color: {luz_rgba}; border-right-color: {sombra_rgba}; border-bottom-color: {sombra_rgba}; border-radius: {raio}px; }}
QFrame#cabecalho {{ background: {painel_rgba}; border: none; border-bottom: 1px solid {borda_rgba}; }}
QLabel#marca {{ color: {destaque}; font-size: 20px; font-weight: 700; }}
QLabel#secao {{ color: {destaque}; font-weight: 700; padding-bottom: 2px; }}
QLabel#apagado, QLabel#previa {{ color: {apagado}; }}
QLabel#previa {{ background: {campo}; border: none; border-radius: {raio_menor}px; }}

QTabWidget::pane {{ border: none; background: transparent; }}
QTabBar::tab {{ background: {painel_rgba}; color: {apagado}; padding: 8px 16px; margin-right: 8px; border: 1px solid {borda_rgba};
    border-bottom: 2px solid transparent; border-top-left-radius: {raio}px; border-top-right-radius: {raio}px; font-weight: 600; }}
QTabBar::tab:selected {{ color: {destaque}; border-bottom: 2px solid {destaque}; }}
QTabBar::tab:hover {{ color: {texto}; border-bottom: 2px solid {hover}; }}

QPushButton {{ background: {destaque_suave}; color: {texto}; border: 1px solid {borda_rgba}; border-top-color: {luz_rgba};
    border-left-color: {luz_rgba}; border-right-color: {sombra_rgba}; border-bottom-color: {sombra_rgba}; border-radius: {raio}px;
    padding: 8px 16px; min-height: 22px; font-weight: 600; }}
QPushButton:hover {{ border-color: {hover}; background: {hover_suave}; }}
QPushButton:pressed {{ background: {destaque}; color: {sobre_destaque}; border-top-color: {sombra_rgba}; border-left-color: {sombra_rgba};
    border-right-color: {luz_rgba}; border-bottom-color: {luz_rgba}; }}
QPushButton:disabled {{ color: {apagado}; background: transparent; }}

QPushButton#primario {{ background: {destaque}; color: {sobre_destaque}; font-size: 15px; padding: 12px 24px; border-color: {destaque}; }}
QPushButton#primario:hover {{ border-color: {hover}; }}
QPushButton#primario:disabled {{ background: {destaque_suave}; color: {apagado}; }}
QPushButton#olho {{ background: transparent; color: {apagado}; border: 1px solid {borda_rgba}; border-radius: {raio}px;
    padding: 8px 16px; font-weight: 600; }}
QPushButton#olho:hover {{ color: {texto}; border-color: {hover}; background: {hover_suave}; }}
QPushButton#olho:checked {{ background: {destaque}; color: {sobre_destaque}; border-color: {destaque}; }}
QFrame#bloco {{ background: {painel_rgba}; border: none; border-radius: {raio}px; }}
QListWidget#limpa {{ background: transparent; border: none; outline: 0; }}
QPushButton#cartao {{ background: {painel_rgba}; border: 1px solid {borda_rgba}; border-radius: {raio_cartao}px; padding: 0;
    text-align: left; }}
QPushButton#cartao:hover {{ border-color: {hover}; background: {hover_suave}; }}
QLabel#capa {{ background: {campo}; border: none; border-radius: {raio_cartao}px; color: {destaque}; font-size: 40pt; }}
QPushButton#mais {{ background: {painel_rgba}; color: {texto}; border: 1px solid {borda_rgba}; border-radius: {raio_menor}px;
    padding: 0; min-height: 0; font-size: 16px; font-weight: 700; }}
QPushButton#mais:hover {{ border-color: {hover}; background: {campo}; }}
QPushButton#mais:disabled {{ color: {apagado}; }}
QLabel#titulo {{ color: {texto}; font-size: 22px; font-weight: 700; }}
QLabel#pergunta {{ color: {texto}; font-size: 17px; font-weight: 700; }}

QMenuBar {{ background: {painel_rgba}; color: {texto}; border-bottom: 1px solid {borda_rgba}; }}
QMenuBar::item {{ background: transparent; padding: 4px 12px; margin: 4px 2px; border-radius: {raio_menor}px; }}
QMenuBar::item:selected {{ background: {hover_suave}; }}
QLabel#logo {{ background: transparent; padding: 4px 8px 4px 16px; }}
QMenu {{ background: {campo}; color: {texto}; border: 1px solid {borda_rgba}; border-radius: {raio}px; padding: 4px; }}
QMenu::item {{ padding: 8px 16px; border-radius: {raio_menor}px; }}
QMenu::item:selected {{ background: {destaque}; color: {sobre_destaque}; }}
QMenu::item:disabled {{ color: {apagado}; }}
QMenu::separator {{ height: 1px; background: {borda_rgba}; margin: 4px 8px; }}

QRadioButton {{ spacing: 8px; padding: 4px 0; }}
QRadioButton::indicator {{ width: 14px; height: 14px; border: 1px solid {borda_rgba}; border-radius: 7px; background: {campo}; }}
QRadioButton::indicator:checked {{ background: {destaque}; border: 3px solid {campo}; }}
QRadioButton:disabled {{ color: {apagado}; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget#qt_scrollarea_viewport, QWidget#grade {{ background: transparent; }}

QLineEdit, QSpinBox, QComboBox, QPlainTextEdit, QTextBrowser, QListWidget {{ background: {campo}; color: {texto};
    border: 1px solid {borda_rgba}; border-radius: {raio}px; padding: 8px; selection-background-color: {destaque};
    selection-color: {sobre_destaque}; }}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus, QListWidget:focus {{ border-color: {hover}; }}
QLineEdit:disabled, QComboBox:disabled {{ color: {apagado}; }}
QComboBox QAbstractItemView {{ background: {campo}; color: {texto}; border: 1px solid {borda_rgba}; selection-background-color: {destaque};
    selection-color: {sobre_destaque}; }}
QListWidget::item {{ padding: 4px; border-radius: {raio_menor}px; }}
QListWidget::item:hover {{ background: {hover_suave}; }}
QListWidget::item:selected {{ background: {destaque}; color: {sobre_destaque}; }}

QCheckBox {{ spacing: 6px; }}
QCheckBox::indicator {{ width: 14px; height: 14px; border: 1px solid {borda_rgba}; border-radius: {raio_menor}px; background: {campo}; }}
QCheckBox::indicator:checked {{ background: {destaque}; }}
QCheckBox:disabled {{ color: {apagado}; }}

QProgressBar {{ background: {campo}; border: 1px solid {borda_rgba}; border-radius: {raio_menor}px; text-align: center; color: {texto}; }}
QProgressBar::chunk {{ background: {destaque}; border-radius: {raio_menor}px; }}
QStatusBar {{ background: {painel_rgba}; border-top: 1px solid {borda_rgba}; }}
QStatusBar QLabel {{ color: {texto}; }}
QSplitter::handle {{ background: transparent; }}
QScrollBar:vertical, QScrollBar:horizontal {{ background: transparent; border: none; width: 8px; height: 8px; }}
QScrollBar::handle {{ background: {borda_rgba}; border-radius: {raio_barra}px; min-height: 24px; min-width: 24px; }}
QScrollBar::handle:hover {{ background: {hover}; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ background: none; border: none; }}
"""


def folha(t: Tema) -> str:
    return FOLHA.format(**valores(t))


__all__ = ["PADRAO", "Tema", "TEMAS", "tema", "folha", "valores", "contraste", "painel_visto", "texto_sobre_destaque", "texto_apagado", "rgba"]
