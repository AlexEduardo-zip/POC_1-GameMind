"""Janela principal do GameMind (PySide6).
Tela inicial: a biblioteca de jogos (biblioteca.py). Adicionar um jogo abre o assistente (assistente.py), um questionário com as
pastas e o uso de IA. A página de um jogo mostra só o essencial: iniciar a leitura, acompanhar a pasta, a captura em leitura, as
notas do vault e abrir no Obsidian. O resto (configurar o jogo, limpar o vault, configurações gerais, registro) fica no menu de
cima. Toda a lógica está no núcleo; aqui só há apresentação e encadeamento de ações."""
import html
import logging
import sys
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QIcon, QImage, QPixmap
from PySide6.QtWidgets import (QApplication, QDialog, QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QMainWindow, QMenu, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QSizePolicy, QSpinBox,
                               QSplitter, QStackedWidget, QTabWidget, QTextBrowser, QVBoxLayout, QWidget)

from .. import VERSAO
from ..nucleo.config import Config
from ..nucleo.diagnostico import PASSOS_VERIFICAR, verificar
from ..nucleo import obsidian
from ..nucleo.observador import Observador
from ..nucleo.pipeline import Pipeline, Progresso, limpar
from ..nucleo.recursos import EXT_CLIPE
from ..nucleo.repositorio import Jogo
from . import aparencia
from .aparencia import MenuTemas, aparecer, aplicar, arredondar, brilhar, icone_olho, logo
from .ajuda import GUIAS, JanelaAjuda, JanelaSobre
from .assistente import AssistenteJogo
from .biblioteca import Biblioteca
from .chat import PainelChat
from .espera import Espera
from .tarefas import PonteLog, Trabalhador, em_andamento, em_thread
from .temas import tema as tema_de, valores

log = logging.getLogger("gamemind")

ETAPAS = {"registro": "Procurando capturas", "regioes": "Aprendendo onde fica o texto", "leitura": "Lendo o texto das capturas",
          "llm": "Consultando a IA", "grafo": "Montando o grafo e os nomes do jogo",
          "resumos": "Revisando e resumindo as entidades com a IA", "vault": "Criando as notas do vault"}
NOTAS_VAULT = ("*.md", "*.canvas")


def _imagem_do_arquivo(caminho: Path) -> QImage | None:
    """A captura, ou um quadro do meio do clipe."""
    if caminho.suffix.lower() not in EXT_CLIPE:
        img = QImage(str(caminho))
        return None if img.isNull() else img
    try:
        import cv2
        cap = cv2.VideoCapture(str(caminho))
        try:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(cap.get(cv2.CAP_PROP_FRAME_COUNT) // 2))
            ok, quadro = cap.read()
        finally:
            cap.release()
        if not ok:
            return None
        quadro = cv2.cvtColor(quadro, cv2.COLOR_BGR2RGB)
        h, w, _ = quadro.shape
        return QImage(quadro.data, w, h, 3 * w, QImage.Format_RGB888).copy()
    except Exception:  # noqa: BLE001 - a prévia é enfeite: sem ela o processamento segue
        return None


class Previa(QLabel):
    """Mostra uma imagem ajustada ao espaço disponível, refazendo o ajuste quando a janela muda de tamanho."""

    def __init__(self):
        super().__init__("Nenhum arquivo em processamento")
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(360, 220)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.setObjectName("previa")   # cores do tema (temas.py)
        self._original: QPixmap | None = None

    def mostrar(self, img: QImage | None, vazio: str = "Sem prévia") -> None:
        self._original = QPixmap.fromImage(img) if img else None
        if self._original:
            self._ajustar()
        else:
            self.setPixmap(QPixmap())
            self.setText(vazio)

    def _ajustar(self) -> None:
        if self._original:
            self.setPixmap(self._original.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._ajustar()


def _painel(titulo: str, *conteudo) -> QFrame:
    """Painel com cabeçalho "[ TÍTULO ]"; `conteudo`: widgets ou layouts, um embaixo do outro."""
    painel = QFrame(objectName="painel")
    lay = QVBoxLayout(painel)
    lay.setContentsMargins(16, 16, 16, 16)
    lay.addWidget(QLabel(f"[ {titulo.upper()} ]", objectName="secao"))
    for c in conteudo:
        (lay.addLayout if isinstance(c, (QHBoxLayout, QVBoxLayout, QFormLayout)) else lay.addWidget)(c)
    brilhar(painel)   # o brilho do tema, como nos painéis que já existiam quando o tema foi aplicado
    return painel


class Janela(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"GameMind {VERSAO}")
        self.resize(1100, 720)
        self.config = Config.carregar()
        self.jogo: Jogo | None = None
        self.pipeline: Pipeline | None = None
        self.thread = None
        self.observadores: list[Observador] = []
        self.de_novo = False   # chegou mídia nova durante uma rodada: roda outra ao terminar
        self.saindo = False    # fechando: a rodada em andamento termina e nada novo começa
        self.arquivo_atual = ""
        self.itens_vault: dict[str, QListWidgetItem] = {}

        self.ponte_log = PonteLog()
        logging.getLogger("gamemind").addHandler(self.ponte_log)
        logging.getLogger("gamemind").setLevel(logging.INFO)
        self.registro = QPlainTextEdit(readOnly=True)
        self.registro.setMaximumBlockCount(5000)
        self.ponte_log.linha.connect(self.registro.appendPlainText)

        self.biblioteca = Biblioteca()
        self.biblioteca.abrir.connect(self._abrir_jogo)
        self.biblioteca.adicionar.connect(self._novo_jogo)
        self.biblioteca.apagar.connect(self._apagar_jogo)
        self.telas = QStackedWidget()
        self.telas.addWidget(self.biblioteca)
        self.telas.addWidget(self._pagina_jogo())
        central = QWidget()
        corpo = QVBoxLayout(central)
        corpo.setContentsMargins(0, 0, 0, 0)
        corpo.setSpacing(0)
        corpo.addWidget(self._cabecalho())
        miolo = QVBoxLayout()
        miolo.setContentsMargins(24, 16, 24, 16)
        miolo.addWidget(self.telas)
        corpo.addLayout(miolo, 1)
        self.setCentralWidget(central)
        self._menu()
        self.logo = QLabel(objectName="logo", toolTip=f"GameMind {VERSAO}")   # à esquerda do menu; desenhado nas cores do tema
        self.menuBar().setCornerWidget(self.logo, Qt.TopLeftCorner)
        self.botao_mais.clicked.connect(lambda: self.menu_jogo.exec(self.botao_mais.mapToGlobal(QPoint(0, self.botao_mais.height() + 4))))
        self.progresso = QProgressBar()
        self.progresso.setMaximumWidth(260)
        self.progresso.hide()
        self.estado = QLabel()
        self.statusBar().addWidget(self.estado, 1)
        self.statusBar().addPermanentWidget(self.progresso)
        aplicar(self, tema_de(self.config.tema))
        self._mostrar_biblioteca()

    # ---------------------------------------------------------------- construção
    def _cabecalho(self) -> QFrame:
        cab = QFrame(objectName="cabecalho")
        lay = QHBoxLayout(cab)
        lay.setContentsMargins(24, 16, 24, 16)
        lay.addWidget(QLabel("[ GAMEMIND ]", objectName="marca"))
        lay.addWidget(QLabel(f"SISTEMA · v{VERSAO}", objectName="apagado"))
        lay.addStretch()
        return cab

    def _menu(self) -> None:
        def acao(menu, texto, funcao, atalho=""):
            a = QAction(texto, self)
            a.triggered.connect(lambda _=False: funcao())
            if atalho:
                a.setShortcut(atalho)
            menu.addAction(a)
            return a

        def menu(titulo):
            m = arredondar(QMenu(titulo, self))
            self.menuBar().addMenu(m)
            return m
        m = menu("Jogo")
        self.acoes_jogo = [acao(m, "Configurar jogo (pastas, IA, regiões, resumos)...", self._configurar_jogo),
                           acao(m, "Abrir a pasta dos dados do jogo", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.jogo.pasta)))),
                           acao(m, "Limpar vault...", self._limpar_vault)]
        m.addSeparator()
        self.acao_apagar = acao(m, "Apagar jogo...", self._apagar_jogo)
        m.addSeparator()
        self.acao_biblioteca = acao(m, "Voltar à biblioteca", self._mostrar_biblioteca, "Ctrl+B")
        self.acoes_jogo += [self.acao_apagar, self.acao_biblioteca]
        # o botão "⋯" da página do jogo abre as mesmas ações (as mesmas QActions: ligar e desligar vale para os dois)
        self.menu_jogo = arredondar(QMenu(self))
        self.menu_jogo.addActions(self.acoes_jogo[:3])
        self.menu_jogo.addSeparator()
        self.menu_jogo.addAction(self.acao_apagar)
        m = menu("Aplicativo")
        # o que não pode começar no meio de uma leitura fica desligado durante ela (_ocupado)
        self.acoes_app = [acao(m, "Adicionar jogo...", self._novo_jogo, "Ctrl+N"),
                          acao(m, "Configurações gerais...", self._configuracoes_gerais),
                          acao(m, "Verificar o computador...", self._diagnostico)]
        acao(m, "Registro", self._mostrar_registro)
        m.addSeparator()
        m.addMenu(MenuTemas(self, self.config.tema, self._mudar_tema))
        m = menu("Ajuda")
        for chave, titulo, _ in GUIAS:
            acao(m, titulo, lambda c=chave: self._ajuda(c), "F1" if chave == "inicio" else "")
        self.menuBar().addAction("Sobre", self._sobre)

    def _ajuda(self, guia: str = "inicio"):
        """Os guias numa janela que não bloqueia a principal: dá para seguir os passos com ela aberta."""
        if not getattr(self, "_janela_ajuda", None):
            self._janela_ajuda = JanelaAjuda(self, guia, acoes={"verificar": self._diagnostico})
        else:
            self._janela_ajuda.lista.setCurrentRow(next(i for i, (k, _, _) in enumerate(GUIAS) if k == guia))
        self._janela_ajuda.show()
        self._janela_ajuda.raise_()
        self._janela_ajuda.activateWindow()

    def _sobre(self):
        d = JanelaSobre(self, str(Jogo.raiz()))
        d.exec()
        d.deleteLater()

    def _mudar_tema(self, chave: str, definitivo: bool):
        """Troca a aparência na hora (só cores, bordas e opacidade); `definitivo` grava a escolha para a próxima vez."""
        if aparencia.ATUAL is not tema_de(chave):   # passar o mouse de novo no mesmo tema não refaz a folha de estilo
            aplicar(self, tema_de(chave))
        if definitivo and chave != self.config.tema:
            self.config.tema = chave
            self.config.salvar()

    def _pagina_jogo(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        topo = QHBoxLayout()
        self.botao_voltar = QPushButton("← Biblioteca")
        self.botao_voltar.clicked.connect(self._mostrar_biblioteca)
        self.titulo_jogo = QLabel(objectName="titulo")
        self.botao_obsidian = QPushButton("Abrir no Obsidian")
        self.botao_obsidian.setToolTip("O grafo e o Quadro da partida se exploram no Obsidian")
        self.botao_obsidian.clicked.connect(lambda: self._abrir_no_obsidian())
        self.botao_acompanhar = QPushButton(objectName="olho", checkable=True)
        self.botao_acompanhar.setToolTip("Ligado, cada captura nova que aparecer nas pastas do jogo é lida sozinha, enquanto você joga")
        self.botao_acompanhar.toggled.connect(self._observar)
        topo.addWidget(self.botao_voltar)
        topo.addSpacing(12)
        topo.addWidget(self.titulo_jogo)
        topo.addStretch()
        self.botao_mais = QPushButton("⋯", objectName="mais", toolTip="Configurar, limpar o vault ou apagar o jogo")
        self.botao_mais.setFixedSize(40, 40)
        self.botao_mais.setCursor(Qt.PointingHandCursor)
        topo.addWidget(self.botao_acompanhar)
        topo.addWidget(self.botao_obsidian)
        topo.addWidget(self.botao_mais)
        lay.addLayout(topo)

        acoes = QHBoxLayout()
        self.botao_iniciar = QPushButton("▶  Iniciar leitura", objectName="primario")
        self.botao_iniciar.clicked.connect(self._processar)
        self.botao_cancelar = QPushButton("Cancelar")
        self.botao_cancelar.clicked.connect(self._cancelar)
        self.botao_cancelar.hide()
        self.resumo_jogo = QLabel(objectName="apagado", wordWrap=True)
        acoes.addWidget(self.botao_iniciar)
        acoes.addWidget(self.botao_cancelar)
        acoes.addSpacing(14)
        acoes.addWidget(self.resumo_jogo, 1)
        lay.addSpacing(6)
        lay.addLayout(acoes)
        lay.addSpacing(6)

        # dois blocos suaves, sem bordas: a captura em leitura e as notas do vault
        esquerda, direita = QFrame(objectName="bloco"), QFrame(objectName="bloco")
        le, ld = QVBoxLayout(esquerda), QVBoxLayout(direita)
        self.previa = Previa()
        self.legenda = QLabel("", alignment=Qt.AlignCenter, wordWrap=True, objectName="apagado")
        le.addWidget(self.previa, 1)
        le.addWidget(self.legenda)
        self.lista_vault = QListWidget(objectName="limpa")
        self.lista_vault.setToolTip("Clique duas vezes para abrir a nota no Obsidian")
        self.lista_vault.itemActivated.connect(lambda item: self._abrir_no_obsidian(Path(item.data(Qt.UserRole))))
        # as notas do vault e, com uma IA no jogo, a conversa sobre o que foi lido
        self.chat = PainelChat()
        self.chat.mostrar_captura.connect(self._mostrar_captura)
        self.chat.configurar.connect(self._configurar_jogo)
        self.abas = QTabWidget()
        self.abas.addTab(self.lista_vault, "Notas")
        self.abas.addTab(self.chat, "Conversar com a IA")
        ld.addWidget(self.abas, 1)
        div = QSplitter()
        div.addWidget(esquerda)
        div.addWidget(direita)
        div.setSizes([620, 400])
        lay.addWidget(div, 1)
        self._texto_acompanhar(False)
        return w

    # ---------------------------------------------------------------- biblioteca e jogos
    def _mostrar_biblioteca(self):
        if self.thread:
            return
        self._fechar_jogo()
        self.biblioteca.recarregar()
        self.telas.setCurrentWidget(self.biblioteca)
        aparecer(self.biblioteca)
        for a in self.acoes_jogo:
            a.setEnabled(False)
        self.estado.setText(f"{len(Jogo.listar())} jogo(s) na biblioteca")

    def _fechar_jogo(self):
        self.botao_acompanhar.setChecked(False)
        self.chat.fechar()
        if self.jogo:
            self.jogo.fechar()
            self.jogo = None

    def _abrir_jogo(self, nome: str):
        if self.thread:
            return
        self._fechar_jogo()
        self.jogo = Jogo.abrir(nome)
        self.config.ultimo_jogo = self.jogo.nome
        self.config.salvar()
        self.titulo_jogo.setText(self.jogo.nome)
        self.arquivo_atual = ""
        self.previa.mostrar(None, "Nenhum arquivo em processamento")
        self.legenda.setText("")
        self._resumir_jogo()
        self._carregar_vault()
        self.abas.setCurrentIndex(0)
        self._chat_do_jogo()
        self.telas.setCurrentIndex(1)
        aparecer(self.telas.currentWidget())
        for a in self.acoes_jogo:
            a.setEnabled(True)
        self._atualizar()

    def _chat_do_jogo(self):
        """O chat só existe num jogo com IA (Ollama ou Claude); a verificação de que ela funciona roda em segundo plano."""
        com_ia = bool(self.config.do_jogo(self.jogo).ia)
        self.abas.setTabVisible(1, com_ia)
        if com_ia:
            self.chat.abrir(self.jogo, self.config)
        else:
            self.chat.fechar()

    def _mostrar_captura(self, nome: str):
        """Uma captura citada no chat, na prévia da página."""
        midia = next((m for m in self.jogo.midias() if m.nome == nome), None) if self.jogo else None
        if midia and not self.thread:
            self.previa.mostrar(_imagem_do_arquivo(Path(midia.caminho)), "Sem prévia deste arquivo")
            self.legenda.setText(f"Citada no chat: {nome}")

    def _resumir_jogo(self):
        """A linha que lembra como este jogo é lido (as escolhas do assistente)."""
        cfg = self.config.do_jogo(self.jogo)
        pastas = " · ".join(str(p) for p in self.jogo.pastas()) or "nenhuma pasta escolhida (menu Jogo > Configurar jogo)"
        if cfg.ia:
            extras = [t for t, ligado in ((", aprende as regiões", cfg.regioes_por_imagem),
                                          (", revisa e resume as entidades", cfg.revisar_entidades)) if ligado]
            modo = f"com IA ({cfg.ia})" + "".join(extras)
        else:
            modo = "só com OCR"
        self.resumo_jogo.setText(f"Lê {modo}. Pastas: {pastas}")

    def _novo_jogo(self):
        if self.thread:
            return
        a = AssistenteJogo(self, ia_padrao=self.config.ia or "ollama")
        aceito = a.exec() == QDialog.Accepted
        r = a.resultado()
        a.deleteLater()   # sem isto o assistente ficaria pendurado na janela (é filho dela)
        if not aceito:
            return
        jogo = Jogo.abrir(r["nome"])
        try:
            self._gravar_escolhas(jogo, r)
        finally:
            jogo.fechar()
        self._abrir_jogo(r["nome"])
        self.estado.setText("Jogo pronto. Clique em Iniciar leitura.")

    def _configurar_jogo(self):
        if not self.jogo or self.thread:
            return
        a = AssistenteJogo(self, jogo=self.jogo)
        aceito = a.exec() == QDialog.Accepted
        r = a.resultado()
        a.deleteLater()
        if aceito:
            self._gravar_escolhas(self.jogo, r)
            self._resumir_jogo()
            self._chat_do_jogo()
            if self.botao_acompanhar.isChecked():   # as pastas podem ter mudado
                self._observar(False)
                self._observar(True)

    def _apagar_jogo(self, nome: str = ""):
        """Apaga um jogo do GameMind (o aberto, ou `nome`, vindo do cartão da biblioteca), depois de confirmar."""
        nome = nome or (self.jogo.nome if self.jogo else "")
        if not nome or self.thread or self._chat_pensando():
            return
        caixa = QMessageBox(self)
        caixa.setWindowTitle("Apagar jogo")
        caixa.setIcon(QMessageBox.Warning)
        caixa.setText(f"Apagar o jogo <b>{html.escape(nome)}</b>?")
        caixa.setInformativeText(
            "Apaga tudo o que o GameMind guardou deste jogo: as leituras, as respostas da IA, os nomes e as regiões aprendidos, "
            "os resumos e o vault (inclusive notas que você tenha escrito dentro dele).<br><br>"
            "<b>As suas capturas e vídeos não são apagados</b>: continuam nas pastas de origem.<br><br>Não dá para desfazer.")
        apagar = caixa.addButton("Apagar jogo", QMessageBox.DestructiveRole)
        caixa.addButton(QMessageBox.Cancel)
        caixa.setDefaultButton(QMessageBox.Cancel)
        caixa.exec()
        if caixa.clickedButton() is not apagar:
            return
        if self.jogo and self.jogo.nome == nome:
            self._fechar_jogo()   # o banco precisa estar fechado para a pasta sair
        try:
            Jogo.apagar(nome)
        except (OSError, ValueError) as e:
            QMessageBox.warning(self, "Apagar jogo", f"Não consegui apagar tudo (algum arquivo pode estar aberto em outro programa, "
                                                     f"como o Obsidian):\n\n{e}")
        if self.config.ultimo_jogo == nome:
            self.config.ultimo_jogo = ""
            self.config.salvar()
        self._mostrar_biblioteca()
        if nome not in Jogo.listar():
            self.estado.setText(f"{nome} foi apagado.")

    @staticmethod
    def _gravar_escolhas(jogo: Jogo, r: dict):
        for k in ("pasta_capturas", "pasta_videos", "ia", "regioes_por_imagem", "revisar_entidades"):
            jogo.set(k, r[k])
        if r.get("executavel"):
            jogo.set("executavel", r["executavel"])

    def _abrir_no_obsidian(self, arquivo: Path | None = None):
        """Abre o vault (ou uma nota) no Obsidian, registrando o vault nele se for preciso (nucleo/obsidian.py)."""
        url, aviso = obsidian.link(self.jogo.pasta_vault, arquivo)
        if url and QDesktopServices.openUrl(QUrl(url)):
            return
        if aviso:
            QMessageBox.information(self, "Obsidian", aviso)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.jogo.pasta_vault)))   # ao menos mostra a pasta

    # ---------------------------------------------------------------- vault
    def _carregar_vault(self):
        """Lista as notas que o vault já tem, das mais recentes para as mais antigas."""
        self.lista_vault.clear()
        self.itens_vault.clear()
        vault = self.jogo.pasta_vault
        arquivos = [a for padrao in NOTAS_VAULT for a in vault.rglob(padrao) if not any(p.startswith(".") for p in a.relative_to(vault).parts)]
        for a in sorted(arquivos, key=lambda a: a.stat().st_mtime):
            self._nota_criada(a)
        self.abas.setTabText(0, f"Notas ({self.lista_vault.count()})")

    def _nota_criada(self, caminho: Path):
        chave = str(caminho)
        if chave in self.itens_vault:
            self.lista_vault.takeItem(self.lista_vault.row(self.itens_vault[chave]))
        rel = caminho.relative_to(self.jogo.pasta_vault).as_posix() if caminho.is_relative_to(self.jogo.pasta_vault) else caminho.name
        item = QListWidgetItem(rel)
        item.setData(Qt.UserRole, chave)
        self.lista_vault.insertItem(0, item)
        self.itens_vault[chave] = item
        self.abas.setTabText(0, f"Notas ({self.lista_vault.count()})")

    def _limpar_vault(self):
        """Apaga o vault gerado (e, se pedido, também as leituras e respostas da IA) para refazer sem criar outro jogo."""
        if not self.jogo or self.thread or self._chat_pensando():
            return
        caixa = QMessageBox(self)
        caixa.setWindowTitle("Limpar vault")
        caixa.setIcon(QMessageBox.Question)
        caixa.setText(f"Apagar o vault gerado de <b>{html.escape(self.jogo.nome)}</b>?")
        caixa.setInformativeText(
            "<b>Só o vault</b>: apaga as notas, canvas e miniaturas que o GameMind gerou. A próxima leitura refaz o vault rápido, "
            "com as leituras e respostas da IA já guardadas.<br><br>"
            "<b>Tudo</b>: reinicia o jogo do zero, como se tivesse acabado de ser criado: esquece as capturas registradas, as "
            "leituras, as respostas da IA, os nomes e as regiões de leitura aprendidos, os resumos e a conversa com a IA. As pastas e as escolhas do "
            "jogo ficam. A próxima leitura processa tudo de novo (demora como a primeira vez).<br><br>"
            "Notas que você mesmo criou no vault e a configuração do Obsidian não são apagadas.")
        so_vault = caixa.addButton("Só o vault", QMessageBox.AcceptRole)
        tudo = caixa.addButton("Tudo", QMessageBox.DestructiveRole)
        caixa.addButton(QMessageBox.Cancel)
        caixa.setDefaultButton(QMessageBox.Cancel)
        caixa.exec()
        if caixa.clickedButton() not in (so_vault, tudo):
            return
        acompanhando = self.botao_acompanhar.isChecked()
        self.botao_acompanhar.setChecked(False)   # o acompanhamento não pode começar uma rodada no meio da limpeza
        try:
            n = limpar(self.jogo, tudo=caixa.clickedButton() is tudo)
        except OSError as e:
            QMessageBox.warning(self, "Limpar vault", f"Não consegui apagar tudo (o arquivo pode estar aberto em outro programa):\n\n{e}")
            n = None
        self._carregar_vault()
        self._atualizar()
        if self.abas.isTabVisible(1):
            self.chat.atualizar()   # a base (e, com Tudo, a conversa) mudou
        if n is not None:
            self.estado.setText(f"Vault limpo ({n} arquivo(s) apagados). Clique em Iniciar leitura para refazer.")
            self.legenda.setText("Vault limpo")
        self.botao_acompanhar.setChecked(acompanhando)

    # ---------------------------------------------------------------- leitura
    def _processar(self):
        """Uma rodada de leitura, do jeito escolhido para o jogo (com ou sem IA; regiões; revisão)."""
        if not self.jogo:
            return
        if self.thread:
            self.de_novo = True
            return
        if not any(p.is_dir() for p in self.jogo.pastas()):
            QMessageBox.information(self, "Pastas", "As pastas de capturas deste jogo não foram encontradas. Escolha-as em Configurar jogo.")
            self._configurar_jogo()
            return
        cfg = self.config.do_jogo(self.jogo)
        log.info("rodada %s", f"com IA ({cfg.ia})" if cfg.ia else "só com OCR")
        self.pipeline = Pipeline(self.jogo, cfg)
        trab = Trabalhador(self.pipeline)
        trab.progresso.connect(self._progresso)
        trab.concluido.connect(self._concluido)
        trab.falhou.connect(self._falhou)
        self.thread = em_thread(trab)
        self.thread.finished.connect(self._thread_fim)
        self._ocupado(True)

    def _cancelar(self):
        if self.pipeline:
            self.pipeline.cancelar()
            self.estado.setText("Cancelando depois da captura atual...")

    def _progresso(self, p: Progresso):
        if p.parcial:   # nota gravada no meio da leitura/consulta à IA: entra na lista sem mexer no estado da etapa em andamento
            if p.arquivo:
                self._nota_criada(Path(p.arquivo))
            return
        etapa = ETAPAS.get(p.etapa, p.etapa)
        self.estado.setText(f"{etapa}: {p.mensagem}")
        if p.etapa == "vault" and p.arquivo:
            self._nota_criada(Path(p.arquivo))
            self.legenda.setText(etapa)
        elif p.etapa in ("leitura", "llm", "regioes") and p.arquivo:   # a captura em andamento
            if p.arquivo != self.arquivo_atual:
                self.arquivo_atual = p.arquivo
                self.previa.mostrar(_imagem_do_arquivo(Path(p.arquivo)), "Sem prévia deste arquivo")
            self.legenda.setText(f"{etapa}: {Path(p.arquivo).name}" + (f" ({p.feito + 1} de {p.total})" if p.total else ""))
        elif p.etapa not in ("leitura", "llm"):
            self.legenda.setText(etapa)
        if p.total:
            self.progresso.setRange(0, p.total)
            self.progresso.setValue(p.feito)
        elif p.etapa != "leitura":
            self.progresso.setRange(0, 0)

    def _concluido(self, r: dict):
        msg = (f"{r['lidas']} lida(s), {r['erros']} erro(s); {r['nos']} entidades, {r['arestas']} relações, {r['notas']} notas "
               f"({r['tempo_s']} s)" + (" — cancelado" if r["cancelado"] else ""))
        self.estado.setText(msg)
        self.legenda.setText("Cancelado" if r["cancelado"] else "Concluído. Abra o vault no Obsidian para ver o grafo.")
        log.info(msg)
        if r["erro_llm"] and not self.saindo:
            QMessageBox.warning(self, "IA", f"O grafo foi gerado, mas a IA falhou:\n\n{r['erro_llm']}")

    def _falhou(self, erro: str):
        self.estado.setText("Falha no processamento (veja Aplicativo > Registro)")
        if not self.saindo:
            QMessageBox.critical(self, "Falha", erro)

    def _thread_fim(self):
        self.thread = None
        self.pipeline = None
        if self.saindo:
            return
        self._ocupado(False)
        self._carregar_vault()   # o que o GameMind apagou por ter sumido do grafo sai da lista
        self._atualizar()
        if self.abas.isTabVisible(1) and not self.de_novo:
            self.chat.atualizar()   # a base do chat com o que acabou de ser lido
        if self.de_novo:
            self.de_novo = False
            self._processar()

    def _ocupado(self, sim: bool):
        """Durante a leitura, nada que mexa no jogo ou comece outro trabalho pode ser clicado (só Cancelar, acompanhar, abrir o
        vault, o registro e o tema)."""
        self.botao_iniciar.setEnabled(not sim)
        self.botao_cancelar.setVisible(sim)
        self.botao_voltar.setEnabled(not sim)
        self.botao_mais.setEnabled(not sim)
        for a in self.acoes_jogo + self.acoes_app:
            a.setEnabled(not sim)
        self.chat.ocupado(sim)
        self.progresso.setVisible(sim)
        if sim:
            self.progresso.setRange(0, 0)

    def _chat_pensando(self) -> bool:
        if self.chat.pensando:
            self.estado.setText("Espere a IA terminar de responder no chat.")
        return self.chat.pensando

    # ---------------------------------------------------------------- acompanhar a pasta
    def _texto_acompanhar(self, ligado: bool):
        self.botao_acompanhar.setText("  Acompanhando" if ligado else "  Acompanhar pasta")
        self._icone_olho()

    def _icone_olho(self):
        """O olho na cor do texto do botão: forte quando ligado (sobre o destaque), apagado quando desligado."""
        if aparencia.ATUAL:
            v = valores(aparencia.ATUAL)
            self.botao_acompanhar.setIcon(icone_olho(v["sobre_destaque"] if self.botao_acompanhar.isChecked() else v["apagado"]))

    def ao_mudar_tema(self, tema):
        if hasattr(self, "logo"):
            self.logo.setPixmap(logo(tema, 22))
            QApplication.instance().setWindowIcon(QIcon(logo(tema, 64)))   # a janela e a barra de tarefas
        if hasattr(self, "botao_acompanhar"):
            self._icone_olho()
            self.chat.ao_mudar_tema()

    def _observar(self, ligar: bool):
        for o in self.observadores:
            o.parar()
        self.observadores = []
        if getattr(self, "_timer", None):
            self._timer.stop()
        self._texto_acompanhar(ligar)
        if not ligar or not self.jogo:
            return
        pastas = [p for p in self.jogo.pastas() if p.is_dir()]
        if not pastas:
            QMessageBox.information(self, "Acompanhar", "As pastas de capturas deste jogo não foram encontradas. Escolha-as em Configurar jogo.")
            self.botao_acompanhar.setChecked(False)
            return
        conhecidos = {Path(m.caminho): m.tamanho for m in self.jogo.midias()}
        self.observadores = [Observador(p, None, self.config.observar_intervalo_s, conhecidos) for p in pastas]
        # a consulta (barata: só lista as pastas) roda num QTimer na thread da interface; não precisa de thread nem de sinais
        self._timer = QTimer(self, interval=self.config.observar_intervalo_s * 1000)
        self._timer.timeout.connect(self._consultar_pastas)
        self._timer.start()
        log.info("acompanhando %s", ", ".join(str(p) for p in pastas))

    def _consultar_pastas(self):
        novos = [n for o in self.observadores for n in o.consultar()]
        if novos:
            log.info("%d captura(s) nova(s)", len(novos))
            self._processar()

    def _atualizar(self):
        if self.jogo and not self.thread:
            r = self.jogo.resumo()
            self.estado.setText(f"{r['lida']} captura(s) lida(s), {r['pendente']} pendente(s), {r['erro']} com erro")

    # ---------------------------------------------------------------- menu Aplicativo
    def _configuracoes_gerais(self):
        """O que vale para todos os jogos: desempenho do OCR, idioma do texto e vídeo."""
        d = QDialog(self)
        d.setWindowTitle("Configurações gerais")
        form = QFormLayout()
        workers = QSpinBox(minimum=1, maximum=16, value=self.config.workers)
        idioma = QLineEdit(self.config.idioma_ocr, placeholderText="idiomas do Tesseract, separados por + (ex.: por+eng)")
        intervalo = QSpinBox(minimum=1, maximum=10, value=self.config.intervalo_video_s, suffix=" s")
        form.addRow("OCR em paralelo:", workers)
        form.addRow("Idioma do texto dos jogos:", idioma)
        form.addRow("Vídeo, um quadro a cada:", intervalo)
        salvar = QPushButton("Salvar")
        salvar.clicked.connect(d.accept)
        lay = QVBoxLayout(d)
        lay.addWidget(_painel("Configurações gerais", form, QLabel("Valem para todos os jogos. As pastas e a IA de cada jogo ficam em "
                                                                  "Jogo > Configurar jogo.", objectName="apagado", wordWrap=True)))
        lay.addWidget(salvar, alignment=Qt.AlignRight)
        if d.exec() == QDialog.Accepted:
            self.config.workers, self.config.intervalo_video_s = workers.value(), intervalo.value()
            self.config.idioma_ocr = idioma.text().strip() or "por+eng"
            self.config.salvar()
            self.estado.setText("Configurações gerais salvas")
        d.deleteLater()

    def _diagnostico(self):
        """Verifica o OCR, o FFmpeg, o modelo de imagem e a IA. Leva alguns segundos (programas e o Ollama são consultados): roda
        fora da interface, com a janela de espera mostrando cada passo."""
        if self.thread:
            return
        ia = self.config.do_jogo(self.jogo).ia if self.jogo else self.config.ia
        ok, itens = Espera(self, "Verificando o computador", PASSOS_VERIFICAR).executar(verificar, ia, self.config.idioma_ocr,
                                                                                        avisar=True)
        if not ok:
            QMessageBox.warning(self, "Verificar o computador", f"A verificação falhou:\n\n{itens}")
            return
        linhas = [f"<li><b>{'✔' if i.ok else ('✖' if i.obrigatorio else '!')} {html.escape(i.nome)}</b>: {html.escape(i.detalhe)}</li>"
                  for i in itens]
        d = QDialog(self)
        d.setWindowTitle("Verificar o computador")
        d.resize(640, 360)
        saida = QTextBrowser()
        saida.setHtml("<ul>" + "".join(linhas) + f"</ul><p>Jogos em: {html.escape(str(Jogo.raiz()))}</p>")
        QVBoxLayout(d).addWidget(_painel("Verificar o computador", saida))
        d.exec()
        d.deleteLater()

    def _mostrar_registro(self):
        if not getattr(self, "_janela_registro", None):
            self._janela_registro = QDialog(self)
            self._janela_registro.setWindowTitle("Registro")
            self._janela_registro.resize(800, 420)
            QVBoxLayout(self._janela_registro).addWidget(_painel("Registro", self.registro))
        self._janela_registro.show()
        self._janela_registro.raise_()

    def closeEvent(self, ev):
        if self.thread:
            if QMessageBox.question(self, "Sair", "Há uma leitura em andamento. Cancelar e sair?") != QMessageBox.Yes:
                ev.ignore()
                return
            self.pipeline.cancelar()
        self.saindo = True
        self._observar(False)
        pendentes = em_andamento()   # a leitura e buscas que ainda rodam (ex.: jogos instalados): terminam antes de fechar
        if pendentes:
            passo = "Terminando a captura em leitura e salvando" if self.thread else "Terminando o que estava em andamento"
            Espera(self, "Fechando o GameMind", [passo]).executar(lambda: [t.wait() for t in pendentes])
            for t in em_andamento():   # a da própria espera, que já acabou o trabalho
                t.wait(2000)
        logging.getLogger("gamemind").removeHandler(self.ponte_log)
        if self.jogo:
            self.jogo.fechar()
        ev.accept()


def iniciar() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("GameMind")
    j = Janela()
    j.show()
    return app.exec()
