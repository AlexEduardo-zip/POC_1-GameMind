"""Chat com a IA: base de conhecimento, busca, conversa e disponibilidade (sem IA de verdade)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parent.parent / "src")]
os.environ.setdefault("GAMEMIND_DADOS", tempfile.mkdtemp())

from gamemind.nucleo import chat  # noqa: E402

GRAFO = {"nos": [
    {"nome": "Aldric", "tipo": "personagem", "aliases": ["Capitão Aldric"], "descricao": "Capitão da guarda de Vale Alto.",
     "fontes": [{"arquivo": "a.jpg"}, {"arquivo": "b.jpg"}, {"arquivo": "c.jpg"}]},
    {"nome": "Ravena", "tipo": "personagem", "descricao": "Feiticeira que procura o capitão.", "fontes": [{"arquivo": "c.jpg"}]},
    {"nome": "Vale Alto", "tipo": "local", "fontes": [{"arquivo": "a.jpg"}, {"arquivo": "d.jpg"}]},
    {"nome": "Ordem do Corvo", "tipo": "faccao", "fontes": [{"arquivo": "d.jpg"}]}],
    "arestas": [{"sujeito": "Aldric", "predicado": "membro_de", "objeto": "Ordem do Corvo", "fontes": []}]}


def leitura(*secoes):
    return {"quadros": [{"t": 0, "secoes": dict(secoes)}]}


LEITURAS = {
    "a.jpg": leitura(("legenda", "Aldric: O portão de Vale Alto fecha ao anoitecer."), ("tela", "|| = 6 &\nAldric: O portão de Vale Alto fecha ao anoitecer.")),
    "b.jpg": leitura(("legenda", "Aldric: Traga as ervas do pântano.")),
    "c.jpg": leitura(("legenda", "Ravena: Onde está o capitão? Preciso da espada antiga.")),
    "d.jpg": leitura(("aviso", "Nova área descoberta: Vale Alto\nA Ordem do Corvo guarda a ponte.")),
    "e.jpg": leitura(("tela", "@ # 4 ||\n= =")),   # só ruído: não vira trecho
}


class TestBase(unittest.TestCase):
    def setUp(self):
        self.base = chat.Base.de_dados(GRAFO, LEITURAS)

    def test_trechos_sem_ruido_e_sem_repeticao(self):
        self.assertEqual([t.arquivo for t in self.base.trechos], ["a.jpg", "b.jpg", "c.jpg", "d.jpg"])
        self.assertEqual(self.base.trechos[0].texto, "Aldric: O portão de Vale Alto fecha ao anoitecer.")   # a tela repetia a legenda

    def test_entidades_citadas_pelo_nome_outro_nome_ou_grafia_parecida(self):
        nomes = lambda p: [e.nome for e in self.base.citadas(p)]   # noqa: E731
        self.assertEqual(nomes("Quem é Aldric?"), ["Aldric"])
        self.assertEqual(nomes("o que o capitão aldric faz"), ["Aldric"])
        self.assertEqual(nomes("quem é Aldrik?"), ["Aldric"])                   # erro de digitação
        self.assertEqual(nomes("fale da ordem do corvo"), ["Ordem do Corvo"])
        self.assertEqual(nomes("qual o clima hoje?"), [])

    def test_busca_traz_a_entidade_as_relacoes_e_os_trechos_dela(self):
        ctx = self.base.buscar("Quem é Aldric?")
        self.assertEqual(ctx.entidades[0].nome, "Aldric")
        self.assertIn("Ordem do Corvo", [e.nome for e in ctx.entidades])          # vizinha pela relação
        self.assertEqual({t.arquivo for t in ctx.trechos[:2]}, {"a.jpg", "b.jpg"})
        texto = ctx.texto()
        self.assertIn("Aldric membro de Ordem do Corvo", texto)
        self.assertIn("[C1]", texto)
        self.assertEqual(set(ctx.fontes.values()), {t.arquivo for t in ctx.trechos})

    def test_pergunta_de_continuacao_herda_a_entidade(self):
        ctx = self.base.buscar("e o que ela procura?", anteriores=["Quem é Ravena?"])
        self.assertEqual(ctx.entidades[0].nome, "Ravena")
        self.assertEqual(ctx.trechos[0].arquivo, "c.jpg")

    def test_nome_desconhecido_e_outro_assunto(self):
        ctx = self.base.buscar("Quem é o Barão Tormenta?", anteriores=["Quem é Ravena?"])
        self.assertNotIn("Ravena", [e.nome for e in ctx.entidades[:1]])          # não herda a entidade da pergunta anterior
        self.assertTrue(self.base.assunto_novo("Quem é o Barão Tormenta?"))
        self.assertFalse(self.base.assunto_novo("E o que Ravena procura?"))

    def test_limite_de_tamanho(self):
        ctx = self.base.buscar("Vale Alto", limite=300)
        self.assertLessEqual(len(ctx.texto()), 300 + 200)                       # cabeçalhos à parte
        self.assertTrue(ctx.entidades and ctx.entidades[0].nome == "Vale Alto")

    def test_pergunta_geral_traz_as_mais_vistas(self):
        ctx = self.base.buscar("quem são os personagens principais?")
        self.assertEqual(ctx.entidades[0].nome, "Aldric")
        self.assertTrue(ctx.trechos)

    def test_jogo_sem_leitura_e_base_vazia(self):
        self.assertTrue(chat.Base.de_dados({}, {}).vazia)


class IAFalsa:
    nome = "falsa"

    def __init__(self, *respostas):
        self.respostas, self.pedidos = list(respostas), []

    def perguntar(self, instrucoes, pedido, esquema):
        self.pedidos.append(pedido)
        r = self.respostas.pop(0)
        return {"resposta": r[0], "capturas": r[1]} if isinstance(r, tuple) else {"resposta": r}


class TestConversa(unittest.TestCase):
    def setUp(self):
        self.pasta = Path(tempfile.mkdtemp())
        self.base = chat.Base.de_dados(GRAFO, LEITURAS)

    def test_citacoes_so_das_capturas_enviadas(self):
        self.assertEqual(chat.citar("Ele é capitão [C1, C9] e manda [c2] .", {"C1": "a.jpg", "C2": "b.jpg"}),
                         ("Ele é capitão [C1] e manda [C2].", {"C1": "a.jpg", "C2": "b.jpg"}))

    def test_pergunta_resposta_guardada_e_continuacao(self):
        ia = IAFalsa("Aldric é o capitão da guarda [C1].", "Ele pede ervas do pântano [C2].")
        c = chat.Conversa(self.pasta, self.base)
        m = c.perguntar("Quem é Aldric?", ia)
        self.assertEqual((m.resposta, m.ia), ("Aldric é o capitão da guarda [C1].", "falsa"))
        self.assertEqual(m.fontes, {"C1": c.base.buscar("Quem é Aldric?").fontes["C1"]})
        self.assertIn("## Pergunta\nQuem é Aldric?", ia.pedidos[0])
        c.perguntar("e o que ele pede?", ia)
        self.assertIn("Usuário: Quem é Aldric?", ia.pedidos[1])                   # o histórico vai junto
        self.assertIn("Aldric (personagem", ia.pedidos[1])                        # e a entidade da pergunta anterior
        de_novo = chat.Conversa(self.pasta, self.base)                             # reaberta: a conversa continua lá
        self.assertEqual([x.pergunta for x in de_novo.mensagens], ["Quem é Aldric?", "e o que ele pede?"])
        de_novo.limpar()
        self.assertEqual(chat.Conversa(self.pasta, self.base).mensagens, [])

    def test_capturas_do_campo_proprio(self):
        m = chat.Conversa(self.pasta, self.base).perguntar("Quem é Aldric?", IAFalsa(("Aldric é o capitão.", ["C1", "C77", "[c2]"])))
        self.assertEqual(sorted(m.fontes), ["C1", "C2"])                           # a inventada (C77) não entra

    def test_resposta_vazia_vira_aviso(self):
        m = chat.Conversa(self.pasta, self.base).perguntar("Quem é Aldric?", IAFalsa(""))
        self.assertEqual(m.resposta, chat.SEM_RESPOSTA)


class TestDisponibilidade(unittest.TestCase):
    def jogo(self, lidas=1):
        from unittest import mock
        return mock.Mock(resumo=lambda: {"lida": lidas})

    def config(self, ia):
        from unittest import mock
        return mock.Mock(do_jogo=lambda jogo: mock.Mock(ia=ia))

    def test_motivos(self):
        from unittest import mock
        self.assertIn("só com OCR", chat.disponibilidade(self.jogo(), self.config(""))[1])
        self.assertIn("Iniciar leitura", chat.disponibilidade(self.jogo(0), self.config("ollama"))[1])
        with mock.patch.object(chat.visao, "_json", side_effect=OSError):
            self.assertIn("não está aberto", chat.disponibilidade(self.jogo(), self.config("ollama"))[1])
        with mock.patch.object(chat.visao, "_json", return_value={"models": [{"name": "outro:7b"}]}):
            self.assertIn("ollama pull qwen2.5:7b", chat.disponibilidade(self.jogo(), self.config("ollama"))[1])
        with mock.patch.object(chat.visao, "_json", return_value={"models": [{"name": "qwen2.5:7b"}]}):
            self.assertEqual(chat.disponibilidade(self.jogo(), self.config("ollama")), (True, "ollama:qwen2.5:7b"))
        with mock.patch("extracao.ia_publica.achar_claude", side_effect=chat.ErroConector("Claude Code não encontrado")):
            self.assertEqual(chat.disponibilidade(self.jogo(), self.config("claude-code")), (False, "Claude Code não encontrado"))

    def test_chat_usa_contexto_maior_no_ollama(self):
        b = chat.backend_do_chat("ollama")
        self.assertEqual((b.num_ctx, chat.limite_para(b)), (chat.CONTEXTO_OLLAMA, chat.LIMITE_OLLAMA))


@unittest.skipUnless(__import__("importlib").util.find_spec("PySide6"), "PySide6 não instalado")
class TestPainel(unittest.TestCase):
    def esperar(self, condicao, prazo=5.0):
        import time
        from PySide6.QtWidgets import QApplication
        fim = time.time() + prazo
        while not condicao() and time.time() < fim:
            QApplication.processEvents()
            time.sleep(0.01)
        self.assertTrue(condicao())

    def test_perguntar_citar_e_esperar_a_leitura(self):
        from unittest import mock
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
        from gamemind.ui.chat import PainelChat
        pasta = Path(tempfile.mkdtemp())
        jogo = mock.Mock(pasta=pasta)
        config = mock.Mock(do_jogo=lambda j: mock.Mock(ia="ollama"))
        ia = IAFalsa("Aldric é o capitão [C1].")
        p = PainelChat()
        citadas = []
        p.mostrar_captura.connect(citadas.append)
        with mock.patch.object(chat, "disponibilidade", return_value=(True, "falsa")), \
             mock.patch.object(chat.Base, "do_jogo", return_value=chat.Base.de_dados(GRAFO, LEITURAS)), \
             mock.patch.object(chat, "backend_do_chat", return_value=ia):
            p.abrir(jogo, config)
            self.esperar(lambda: p.estados.currentIndex() == 2)
            p.ocupado(True)                                                          # leitura em andamento: o chat espera
            self.assertFalse(p.pergunta.isEnabled())
            p.enviar("Quem é Aldric?")
            self.assertFalse(p.pensando)
            p.ocupado(False)
            p.enviar("Quem é Aldric?")
            self.assertTrue(p.pensando and not p.pergunta.isEnabled())
            self.esperar(lambda: not p.pensando)
        html = p.texto.toHtml()
        citada = p.conversa.mensagens[0].fontes["C1"]
        self.assertIn("Você:", html)
        self.assertIn(f"captura:{citada}", html)                                     # [C1] virou link para a captura
        from PySide6.QtCore import QUrl
        p._link(QUrl(f"captura:{citada}"))
        self.assertEqual(citadas, [citada])
        self.assertTrue((pasta / chat.ARQUIVO).exists())

    def test_indisponivel_mostra_o_motivo(self):
        from unittest import mock
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
        from gamemind.ui.chat import PainelChat
        p = PainelChat()
        with mock.patch.object(chat, "disponibilidade", return_value=(False, "O Ollama não está aberto.")):
            p.abrir(mock.Mock(pasta=Path(tempfile.mkdtemp())), mock.Mock())
            p.fechar()                                                               # fechou antes da resposta: ela é ignorada
            p.abrir(mock.Mock(pasta=Path(tempfile.mkdtemp())), mock.Mock())
            self.esperar(lambda: p.estados.currentIndex() == 1)
        self.assertEqual(p.motivo.text(), "O Ollama não está aberto.")


if __name__ == "__main__":
    unittest.main()
