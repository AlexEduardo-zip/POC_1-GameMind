"""Menus Ajuda e Sobre. A Ajuda é uma janela com guias curtos (lista à esquerda, texto à direita). Nos textos, um link
`copiar:<comando>` copia o comando para a área de transferência, `acao:<nome>` chama uma ação da janela principal (ex.:
verificar o computador) e os links da web abrem no navegador. Exemplos de jogo usam nomes inventados (Aldric, Vale Alto)."""
import html
from urllib.parse import quote, unquote

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QListWidget, QPushButton, QTextBrowser, QVBoxLayout

from .. import VERSAO
from . import aparencia
from .aparencia import brilhar, logo


def _cmd(comando: str) -> str:
    """Um comando de terminal com o link de copiar ao lado."""
    return f'<p><code>{html.escape(comando)}</code> &nbsp;<a href="copiar:{quote(comando)}">copiar</a></p>'


def _link(url: str, texto: str = "") -> str:
    return f'<a href="{url}">{html.escape(texto or url)}</a>'


# (chave, título, texto em HTML simples)
GUIAS = [
    ("inicio", "Primeiros passos", """
<h3>Primeiros passos</h3>
<p>O GameMind lê as screenshots e os vídeos que você grava enquanto joga e monta, sozinho, um caderno do jogo no Obsidian:
uma nota para cada personagem, lugar, facção e criatura, com as capturas em que apareceu e um quadro geral da partida.</p>
<ol>
<li><b>Adicione o jogo</b> no cartão <b>+ Adicionar jogo</b> da biblioteca. Um questionário pergunta o nome, as pastas onde as
capturas são gravadas e se você quer usar IA.</li>
<li><b>Jogue e capture</b> as telas com texto: diálogos com legenda, o diário de missões, o mapa, o bestiário.</li>
<li>Na página do jogo, clique em <b>Iniciar leitura</b>. Para ler sozinho enquanto joga, ligue <b>Acompanhar pasta</b> (o olho).</li>
<li>Clique em <b>Abrir no Obsidian</b> para explorar as notas, o grafo e o <i>Quadro da partida</i>.</li>
</ol>
<p>Nada precisa ser configurado à mão: os nomes do jogo (ex.: Aldric, Vale Alto) são aprendidos na leitura, e cada jogo
guarda o que aprendeu só para ele. Para mudar pastas ou a IA depois: <b>Jogo &gt; Configurar jogo</b> ou o botão <b>⋯</b>.</p>
<p>Antes de começar, vale usar <a href="acao:verificar">Verificar o computador</a>: ele diz se o OCR, o vídeo e a IA estão prontos.</p>
"""),
    ("ollama", "IA local (Ollama)", f"""
<h3>IA local com o Ollama</h3>
<p>Sem IA, o GameMind já reconhece personagens, lugares e facções pelo texto da tela. Com uma IA, ele também acha criaturas,
itens e as relações entre eles, e escreve um resumo de cada entidade. O <b>Ollama</b> roda essa IA <b>no seu computador</b>:
é gratuito e nenhuma captura sai do computador.</p>

<h4>1. Instalar o Ollama</h4>
<ul>
<li><b>Windows e macOS:</b> baixe o instalador em {_link("https://ollama.com/download")} e instale. O Ollama fica aberto em
segundo plano (ícone perto do relógio) e abre sozinho com o computador.</li>
<li><b>Linux:</b> no terminal:</li>
</ul>
{_cmd("curl -fsSL https://ollama.com/install.sh | sh")}

<h4>2. Baixar o modelo de texto</h4>
<p>Abra um terminal (no Windows: menu Iniciar, digite <i>PowerShell</i>) e rode o comando abaixo. São cerca de 4,7 GB, uma vez só.</p>
{_cmd("ollama pull qwen2.5:7b")}
<p>Computador com pouca memória de vídeo (menos de 6 GB)? Use o modelo menor, de cerca de 2 GB, e escreva <code>qwen2.5:3b</code>
no campo <i>modelo</i> do questionário:</p>
{_cmd("ollama pull qwen2.5:3b")}

<h4>3. Opcional: o modelo de imagem</h4>
<p>Com ele, o GameMind aprende uma vez por jogo onde ficam a legenda, o objetivo e os avisos na tela (cerca de 1 minuto),
e lê melhor. As imagens continuam no seu computador. São cerca de 6 GB (ou cerca de 3 GB na versão menor):</p>
{_cmd("ollama pull qwen2.5vl:7b")}
{_cmd("ollama pull qwen2.5vl:3b")}

<h4>4. Usar no GameMind</h4>
<ol>
<li>Em <b>Jogo &gt; Configurar jogo</b> (ou ao adicionar um jogo), responda <i>Sim, usar IA</i> e escolha <b>Ollama</b>.</li>
<li>Clique em <b>Testar conexão</b>. A primeira resposta demora mais (o modelo é carregado na memória, uns 20 s).</li>
<li>Clique em <b>Iniciar leitura</b>.</li>
</ol>
<p>Para conferir os modelos instalados: <code>ollama list</code>. Ou <a href="acao:verificar">verifique o computador</a>.</p>

<h4>Dicas</h4>
<ul>
<li>O modelo de 7B ocupa cerca de 5 GB de memória de vídeo. Ler depois de jogar evita disputar a placa com o jogo.</li>
<li>O modelo de texto e o de imagem não precisam caber juntos: o GameMind usa um de cada vez.</li>
</ul>

<h4>Se algo der errado</h4>
<ul>
<li><b>"O Ollama não está aberto"</b>: abra o Ollama pelo menu Iniciar, ou rode <code>ollama serve</code> num terminal.</li>
<li><b>Respostas vazias ou erro 500 seguidos</b>: descarregue o modelo e tente de novo:</li>
</ul>
{_cmd("ollama stop qwen2.5:7b")}
<ul><li><b>Muito lento</b>: use o modelo menor (<code>qwen2.5:3b</code>) ou feche o jogo durante a leitura.</li></ul>
<p>Documentação do Ollama: {_link("https://github.com/ollama/ollama/blob/main/README.md", "github.com/ollama/ollama")}</p>
"""),
    ("claude", "Claude com a sua conta", f"""
<h3>Claude com o login da sua assinatura</h3>
<p>Se você assina o Claude (Pro ou Max), o GameMind pode usá-lo no lugar da IA local, pelo <b>Claude Code</b>: sem chave de API
e sem cobrança por uso, mas descontando da cota do seu plano. Bom para quem não tem placa de vídeo.</p>
<ol>
<li>Instale o Claude Code: {_link("https://claude.com/claude-code")}.</li>
<li>Em <b>Jogo &gt; Configurar jogo</b>, escolha <b>Claude</b> e clique em <b>Entrar com a conta Claude</b>. Um terminal abre e
pede o login no navegador, se faltar.</li>
<li>Clique em <b>Testar conexão</b>.</li>
</ol>
<p><b>O que sai do computador:</b> só o texto lido das telas. Imagens e vídeos nunca saem.</p>
<p><b>Limites:</b> cerca de 10 s por captura; num lote grande a cota do plano pode acabar. O que já foi respondido fica
guardado e a leitura continua de onde parou na próxima vez.</p>
"""),
    ("chat", "Chat com a IA", """
<h3>Chat com a IA</h3>
<p>Na página do jogo, a aba <b>Conversar com a IA</b> responde perguntas sobre o que você já viu: quem é um personagem, onde
fica um lugar, o que aconteceu numa missão. Ela aparece quando o jogo usa uma IA (Ollama ou Claude) e já tem capturas lidas.</p>
<ul>
<li>A IA responde <b>só com o que foi lido das suas capturas</b>, nunca com o que ela sabe do jogo por fora: nada de spoiler.
Se algo ainda não apareceu nas capturas, ela diz isso.</li>
<li>Cada resposta mostra de quais capturas tirou a informação (<b>[1]</b>, <b>[2]</b>...). Clique para ver a captura na prévia.</li>
<li>Dá para continuar o assunto: depois de "Quem é Aldric?", pergunte "e onde ele mora?".</li>
<li>Durante a leitura das capturas o chat espera; ao terminar, ele já conhece o que foi lido.</li>
<li>A conversa fica guardada no jogo. <b>Limpar conversa</b> apaga; <b>Limpar vault &gt; Tudo</b> também.</li>
</ul>
<p>Com o Ollama, a primeira pergunta demora mais (o modelo é carregado). Com o Claude, só o texto lido e a pergunta saem do
computador.</p>
"""),
    ("capturas", "Capturas e pastas", """
<h3>Capturas e pastas</h3>
<p>O GameMind não copia nem altera as suas capturas: ele só lê as pastas onde a sua ferramenta grava.</p>
<ul>
<li><b>Steam:</b> tecla F12. O questionário já encontra a pasta do jogo pelo nome.</li>
<li><b>NVIDIA</b> (Alt+F1; vídeo Alt+F9), <b>AMD Adrenalin</b> (Ctrl+Shift+I; vídeo Ctrl+Shift+E) e <b>Xbox Game Bar</b> (Win+Alt+PrtScn), nos atalhos padrão:
as pastas delas aparecem como atalho no questionário.</li>
</ul>
<h4>O que capturar</h4>
<ul>
<li>Diálogos com a legenda ligada, o diário de missões, o mapa com os nomes, telas de bestiário e de personagens.</li>
<li>Clipes curtos de diálogo também servem: o GameMind lê um quadro a cada poucos segundos
(<b>Aplicativo &gt; Configurações gerais</b>).</li>
</ul>
<p>Com <b>Acompanhar pasta</b> ligado, cada captura nova é lida sozinha enquanto você joga.</p>
"""),
    ("obsidian", "Obsidian e o vault", f"""
<h3>Obsidian e o vault</h3>
<p>O resultado é um <i>vault</i> (uma pasta de notas) que se explora no <b>Obsidian</b>, gratuito:
{_link("https://obsidian.md/download")}. Instale e abra o Obsidian uma vez.</p>
<ul>
<li><b>Abrir no Obsidian</b> registra o vault do jogo no Obsidian e o abre. Se o Obsidian estiver aberto e ainda não conhecer
o vault, feche-o e clique de novo (ou use nele <i>Abrir pasta como cofre</i>).</li>
<li><b>Quadro da partida</b>: o mapa do mundo, com os protagonistas no alto e uma coluna por lugar, com as facções e
personagens dele.</li>
<li>Cada nota (ex.: <i>Aldric</i>) traz um resumo, as capturas em que apareceu e quem esteve junto.</li>
<li>A visão de grafo do Obsidian (Ctrl+G) mostra todas as ligações.</li>
</ul>
<p>Para refazer o vault sem perder a leitura: <b>Jogo &gt; Limpar vault</b>.</p>
"""),
    ("problemas", "Problemas comuns", f"""
<h3>Problemas comuns</h3>
<p>Comece por <a href="acao:verificar">Verificar o computador</a>: ele diz o que falta. Detalhes da última leitura ficam em
<b>Aplicativo &gt; Registro</b>.</p>
<ul>
<li><b>Tesseract (OCR) não encontrado:</b> no Windows, instale pelo
{_link("https://github.com/UB-Mannheim/tesseract/wiki", "instalador do Tesseract")}, marque os idiomas dos seus jogos
(ex.: <i>Portuguese</i>) e deixe-o no PATH. O idioma lido fica em <b>Aplicativo &gt; Configurações gerais</b>.</li>
<li><b>Vídeos dão erro:</b> falta o FFmpeg ({_link("https://ffmpeg.org/download.html")}). Imagens funcionam sem ele.</li>
<li><b>Nomes estranhos ou repetidos:</b> com IA, ligue <i>Revisar e resumir as entidades</i> no questionário: a IA junta as
grafias erradas de um mesmo nome.</li>
<li><b>Quero recomeçar do zero:</b> <b>Jogo &gt; Limpar vault &gt; Tudo</b> esquece o que foi lido e aprendido; as pastas e as
escolhas ficam. <b>Apagar jogo</b> tira o jogo da biblioteca (as capturas ficam).</li>
</ul>
"""),
]


class JanelaAjuda(QDialog):
    """Os guias. `acoes`: {nome: função} para os links `acao:<nome>` (ex.: "verificar")."""

    def __init__(self, pai, guia: str = "inicio", acoes: dict | None = None):
        super().__init__(pai)
        self.setWindowTitle("Ajuda do GameMind")
        self.resize(900, 600)
        self.acoes = acoes or {}
        self.lista = QListWidget(objectName="limpa")
        self.lista.setFixedWidth(220)
        for _, titulo, _ in GUIAS:
            self.lista.addItem(titulo)
        self.texto = QTextBrowser(openLinks=False)
        self.texto.anchorClicked.connect(self._link)
        self.aviso = QLabel(objectName="apagado")
        self.lista.currentRowChanged.connect(self._mostrar)
        fechar = QPushButton("Fechar")
        fechar.clicked.connect(self.accept)

        painel = QFrame(objectName="painel")
        corpo = QHBoxLayout(painel)
        corpo.setContentsMargins(16, 16, 16, 16)
        corpo.setSpacing(16)
        corpo.addWidget(self.lista)
        corpo.addWidget(self.texto, 1)
        brilhar(painel)
        rodape = QHBoxLayout()
        rodape.addWidget(self.aviso, 1)
        rodape.addWidget(fechar)
        lay = QVBoxLayout(self)
        lay.addWidget(painel, 1)
        lay.addLayout(rodape)
        self.lista.setCurrentRow(next((i for i, (k, _, _) in enumerate(GUIAS) if k == guia), 0))

    def _mostrar(self, i: int) -> None:
        if 0 <= i < len(GUIAS):
            self.texto.setHtml(GUIAS[i][2])
            self.aviso.setText("")

    def _link(self, url: QUrl) -> None:
        esquema, _, resto = url.toString(QUrl.FullyEncoded).partition(":")
        if esquema == "copiar":
            QGuiApplication.clipboard().setText(unquote(resto))
            self.aviso.setText(f"Copiado: {unquote(resto)}  (cole no terminal com Ctrl+V)")
        elif esquema == "acao" and resto in self.acoes:
            self.acoes[resto]()
        else:
            QDesktopServices.openUrl(url)


class JanelaSobre(QDialog):
    def __init__(self, pai, pasta_dados: str = ""):
        super().__init__(pai)
        self.setWindowTitle("Sobre o GameMind")
        painel = QFrame(objectName="painel")
        lay = QVBoxLayout(painel)
        lay.setContentsMargins(32, 32, 32, 24)
        lay.setSpacing(8)
        icone = QLabel(alignment=Qt.AlignCenter)
        if aparencia.ATUAL:
            icone.setPixmap(logo(aparencia.ATUAL, 72))
        lay.addWidget(icone)
        lay.addWidget(QLabel("GameMind", objectName="titulo", alignment=Qt.AlignCenter))
        lay.addWidget(QLabel(f"versão {VERSAO}", objectName="apagado", alignment=Qt.AlignCenter))
        lay.addSpacing(8)
        for texto in ("Lê as screenshots e os vídeos dos seus jogos (OCR e, se você quiser, IA) e monta um caderno do jogo no "
                      "Obsidian: personagens, lugares, facções, criaturas e as ligações entre eles.",
                      "Funciona com qualquer jogo, sem configuração: o que é de cada jogo é aprendido na leitura e fica só "
                      "na pasta dele.",
                      "Tudo roda no seu computador. As imagens nunca saem dele; só com o Claude ligado sai o texto lido das telas."):
            lay.addWidget(QLabel(texto, wordWrap=True, alignment=Qt.AlignCenter))
        lay.addSpacing(8)
        lay.addWidget(QLabel("Feito com PySide6 (Qt), Tesseract OCR, Ollama e Obsidian.", objectName="apagado",
                             wordWrap=True, alignment=Qt.AlignCenter))
        if pasta_dados:
            dados = QLabel(f'Seus jogos ficam em: <a href="{QUrl.fromLocalFile(pasta_dados).toString()}">'
                           f"{html.escape(pasta_dados)}</a>", objectName="apagado", wordWrap=True, alignment=Qt.AlignCenter,
                           textFormat=Qt.RichText, openExternalLinks=True)
            lay.addWidget(dados)
        brilhar(painel)
        fechar = QPushButton("Fechar")
        fechar.clicked.connect(self.accept)
        fora = QVBoxLayout(self)
        fora.addWidget(painel)
        fora.addWidget(fechar, alignment=Qt.AlignRight)
        self.setFixedWidth(520)


__all__ = ["GUIAS", "JanelaAjuda", "JanelaSobre"]
