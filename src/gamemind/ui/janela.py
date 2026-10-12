"""Janela principal do GameMind (PySide6).
Uma tela de trabalho (jogo, pasta de capturas, a captura que está sendo lida e as notas do vault que vão sendo criadas),
mais Configurações (IA, desempenho, diagnóstico) e Registro. O grafo se explora no Obsidian. Toda a lógica está no núcleo;
aqui só há apresentação e encadeamento de ações."""
import html
import logging
import sys
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QImage, QPixmap
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog, QFormLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
                               QSizePolicy, QSpinBox, QSplitter, QTabWidget, QTextBrowser, QVBoxLayout, QWidget)

from .. import VERSAO
from ..nucleo.config import Config
from ..nucleo.diagnostico import testar_ia, verificar
from ..nucleo import obsidian
from ..nucleo.observador import Observador
from ..nucleo.pipeline import Pipeline, Progresso
from ..nucleo.recursos import EXT_CLIPE
from ..nucleo.repositorio import Jogo
from .tarefas import Funcao, PonteLog, Trabalhador, em_thread

log = logging.getLogger("gamemind")

# (rótulo, provedor) das opções de IA; o modelo vai num campo à parte (vazio = padrão do provedor)
OPCOES_IA = [("Nenhuma (só OCR, dicionário e regras)", ""), ("Local: Ollama", "ollama"), ("OpenAI (ChatGPT/Codex), API", "openai"),
             ("Google Gemini, API", "gemini"), ("Anthropic Claude, API", "claude"), ("Claude Code (plano Pro/Max, sem chave)", "claude-code")]
ETAPAS = {"registro": "Procurando capturas", "regioes": "Aprendendo onde fica o texto", "leitura": "Lendo o texto das capturas",
          "llm": "Consultando a IA", "grafo": "Montando o grafo e os nomes do jogo",
          "vault": "Criando as notas do vault"}
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
        self.setStyleSheet("background: #1b1b1f; color: #9a9aa5; border-radius: 6px;")
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


class Janela(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"GameMind {VERSAO}")
        self.resize(1100, 720)
        self.config = Config.carregar()
        self.jogo: Jogo | None = None
        self.pipeline: Pipeline | None = None
        self.thread = None
        self.observador: Observador | None = None
        self.de_novo = False   # chegou mídia nova durante uma rodada: roda outra ao terminar
        self.com_ia = False    # modo da última rodada pedida (o observador e a rodada extra repetem o mesmo modo)
        self.arquivo_atual = ""
        self.itens_vault: dict[str, QListWidgetItem] = {}

        self.ponte_log = PonteLog()
        logging.getLogger("gamemind").addHandler(self.ponte_log)
        logging.getLogger("gamemind").setLevel(logging.INFO)

        self.abas = QTabWidget()
        self.abas.addTab(self._aba_principal(), "Processamento")
        self.abas.addTab(self._aba_config(), "Configurações")
        self.abas.addTab(self._aba_registro(), "Registro")
        self.setCentralWidget(self.abas)
        self._rotulo_ia()
        self.progresso = QProgressBar()
        self.progresso.setMaximumWidth(260)
        self.progresso.hide()
        self.estado = QLabel()
        self.statusBar().addWidget(self.estado, 1)
        self.statusBar().addPermanentWidget(self.progresso)

        nomes = Jogo.listar()
        self._recarregar_jogos(self.config.ultimo_jogo if self.config.ultimo_jogo in nomes else (nomes[0] if nomes else ""))

    # ---------------------------------------------------------------- construção
    def _aba_principal(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)

        topo = QHBoxLayout()
        topo.addWidget(QLabel("Jogo:"))
        self.combo_jogo = QComboBox()
        self.combo_jogo.setMinimumWidth(180)
        self.combo_jogo.currentTextChanged.connect(self._abrir_jogo)
        topo.addWidget(self.combo_jogo)
        self.botao_novo = QPushButton("Novo jogo")
        self.botao_novo.clicked.connect(self._novo_jogo)
        topo.addWidget(self.botao_novo)
        topo.addSpacing(16)
        topo.addWidget(QLabel("Capturas em:"))
        self.campo_capturas = QLineEdit()
        self.campo_capturas.setPlaceholderText("pasta onde as capturas e os vídeos do jogo são gravados")
        self.campo_capturas.editingFinished.connect(self._salvar_pasta)
        topo.addWidget(self.campo_capturas, 1)
        self.botao_pasta = QPushButton("Escolher...")
        self.botao_pasta.clicked.connect(self._escolher_pasta)
        topo.addWidget(self.botao_pasta)
        lay.addLayout(topo)

        botoes = QHBoxLayout()
        self.botao_ocr = QPushButton("Processar só OCR")
        self.botao_ocr.setToolTip("Lê o texto das capturas e reconhece os nomes aprendidos, sem usar IA")
        self.botao_ocr.clicked.connect(lambda: self._processar(False))
        self.botao_ia = QPushButton("Processar com IA")
        self.botao_ia.clicked.connect(lambda: self._processar(True))
        self.botao_cancelar = QPushButton("Cancelar")
        self.botao_cancelar.setEnabled(False)
        self.botao_cancelar.clicked.connect(self._cancelar)
        self.chk_observar = QCheckBox("Observar a pasta")
        self.chk_observar.setToolTip("Processa sozinho as capturas novas que aparecerem na pasta")
        self.chk_observar.toggled.connect(self._observar)
        self.botao_obsidian = QPushButton("Abrir no Obsidian")
        self.botao_obsidian.setToolTip("O grafo e os canvas se exploram no Obsidian (Graph view)")
        self.botao_obsidian.clicked.connect(self._abrir_obsidian)
        for b in (self.botao_ocr, self.botao_ia, self.botao_cancelar, self.chk_observar):
            botoes.addWidget(b)
        botoes.addStretch()
        botoes.addWidget(self.botao_obsidian)
        lay.addLayout(botoes)

        esquerda, direita = QWidget(), QWidget()
        le, ld = QVBoxLayout(esquerda), QVBoxLayout(direita)
        for l in (le, ld):
            l.setContentsMargins(0, 0, 0, 0)
        self.previa = Previa()
        self.legenda = QLabel("")
        self.legenda.setAlignment(Qt.AlignCenter)
        self.legenda.setWordWrap(True)
        le.addWidget(self.previa, 1)
        le.addWidget(self.legenda)
        self.titulo_vault = QLabel()
        self.lista_vault = QListWidget()
        self.lista_vault.setToolTip("Clique duas vezes para abrir a nota no Obsidian")
        self.lista_vault.itemActivated.connect(self._abrir_nota)
        ld.addWidget(self.titulo_vault)
        ld.addWidget(self.lista_vault, 1)
        div = QSplitter()
        div.addWidget(esquerda)
        div.addWidget(direita)
        div.setSizes([620, 400])
        lay.addWidget(div, 1)
        return w

    def _aba_config(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        form = QFormLayout()
        self.combo_ia = QComboBox()
        for rotulo, prov in OPCOES_IA:
            self.combo_ia.addItem(rotulo, prov)
        self.campo_modelo = QLineEdit()
        self.campo_modelo.setPlaceholderText("vazio = modelo padrão do provedor (ex.: qwen2.5:7b, gpt-5-mini, sonnet)")
        prov, _, modelo = self.config.ia.partition(":")
        prov = prov if prov in {p for _, p in OPCOES_IA} else ("ollama" if self.config.ia else "")
        if prov == "ollama" and self.config.ia and not self.config.ia.startswith("ollama"):
            modelo = self.config.ia   # modelo do Ollama sem prefixo
        self.combo_ia.setCurrentIndex(max(0, self.combo_ia.findData(prov)))
        self.campo_modelo.setText(modelo)
        form.addRow("IA para relações:", self.combo_ia)
        form.addRow("Modelo:", self.campo_modelo)
        self.spin_workers = QSpinBox(minimum=1, maximum=16, value=self.config.workers)
        form.addRow("OCR em paralelo:", self.spin_workers)
        self.campo_idioma = QLineEdit(self.config.idioma_ocr)
        self.campo_idioma.setPlaceholderText("idiomas do Tesseract, separados por + (ex.: por+eng)")
        form.addRow("Idioma do texto dos jogos:", self.campo_idioma)
        self.spin_intervalo = QSpinBox(minimum=1, maximum=10, value=self.config.intervalo_video_s, suffix=" s")
        form.addRow("Vídeo, um quadro a cada:", self.spin_intervalo)
        lay.addLayout(form)
        botoes = QHBoxLayout()
        salvar = QPushButton("Salvar")
        salvar.clicked.connect(self._salvar_config)
        testar = QPushButton("Testar conexão com a IA")
        testar.clicked.connect(self._testar_ia)
        diag = QPushButton("Verificar o computador")
        diag.clicked.connect(self._diagnostico)
        for b in (salvar, testar, diag):
            botoes.addWidget(b)
        botoes.addStretch()
        lay.addLayout(botoes)
        aviso = QLabel("A IA pública recebe só o texto lido da tela, nunca as imagens. Chaves de API ficam no arquivo .env "
                       "(veja docs/ia-publica.md). O Claude Code usa o login da sua assinatura e consome a cota do plano.")
        aviso.setWordWrap(True)
        lay.addWidget(aviso)
        self.saida_diag = QTextBrowser()
        lay.addWidget(self.saida_diag)
        return w

    def _aba_registro(self) -> QWidget:
        self.registro = QPlainTextEdit(readOnly=True)
        self.registro.setMaximumBlockCount(5000)
        self.ponte_log.linha.connect(self.registro.appendPlainText)
        return self.registro

    # ---------------------------------------------------------------- jogo
    def _recarregar_jogos(self, selecionar: str = ""):
        self.combo_jogo.blockSignals(True)
        self.combo_jogo.clear()
        self.combo_jogo.addItems(Jogo.listar())
        self.combo_jogo.blockSignals(False)
        if selecionar:
            self.combo_jogo.setCurrentText(selecionar)
        self._abrir_jogo(selecionar)

    def _novo_jogo(self):
        nome, ok = QInputDialog.getText(self, "Novo jogo", "Nome do jogo (cada jogo tem a sua pasta e o seu vault):")
        if ok and nome.strip():
            try:
                Jogo.abrir(nome).fechar()
            except ValueError as e:
                QMessageBox.warning(self, "Nome inválido", str(e))
                return
            self._recarregar_jogos(nome.strip())

    def _abrir_jogo(self, nome: str):
        if self.thread:
            return
        self._observar(False)
        self.chk_observar.setChecked(False)
        if self.jogo:
            self.jogo.fechar()
        self.jogo = Jogo.abrir(nome) if nome else None
        tem = self.jogo is not None
        for wdg in (self.campo_capturas, self.botao_pasta, self.chk_observar, self.botao_ocr, self.botao_ia, self.botao_obsidian):
            wdg.setEnabled(tem)
        self.campo_capturas.setText(self.jogo.get("pasta_capturas", "") if tem else "")
        if tem:
            self.config.ultimo_jogo = nome
            self.config.salvar()
        self.arquivo_atual = ""
        self.previa.mostrar(None, "Nenhum arquivo em processamento")
        self.legenda.setText("")
        if tem:
            self._carregar_vault()
        else:
            self.lista_vault.clear()
            self.itens_vault.clear()
            self.estado.setText("Crie um jogo para começar (botão Novo jogo).")
        self._atualizar()

    def _escolher_pasta(self):
        p = QFileDialog.getExistingDirectory(self, "Pasta de capturas", self.campo_capturas.text() or str(Path.home()))
        if p:
            self.campo_capturas.setText(p)
            self._salvar_pasta()

    def _salvar_pasta(self):
        self.jogo.set("pasta_capturas", self.campo_capturas.text().strip())

    def _abrir_no_obsidian(self, arquivo: Path | None = None):
        """Abre o vault (ou uma nota) no Obsidian, registrando o vault nele se for preciso (nucleo/obsidian.py)."""
        url, aviso = obsidian.link(self.jogo.pasta_vault, arquivo)
        if url and QDesktopServices.openUrl(QUrl(url)):
            return
        if aviso:
            QMessageBox.information(self, "Obsidian", aviso)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.jogo.pasta_vault)))   # ao menos mostra a pasta

    def _abrir_obsidian(self):
        self._abrir_no_obsidian()

    # ---------------------------------------------------------------- vault
    def _carregar_vault(self):
        """Lista as notas que o vault já tem, das mais recentes para as mais antigas."""
        self.lista_vault.clear()
        self.itens_vault.clear()
        vault = self.jogo.pasta_vault
        arquivos = [a for padrao in NOTAS_VAULT for a in vault.rglob(padrao) if not any(p.startswith(".") for p in a.relative_to(vault).parts)]
        for a in sorted(arquivos, key=lambda a: a.stat().st_mtime):
            self._nota_criada(a)

    def _nota_criada(self, caminho: Path):
        chave = str(caminho)
        if chave in self.itens_vault:
            self.lista_vault.takeItem(self.lista_vault.row(self.itens_vault[chave]))
        rel = caminho.relative_to(self.jogo.pasta_vault).as_posix() if caminho.is_relative_to(self.jogo.pasta_vault) else caminho.name
        item = QListWidgetItem(rel)
        item.setData(Qt.UserRole, chave)
        self.lista_vault.insertItem(0, item)
        self.itens_vault[chave] = item
        self.titulo_vault.setText(f"<b>Notas no vault</b> ({self.lista_vault.count()})")

    def _abrir_nota(self, item: QListWidgetItem):
        self._abrir_no_obsidian(Path(item.data(Qt.UserRole)))

    # ---------------------------------------------------------------- processamento
    def _rotulo_ia(self):
        """O botão de IA diz qual IA está configurada (a escolha fica na aba Configurações)."""
        self.botao_ia.setText(f"Processar com IA ({self.config.ia})" if self.config.ia else "Processar com IA")
        self.botao_ia.setToolTip("Lê o texto e usa a IA escolhida na aba Configurações para achar o que o OCR sozinho não acha"
                                 if self.config.ia else "Nenhuma IA configurada: escolha uma na aba Configurações")

    def _processar(self, com_ia: bool | None = None):
        """`com_ia`: True roda OCR + IA (a da aba Configurações), False só o OCR; None repete o modo da última rodada."""
        if com_ia is not None:
            if com_ia and not self.config.ia:
                QMessageBox.information(self, "IA", "Nenhuma IA configurada. Escolha uma na aba Configurações e clique em Salvar.")
                self.abas.setCurrentIndex(1)
                return
            self.com_ia = com_ia
        if not self.jogo or self.thread:
            self.de_novo = bool(self.thread)
            return
        if not self.jogo.get("pasta_capturas"):
            QMessageBox.information(self, "Pasta de capturas", "Escolha primeiro a pasta onde ficam as capturas do jogo.")
            return
        cfg = self.config if self.com_ia else replace(self.config, ia="")
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
            self.estado.setText("Cancelando depois da mídia atual...")

    def _progresso(self, p: Progresso):
        etapa = ETAPAS.get(p.etapa, p.etapa)
        self.estado.setText(f"{etapa}: {p.mensagem}")
        if p.etapa == "vault" and p.arquivo:
            self._nota_criada(Path(p.arquivo))
            self.legenda.setText(etapa)
        elif p.etapa in ("leitura", "llm") and p.arquivo:   # a captura em andamento aparece na leitura e também na consulta à IA
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
        if r["erro_llm"]:
            QMessageBox.warning(self, "IA", f"O grafo foi gerado, mas a IA falhou:\n\n{r['erro_llm']}")

    def _falhou(self, erro: str):
        self.estado.setText("Falha no processamento (veja a aba Registro)")
        QMessageBox.critical(self, "Falha", erro)

    def _thread_fim(self):
        self.thread = None
        self.pipeline = None
        self._ocupado(False)
        self._carregar_vault()   # o que o GameMind apagou por ter sumido do grafo sai da lista
        self._atualizar()
        if self.de_novo:
            self.de_novo = False
            self._processar()

    def _ocupado(self, sim: bool):
        self.botao_ocr.setEnabled(not sim and self.jogo is not None)
        self.botao_ia.setEnabled(not sim and self.jogo is not None)
        self.botao_cancelar.setEnabled(sim)
        self.combo_jogo.setEnabled(not sim)
        self.botao_novo.setEnabled(not sim)
        self.campo_capturas.setEnabled(not sim)
        self.botao_pasta.setEnabled(not sim)
        self.progresso.setVisible(sim)
        if sim:
            self.progresso.setRange(0, 0)

    def _observar(self, ligar: bool):
        if self.observador:
            self.observador.parar()
            self.observador = None
        if not ligar or not self.jogo:
            return
        pasta = self.jogo.get("pasta_capturas")
        if not pasta or not Path(pasta).is_dir():
            QMessageBox.information(self, "Observar", "Escolha uma pasta de capturas existente.")
            self.chk_observar.setChecked(False)
            return
        conhecidos = {Path(m.caminho): m.tamanho for m in self.jogo.midias()}
        self.observador = Observador(Path(pasta), None, self.config.observar_intervalo_s, conhecidos)
        # a consulta (barata: só lista a pasta) roda num QTimer na thread da interface; não precisa de thread nem de sinais
        self._timer = QTimer(self, interval=self.config.observar_intervalo_s * 1000)
        self._timer.timeout.connect(self._consultar_pasta)
        self._timer.start()
        log.info("observando %s", pasta)

    def _consultar_pasta(self):
        if not self.observador:
            self._timer.stop()
            return
        novos = self.observador.consultar()
        if novos:
            log.info("%d captura(s) nova(s) na pasta", len(novos))
            self._processar()

    def _atualizar(self):
        if self.jogo and not self.thread:
            r = self.jogo.resumo()
            self.estado.setText(f"{r['lida']} captura(s) lida(s), {r['pendente']} pendente(s), {r['erro']} com erro")

    # ---------------------------------------------------------------- configurações
    def _ia_escolhida(self) -> str:
        prov, modelo = self.combo_ia.currentData(), self.campo_modelo.text().strip()
        return "" if not prov else f"{prov}:{modelo}" if modelo else prov

    def _salvar_config(self):
        self.config.ia = self._ia_escolhida()
        self.config.workers = self.spin_workers.value()
        self.config.idioma_ocr = self.campo_idioma.text().strip() or "por+eng"
        self.config.intervalo_video_s = self.spin_intervalo.value()
        self.config.salvar()
        self._rotulo_ia()
        self.estado.setText(f"Configuração salva (IA: {self.config.ia or 'nenhuma'})")

    def _testar_ia(self):
        ia = self._ia_escolhida()
        if not ia:
            self.saida_diag.setPlainText("Nenhuma IA escolhida.")
            return
        self.saida_diag.setPlainText(f"Chamando {ia}... (pode levar alguns segundos)")
        f = Funcao(testar_ia, ia)
        f.concluido.connect(lambda txt: self.saida_diag.setPlainText("OK: " + txt))
        f.falhou.connect(lambda err: self.saida_diag.setPlainText("FALHOU: " + err))
        self._thread_teste = em_thread(f)

    def _diagnostico(self):
        itens = verificar(self._ia_escolhida(), self.config.idioma_ocr)
        linhas = [f"<li><b>{'✔' if i.ok else ('✖' if i.obrigatorio else '!')} {html.escape(i.nome)}</b>: {html.escape(i.detalhe)}</li>"
                  for i in itens]
        self.saida_diag.setHtml("<ul>" + "".join(linhas) + f"</ul><p>Jogos em: {html.escape(str(Jogo.raiz()))}</p>")

    def closeEvent(self, ev):
        if self.thread:
            if QMessageBox.question(self, "Sair", "Há um processamento em andamento. Cancelar e sair?") != QMessageBox.Yes:
                ev.ignore()
                return
            self.pipeline.cancelar()
            self.thread.wait(120000)
        self._observar(False)
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
