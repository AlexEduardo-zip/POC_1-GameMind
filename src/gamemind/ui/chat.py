"""Aba "Conversar" da página do jogo: perguntas à IA do jogo, respondidas com o que foi lido das capturas (nucleo/chat.py).
A verificação (a IA funciona? há algo lido?) e cada resposta rodam fora da interface; enquanto a IA pensa, só a caixa de
pergunta fica parada. As capturas citadas na resposta ([C2]) são links: o clique mostra a captura na prévia da página."""
import html
import re
from urllib.parse import quote, unquote

from PySide6.QtCore import Qt, QUrl, Signal, Slot
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QStackedWidget, QTextBrowser, QVBoxLayout, QWidget

from ..nucleo import chat as nucleo
from . import aparencia
from .aparencia import Carregando
from .tarefas import Funcao, em_thread
from .temas import misturar, valores

# perguntas que servem para qualquer jogo, para quem não sabe por onde começar
SUGESTOES = ("Quem são os personagens principais?", "Quais lugares eu já visitei?", "Resuma o que aconteceu até agora.")


def _preparar(jogo, config):
    """Fora da interface: a disponibilidade e, se der, a conversa com a base do jogo já montada."""
    ok, motivo = nucleo.disponibilidade(jogo, config)
    return ok, motivo, (nucleo.Conversa(jogo.pasta, nucleo.Base.do_jogo(jogo)) if ok else None)


def _com_vez(vez: int, funcao, *args) -> tuple[int, bool, object]:
    """Roda `funcao` e devolve (vez, deu certo, resultado ou erro), sem levantar: a vez diz a que jogo aberto o resultado é."""
    try:
        return vez, True, funcao(*args)
    except Exception as e:  # noqa: BLE001 - o erro vira mensagem no chat
        return vez, False, f"{type(e).__name__}: {e}" if not isinstance(e, nucleo.ErroConector) else str(e)


class PainelChat(QWidget):
    mostrar_captura = Signal(str)   # nome do arquivo citado
    configurar = Signal()           # o usuário quer escolher a IA do jogo

    def __init__(self):
        super().__init__()
        self.jogo = self.config = self.conversa = None
        self.ia = ""
        self.pensando = False
        self._vez = 0          # cada abertura de jogo; resultados de uma vez anterior são descartados
        self._pendente = ""

        # estado 0: verificando; 1: indisponível (com o motivo); 2: a conversa
        self.estados = QStackedWidget()
        verificando = QWidget()
        lv = QHBoxLayout(verificando)
        self.girando_inicio = Carregando(22)
        lv.addStretch()
        lv.addWidget(self.girando_inicio)
        lv.addWidget(QLabel("Verificando a IA do jogo...", objectName="apagado"))
        lv.addStretch()
        self.estados.addWidget(verificando)

        indisponivel = QWidget()
        li = QVBoxLayout(indisponivel)
        self.motivo = QLabel(wordWrap=True, alignment=Qt.AlignCenter)
        botoes = QHBoxLayout()
        self.botao_configurar = QPushButton("Configurar jogo")
        self.botao_configurar.clicked.connect(self.configurar.emit)
        de_novo = QPushButton("Tentar de novo")
        de_novo.clicked.connect(self.atualizar)
        botoes.addStretch()
        botoes.addWidget(self.botao_configurar)
        botoes.addWidget(de_novo)
        botoes.addStretch()
        li.addStretch()
        li.addWidget(self.motivo)
        li.addLayout(botoes)
        li.addStretch()
        self.estados.addWidget(indisponivel)

        conversa = QWidget()
        lc = QVBoxLayout(conversa)
        lc.setContentsMargins(0, 0, 0, 0)
        topo = QHBoxLayout()
        self.sobre = QLabel(objectName="apagado", wordWrap=True)
        self.botao_limpar = QPushButton("Limpar conversa")
        self.botao_limpar.clicked.connect(self._limpar)
        topo.addWidget(self.sobre, 1)
        topo.addWidget(self.botao_limpar)
        self.texto = QTextBrowser(objectName="conversa", openLinks=False)
        self.texto.anchorClicked.connect(self._link)
        entrada = QHBoxLayout()
        self.pergunta = QLineEdit(placeholderText="Pergunte sobre o jogo (ex.: quem é o personagem que aparece no começo?)")
        self.pergunta.returnPressed.connect(self.enviar)
        self.girando = Carregando(20)
        self.botao_enviar = QPushButton("Enviar", objectName="primario")
        self.botao_enviar.clicked.connect(self.enviar)
        entrada.addWidget(self.pergunta, 1)
        entrada.addWidget(self.girando)
        entrada.addWidget(self.botao_enviar)
        lc.addLayout(topo)
        lc.addWidget(self.texto, 1)
        lc.addLayout(entrada)
        self.estados.addWidget(conversa)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.addWidget(self.estados)

    # ---------------------------------------------------------------- abrir e verificar
    def abrir(self, jogo, config) -> None:
        """Um jogo foi aberto (ou mudou: leitura nova, IA trocada)."""
        self.jogo, self.config = jogo, config
        self.atualizar()

    def fechar(self) -> None:
        self._vez += 1
        self.jogo = self.conversa = None
        self.pensando = False
        self.girando.parar()

    @Slot()
    def atualizar(self) -> None:
        if not self.jogo or self.pensando:
            return
        self._vez += 1
        self.estados.setCurrentIndex(0)
        self.girando_inicio.iniciar()
        f = Funcao(_com_vez, self._vez, _preparar, self.jogo, self.config)
        f.concluido.connect(self._preparado)
        em_thread(f)

    @Slot(object)
    def _preparado(self, r) -> None:
        vez, deu, valor = r
        if vez != self._vez:
            return   # resposta de um jogo que já foi fechado
        self.girando_inicio.parar()
        if not deu:
            self._indisponivel(f"Não consegui preparar o chat: {valor}")
            return
        ok, motivo, conversa = valor
        if not ok:
            self._indisponivel(motivo)
            return
        self.conversa, self.ia = conversa, motivo
        self.sobre.setText(f"Respostas só com o que foi lido das capturas · IA: {motivo}")
        self.estados.setCurrentIndex(2)
        self.ocupado()
        self._desenhar()

    def _indisponivel(self, motivo: str) -> None:
        self.conversa = None
        self.motivo.setText(motivo)
        self.botao_configurar.setVisible("Configurar jogo" in motivo)
        self.estados.setCurrentIndex(1)

    # ---------------------------------------------------------------- perguntar
    def ocupado(self, lendo: bool | None = None) -> None:
        """`lendo`: a leitura das capturas começou ou terminou (durante ela o chat espera: a IA e a base estão em uso). Sem
        argumento, só reaplica o estado (leitura em andamento, IA pensando)."""
        if lendo is not None:
            self._lendo = lendo
        lendo = getattr(self, "_lendo", False)
        livre = not lendo and not self.pensando
        for w in (self.pergunta, self.botao_enviar, self.botao_limpar):
            w.setEnabled(livre)
        self.pergunta.setPlaceholderText("Lendo as capturas: o chat volta quando a leitura terminar" if lendo else
                                         "Pergunte sobre o jogo (ex.: quem é o personagem que aparece no começo?)")

    def enviar(self, texto: str = "") -> None:
        pergunta = (texto or self.pergunta.text()).strip()
        if not pergunta or not self.conversa or self.pensando or getattr(self, "_lendo", False):
            return
        try:
            backend = nucleo.backend_do_chat(self.config.do_jogo(self.jogo).ia)
        except nucleo.ErroConector as e:
            self._indisponivel(str(e))
            return
        self.pergunta.clear()
        self.pensando, self._pendente = True, pergunta
        self.ocupado()
        self.girando.iniciar()
        self._desenhar()
        f = Funcao(_com_vez, self._vez, self.conversa.perguntar, pergunta, backend)
        f.concluido.connect(self._respondido)
        em_thread(f)

    @Slot(object)
    def _respondido(self, r) -> None:
        vez, deu, valor = r
        if vez == self._vez:
            self._terminou("" if deu else str(valor))

    def _terminou(self, erro: str = "") -> None:
        self.pensando, pendente, self._pendente = False, self._pendente, ""
        self.girando.parar()
        self.ocupado()
        if erro:
            self.pergunta.setText(pendente)   # a pergunta volta para a caixa, para tentar de novo
        self._desenhar(erro)
        self.pergunta.setFocus()

    def _limpar(self) -> None:
        if self.conversa and not self.pensando:
            self.conversa.limpar()
            self._desenhar()

    # ---------------------------------------------------------------- desenho
    def ao_mudar_tema(self) -> None:
        if self.conversa:
            self._desenhar()

    def _desenhar(self, erro: str = "") -> None:
        t = aparencia.ATUAL
        v = valores(t) if t else {"campo": "#202020", "apagado": "#999999", "hover": "#16B195", "texto": "#DDDDDD"}
        # o balão da pergunta: o campo com um toque do destaque do tema (o texto do tema continua legível sobre ele)
        v["balao"] = misturar(t.destaque, v["campo"], 0.14) if t else "#2A2A2A"
        self.texto.document().setDefaultStyleSheet(f"a {{ color: {v['hover']}; text-decoration: none; font-weight: 600; }}")
        partes = []
        mensagens = self.conversa.mensagens if self.conversa else []
        if not mensagens and not self._pendente:
            sugestoes = " &nbsp;·&nbsp; ".join(f'<a href="perguntar:{quote(s)}">{html.escape(s)}</a>' for s in SUGESTOES)
            partes.append(f'<p style="color:{v["apagado"]}">Pergunte qualquer coisa sobre o que você já viu no jogo. A IA '
                          f"responde só com o que foi lido das suas capturas e mostra de qual captura tirou cada coisa.</p>"
                          f"<p>{sugestoes}</p>")
        for m in mensagens:
            partes.append(self._pergunta_html(m.pergunta, v))
            partes.append(self._resposta_html(m, v))
        if self._pendente:
            partes.append(self._pergunta_html(self._pendente, v))
            partes.append(f'<p style="color:{v["apagado"]}">Pensando... (na primeira pergunta o modelo é carregado, pode levar uns segundos)</p>')
        if erro:
            partes.append(f'<p style="color:{v["apagado"]}">A IA falhou: {html.escape(erro[:300])}</p>')
        self.texto.setHtml("".join(partes))
        barra = self.texto.verticalScrollBar()
        barra.setValue(barra.maximum())

    @staticmethod
    def _pergunta_html(pergunta: str, v: dict) -> str:
        return (f'<table width="100%" cellpadding="8" cellspacing="0" style="margin-top:12px"><tr>'
                f'<td bgcolor="{v["balao"]}"><b>Você:</b> {html.escape(pergunta)}</td></tr></table>')

    @staticmethod
    def _resposta_html(m: nucleo.Mensagem, v: dict) -> str:
        # as marcas internas (C3, C15...) viram 1, 2, 3 nesta resposta, iguais no texto e na lista
        ordem = sorted(m.fontes, key=lambda x: int(x[1:]))
        numero = {x: i for i, x in enumerate(ordem, 1)}

        def marca(x):
            cid = x.group(1).upper()
            arq = m.fontes.get(cid)
            return f'<a href="captura:{quote(arq)}" title="{html.escape(arq)}">[{numero[cid]}]</a>' if arq else ""
        corpo = re.sub(r"\[(C\d+)\]", marca, html.escape(m.resposta), flags=re.IGNORECASE).replace("\n", "<br>")
        fontes = ""
        if ordem:
            lista = " &nbsp;·&nbsp; ".join(f'<a href="captura:{quote(m.fontes[x])}">[{numero[x]}] {html.escape(m.fontes[x])}</a>'
                                           for x in ordem)
            fontes = f'<p style="color:{v["apagado"]}; font-size:12px">Capturas: {lista}</p>'
        return f"<p>{corpo}</p>{fontes}"

    def _link(self, url: QUrl) -> None:
        esquema, _, resto = url.toString(QUrl.FullyEncoded).partition(":")
        if esquema == "captura":
            self.mostrar_captura.emit(unquote(resto))
        elif esquema == "perguntar":
            self.enviar(unquote(resto))


__all__ = ["PainelChat", "SUGESTOES"]
