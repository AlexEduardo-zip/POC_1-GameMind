"""Assistente de novo jogo: um questionário, uma pergunta por tela (nome, pastas, IA, qual IA e o login, regiões, revisão das
entidades) e, no fim, o resumo das escolhas. Também serve para reconfigurar um jogo (sem a pergunta do nome)."""
import html
import os
from pathlib import Path

from extracao.ia_publica import APELIDOS, ErroConector, abrir_login, achar_claude

from PySide6.QtCore import QFileInfo, QSize, Qt, Slot
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QButtonGroup, QDialog, QFileDialog, QFileIconProvider, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QPushButton, QRadioButton, QStackedWidget, QVBoxLayout, QWidget)

from ..nucleo import jogos_instalados, pastas_conhecidas, visao
from ..nucleo.diagnostico import passos_do_teste, testar_ia
from ..nucleo.repositorio import Jogo, nome_valido
from .aparencia import Carregando, aparecer
from .espera import Espera
from .tarefas import Funcao, em_thread

# (rótulo, provedor). As IAs cobradas por token (chave de API) foram retiradas por enquanto.
IAS = [("Ollama, no seu computador (gratuito; nada sai do computador)", "ollama"),
       ("Claude, com o login da sua assinatura (Claude Code; recebe só o texto lido, usa a cota do seu plano)", "claude-code")]


def _pagina(pergunta: str, explicacao: str = "") -> tuple[QWidget, QVBoxLayout]:
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.addWidget(QLabel(pergunta, objectName="pergunta", wordWrap=True))
    if explicacao:
        lay.addWidget(QLabel(explicacao, objectName="apagado", wordWrap=True))
    lay.addSpacing(8)
    return w, lay


def _sim_nao(lay: QVBoxLayout, sim: str, nao: str, marcado: bool) -> tuple[QRadioButton, QRadioButton]:
    grupo = QButtonGroup(lay.parentWidget())
    r_sim, r_nao = QRadioButton(sim), QRadioButton(nao)
    for r in (r_sim, r_nao):
        grupo.addButton(r)
        lay.addWidget(r)
    (r_sim if marcado else r_nao).setChecked(True)
    return r_sim, r_nao


class AssistenteJogo(QDialog):
    """`jogo`: reconfigura um jogo existente (a pergunta do nome é pulada). `resultado()` devolve as escolhas."""

    def __init__(self, parent=None, jogo: Jogo | None = None, ia_padrao: str = ""):
        super().__init__(parent)
        self.jogo = jogo
        self.setWindowTitle("Configurar jogo" if jogo else "Adicionar jogo")
        self.resize(640, 460)
        g = (lambda k, p=None: jogo.get(k, p)) if jogo else (lambda k, p=None: p)
        ia = g("ia", ia_padrao) or ""
        self.pilha = QStackedWidget()
        self.paginas: list[tuple[QWidget, callable]] = []   # (página, quando aparece)

        w, lay = _pagina("Qual é o jogo?", "Digite o nome ou escolha um dos jogos instalados neste computador. Opcional: com o "
                                             ".exe do jogo, o ícone dele vira a capa na biblioteca.")
        self.nome = QLineEdit(placeholderText="nome do jogo")
        lay.addWidget(self.nome)
        linha = QHBoxLayout()
        self.carregando_jogos = Carregando()
        self.status_jogos = QLabel(objectName="apagado")
        escolher_exe = QPushButton("Escolher o .exe...")
        escolher_exe.clicked.connect(self._escolher_exe)
        linha.addWidget(self.carregando_jogos)
        linha.addWidget(self.status_jogos, 1)
        linha.addWidget(escolher_exe)
        lay.addLayout(linha)
        self.lista_jogos = QListWidget()
        self.lista_jogos.setIconSize(QSize(28, 28))
        self.lista_jogos.itemClicked.connect(self._jogo_instalado)
        lay.addWidget(self.lista_jogos, 1)
        self.executavel = ""
        self._procurando_jogos = False
        self._modelos: list[str] | None = None
        self._add(w, lambda: jogo is None)

        w, lay = _pagina("Onde ficam as capturas do jogo?",
                         "As pastas onde a sua ferramenta de captura grava as screenshots e os vídeos. Pode ser uma só. "
                         "As pastas encontradas no computador aparecem como atalho.")
        self.pasta_capturas = self._campo_pasta(lay, "Screenshots", "screenshots", g("pasta_capturas", ""))
        self.pasta_videos = self._campo_pasta(lay, "Vídeos", "videos", g("pasta_videos", ""))
        lay.addStretch()
        self._add(w, lambda: True)

        w, lay = _pagina("Usar uma IA para entender as capturas?",
                         "Só com o OCR o GameMind lê o texto e reconhece os nomes que se repetem. Com IA, ele também acha "
                         "criaturas, itens, missões e as relações entre personagens e lugares.")
        self.usar_ia, self.sem_ia = _sim_nao(lay, "Sim, usar IA", "Não, só o OCR (mais rápido, acha menos)", bool(ia))
        lay.addStretch()
        self._add(w, lambda: True)

        w, lay = _pagina("Qual IA?", "Nenhuma das duas cobra por uso. As imagens nunca saem do computador.")
        grupo = QButtonGroup(w)
        self.opcoes_ia: dict[str, QRadioButton] = {}
        prov, _, modelo = ia.partition(":")
        prov = APELIDOS.get(prov.lower(), prov.lower())
        prov_atual, modelo = (prov, modelo) if prov in {p for _, p in IAS} else ("ollama", "")   # uma IA retirada volta ao Ollama
        for rotulo, p in IAS:
            r = QRadioButton(rotulo)
            r.toggled.connect(self._credencial)
            grupo.addButton(r)
            lay.addWidget(r)
            self.opcoes_ia[p] = r
        self.modelo = QLineEdit(modelo, placeholderText="modelo (vazio = o padrão da IA escolhida)")
        lay.addWidget(self.modelo)
        self.ajuda_ia = QLabel(objectName="apagado", wordWrap=True, textFormat=Qt.RichText, openExternalLinks=True)
        lay.addWidget(self.ajuda_ia)
        linha = QHBoxLayout()
        self.entrar = QPushButton("Entrar com a conta Claude")
        self.entrar.setToolTip("Abre o Claude Code num terminal: se ainda não entrou, ele pede o login no navegador")
        self.entrar.clicked.connect(self._entrar)
        testar = QPushButton("Testar conexão")
        testar.clicked.connect(self._testar)
        self.resultado_teste = QLabel(wordWrap=True)
        linha.addWidget(self.entrar)
        linha.addWidget(testar)
        linha.addWidget(self.resultado_teste, 1)
        lay.addLayout(linha)
        lay.addStretch()
        self._add(w, lambda: self.usar_ia.isChecked())
        self.opcoes_ia[prov_atual].setChecked(True)

        w, lay = _pagina("Aprender onde ficam a legenda, o objetivo e os avisos deste jogo?",
                         "Uma vez por jogo, um modelo de imagem do Ollama olha algumas capturas e ajusta as regiões em que o "
                         "texto é lido (leva cerca de 1 minuto). As imagens não saem do computador.")
        self.regioes, _ = _sim_nao(lay, "Sim, aprender as regiões", "Não, usar as regiões genéricas", g("regioes_por_imagem", True))
        self.ajuda_regioes = QLabel(objectName="apagado", wordWrap=True, textFormat=Qt.RichText)
        lay.addWidget(self.ajuda_regioes)
        lay.addStretch()
        self._add(w, lambda: self.usar_ia.isChecked())

        w, lay = _pagina("Revisar e resumir cada entidade com a IA?",
                         "Depois da leitura, a IA lê tudo o que o jogo mostrou sobre cada personagem, lugar ou criatura, escreve "
                         "um resumo de uma frase para a nota, corrige o tipo e junta nomes que são erros de leitura de outro.")
        self.revisar, _ = _sim_nao(lay, "Sim, revisar e resumir", "Não", g("revisar_entidades", True))
        self.ajuda_revisar = QLabel(objectName="apagado", wordWrap=True)
        lay.addWidget(self.ajuda_revisar)
        lay.addStretch()
        self._add(w, lambda: self.usar_ia.isChecked())

        w, lay = _pagina("Tudo certo?", "Você pode mudar estas escolhas depois, no menu Jogo > Configurar jogo.")
        self.resumo = QLabel(wordWrap=True, textFormat=Qt.RichText)
        lay.addWidget(self.resumo)
        lay.addStretch()
        self._add(w, lambda: True)

        self.aviso = QLabel(objectName="apagado", wordWrap=True)
        self.voltar, self.proximo = QPushButton("Voltar"), QPushButton("Próximo")
        cancelar = QPushButton("Cancelar")
        self.voltar.clicked.connect(lambda: self._ir(-1))
        self.proximo.clicked.connect(self._avancar)
        cancelar.clicked.connect(self.reject)
        rodape = QHBoxLayout()
        rodape.addWidget(cancelar)
        rodape.addStretch()
        rodape.addWidget(self.voltar)
        rodape.addWidget(self.proximo)
        geral = QVBoxLayout(self)
        geral.addWidget(QLabel("[ NOVO JOGO ]" if jogo is None else f"[ {html.escape(jogo.nome.upper())} ]", objectName="secao"))
        geral.addWidget(self.pilha, 1)
        geral.addWidget(self.aviso)
        geral.addLayout(rodape)
        self._ir(0, de=-1)

    # ---------------------------------------------------------------- montagem
    def _add(self, w: QWidget, aparece) -> None:
        self.pilha.addWidget(w)
        self.paginas.append((w, aparece))

    def _campo_pasta(self, lay: QVBoxLayout, rotulo: str, tipo: str, atual: str) -> QLineEdit:
        lay.addWidget(QLabel(rotulo))
        linha = QHBoxLayout()
        campo = QLineEdit(atual, placeholderText="nenhuma")
        escolher = QPushButton("Escolher...")
        escolher.clicked.connect(lambda: self._escolher(campo, tipo, rotulo))
        linha.addWidget(campo, 1)
        linha.addWidget(escolher)
        lay.addLayout(linha)
        atalhos = QHBoxLayout()
        for origem, pasta in pastas_conhecidas.sugestoes()[tipo][:3]:
            b = QPushButton(origem if origem.startswith("Steam") else f"{origem}: {pasta.name}")
            b.setToolTip(str(pasta))
            b.clicked.connect(lambda _=False, p=pasta: campo.setText(str(p)))
            atalhos.addWidget(b)
        atalhos.addStretch()
        lay.addLayout(atalhos)
        return campo

    def _escolher(self, campo: QLineEdit, tipo: str, rotulo: str) -> None:
        inicio = campo.text() if Path(campo.text()).is_dir() else str(pastas_conhecidas.inicio(tipo))
        p = QFileDialog.getExistingDirectory(self, f"Pasta de {rotulo.lower()}", inicio)
        if p:
            campo.setText(p)

    # ---------------------------------------------------------------- navegação
    def _visiveis(self) -> list[int]:
        return [i for i, (_, aparece) in enumerate(self.paginas) if aparece()]

    def _ir(self, passo: int, de: int | None = None) -> None:
        vis = self._visiveis()
        atual = self.pilha.currentIndex() if de is None else de
        pos = vis.index(atual) + passo if atual in vis else 0
        i = vis[max(0, min(len(vis) - 1, pos))]
        self.pilha.setCurrentIndex(i)
        aparecer(self.pilha.currentWidget())
        ultima = i == vis[-1]
        self.voltar.setEnabled(i != vis[0])
        self.proximo.setText("Concluir" if ultima else "Próximo")
        self.aviso.setText("")
        if self.pasta_capturas.parent() is self.pilha.widget(i) and not self.pasta_capturas.text() and self.jogo is None:
            achada = pastas_conhecidas.do_jogo(self.nome.text())   # a pasta da Steam do jogo com esse nome, se houver
            if achada:
                self.pasta_capturas.setText(str(achada))
                self.aviso.setText("Encontrei a pasta de capturas da Steam deste jogo.")
        if self.paginas[i][0] is self.pilha.widget(self.pilha.count() - 1):
            self.resumo.setText(self._texto_resumo())
        if self.ajuda_regioes.parent() is self.pilha.widget(i) and self._modelos is None:
            # perguntar ao Ollama leva alguns segundos: a janela de espera mostra o andamento e segura os outros cliques
            ok, modelos = Espera(self, "Verificando o Ollama", ["Procurando um modelo de imagem instalado"]).executar(
                visao.modelos_de_visao)
            self._modelos_achados(modelos if ok else [])
        if self.ajuda_revisar.parent() is self.pilha.widget(i):
            self.ajuda_revisar.setText("Com o Claude, é uma chamada a cada 6 entidades, descontada da cota do seu plano."
                                       if self._provedor() == "claude-code" else "")

    # ---------------------------------------------------------------- jogos instalados (em segundo plano, opcional)
    def showEvent(self, ev):
        super().showEvent(ev)
        if self.jogo is None and not self._procurando_jogos:
            # a busca não trava nada: dá para digitar o nome e seguir enquanto ela roda. Se a janela fechar antes, a thread
            # termina sozinha (tarefas.py a mantém viva) e o resultado é descartado.
            self._procurando_jogos = True
            self.carregando_jogos.iniciar()
            self.status_jogos.setText("procurando os jogos instalados...")
            f = Funcao(jogos_instalados.listar)
            f.concluido.connect(self._jogos_achados)
            f.falhou.connect(self._busca_falhou)
            em_thread(f)

    @Slot(str)
    def _busca_falhou(self, _erro: str) -> None:
        self._jogos_achados([])

    @Slot(object)
    def _jogos_achados(self, jogos: list) -> None:
        self.carregando_jogos.parar()
        self.status_jogos.setText(f"{len(jogos)} jogo(s) instalado(s) encontrado(s)" if jogos else
                                  "nenhum jogo instalado encontrado: digite o nome (e, se quiser, escolha o .exe)")
        icones = QFileIconProvider()
        for j in jogos:
            item = QListWidgetItem(icones.icon(QFileInfo(str(j.executavel))) if j.executavel else QIcon(), f"{j.nome}   ·   {j.origem}")
            item.setData(Qt.UserRole, [j.nome, str(j.executavel or "")])
            self.lista_jogos.addItem(item)

    def _jogo_instalado(self, item: QListWidgetItem) -> None:
        self.nome.setText(item.data(Qt.UserRole)[0])
        self.executavel = item.data(Qt.UserRole)[1]
        if not self.executavel:
            self.status_jogos.setText("não achei o .exe deste jogo; se quiser o ícone, escolha com o botão ao lado")

    def _escolher_exe(self) -> None:
        inicio = next((p for p in (Path(os.environ.get("ProgramFiles(x86)", "")) / "Steam" / "steamapps" / "common",
                                   Path(os.environ.get("ProgramFiles", "C:/Program Files"))) if p.is_dir()), Path.home())
        p, _ = QFileDialog.getOpenFileName(self, "Executável do jogo", str(inicio), "Executáveis (*.exe)")
        if p:
            self.executavel = p
            if not self.nome.text().strip():
                self.nome.setText(Path(p).parent.name)
            self.status_jogos.setText(f"ícone de {Path(p).name}")

    def _modelos_achados(self, modelos: list) -> None:
        self._modelos = modelos
        self.ajuda_regioes.setText(f"Modelo de imagem encontrado: <b>{html.escape(modelos[0])}</b>." if modelos else
                                   "Nenhum modelo de imagem no Ollama ainda. Para usar, rode <code>ollama pull qwen2.5vl:7b</code>; "
                                   "até lá, ficam as regiões genéricas.")

    def _avancar(self) -> None:
        erro = self._validar(self.pilha.currentIndex())
        if erro:
            self.aviso.setText(erro)
            return
        if self.proximo.text() == "Concluir":
            self.accept()
        else:
            self._ir(1)

    def _validar(self, i: int) -> str:
        w = self.paginas[i][0]
        if self.nome.parent() is w:
            try:
                nome = nome_valido(self.nome.text())
            except ValueError as e:
                return str(e)
            if nome in Jogo.listar():
                return f"Já existe um jogo chamado {nome}."
        if self.pasta_capturas.parent() is w:
            pastas = [c.text().strip() for c in (self.pasta_capturas, self.pasta_videos) if c.text().strip()]
            if not pastas:
                return "Escolha ao menos uma pasta."
            faltam = [p for p in pastas if not Path(p).is_dir()]
            if faltam:
                return f"Pasta não encontrada: {faltam[0]}"
        return ""

    # ---------------------------------------------------------------- IA
    def _provedor(self) -> str:
        return next((p for p, r in self.opcoes_ia.items() if r.isChecked()), "ollama")

    def _credencial(self) -> None:
        claude = self._provedor() == "claude-code"
        self.entrar.setVisible(claude)
        self.resultado_teste.setText("")
        if not claude:
            self.ajuda_ia.setText("Precisa do Ollama aberto e de um modelo de texto (ex.: <code>ollama pull qwen2.5:7b</code>).")
            return
        try:
            achar_claude()
            instalado = True
        except ErroConector:
            instalado = False
        self.entrar.setEnabled(instalado)
        self.ajuda_ia.setText(
            "Usa o Claude Code com o login da sua assinatura (Pro ou Max): sem chave e sem cobrança por uso, mas desconta da cota do "
            "plano. Recebe só o texto lido das capturas. Se ainda não entrou, clique em <b>Entrar com a conta Claude</b>, faça o "
            "login no navegador e volte para testar." if instalado else
            "O Claude Code não está instalado neste computador. Instale em "
            "<a href='https://claude.com/claude-code'>claude.com/claude-code</a> e depois entre com a sua conta.")

    def _entrar(self) -> None:
        try:
            abrir_login()
        except ErroConector as e:
            self.resultado_teste.setText(str(e))
            return
        self.resultado_teste.setText("Abri o Claude Code num terminal. Entre com a sua conta, feche o terminal e clique em Testar conexão.")

    def _ia(self) -> str:
        prov, modelo = self._provedor(), self.modelo.text().strip()
        return f"{prov}:{modelo}" if modelo else prov

    def _testar(self) -> None:
        ia = self._ia()
        ok, r = Espera(self, "Testando a conexão com a IA", passos_do_teste(ia)).executar(testar_ia, ia, avisar=True)
        self.resultado_teste.setText("Funcionou." if ok else f"Falhou: {str(r)[:200]}")

    # ---------------------------------------------------------------- resultado
    def _texto_resumo(self) -> str:
        r = self.resultado()
        pastas = "<br>".join(html.escape(p) for p in (r["pasta_capturas"], r["pasta_videos"]) if p) or "nenhuma"
        linhas = ([f"<b>Jogo:</b> {html.escape(r['nome'])}"] if self.jogo is None else []) + [
            f"<b>Pastas:</b><br>{pastas}", f"<b>IA:</b> {html.escape(r['ia']) if r['ia'] else 'não (só OCR)'}"]
        if r["ia"]:
            linhas += [f"<b>Aprender as regiões:</b> {'sim' if r['regioes_por_imagem'] else 'não'}",
                       f"<b>Revisar e resumir as entidades:</b> {'sim' if r['revisar_entidades'] else 'não'}"]
        return "<br><br>".join(linhas)

    def resultado(self) -> dict:
        """As escolhas: nome, pastas, IA ("" = só OCR), regiões, revisão e o .exe do jogo."""
        com_ia = self.usar_ia.isChecked()
        return {"nome": self.jogo.nome if self.jogo else self.nome.text().strip(),
                "pasta_capturas": self.pasta_capturas.text().strip(), "pasta_videos": self.pasta_videos.text().strip(),
                "ia": self._ia() if com_ia else "", "regioes_por_imagem": com_ia and self.regioes.isChecked(),
                "revisar_entidades": com_ia and self.revisar.isChecked(), "executavel": self.executavel}


__all__ = ["AssistenteJogo", "IAS"]
