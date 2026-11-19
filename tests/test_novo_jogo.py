"""Novo jogo: pastas conhecidas das ferramentas de captura, escolhas por jogo, apagar jogo e o assistente da janela."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path[:0] = [str(Path(__file__).resolve().parent.parent / "src")]
_tmp = tempfile.TemporaryDirectory()
os.environ["GAMEMIND_DADOS"] = _tmp.name   # nunca os dados nem a configuração do usuário
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from gamemind.nucleo import pastas_conhecidas as pc  # noqa: E402
from gamemind.nucleo import pipeline as pl  # noqa: E402
from gamemind.nucleo.config import Config  # noqa: E402
from gamemind.nucleo.repositorio import Jogo  # noqa: E402


def steam_falsa(raiz: Path, appid: str, nome: str) -> Path:
    capturas = raiz / "userdata" / "123" / "760" / "remote" / appid / "screenshots"
    capturas.mkdir(parents=True)
    (raiz / "steamapps").mkdir(exist_ok=True)
    (raiz / "steamapps" / f"appmanifest_{appid}.acf").write_text(f'"AppState"\n{{\n\t"appid"\t\t"{appid}"\n\t"name"\t\t"{nome}"\n}}\n',
                                                                 encoding="utf-8")
    return capturas


class TestPastasConhecidas(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(dir=_tmp.name))
        self.casa, self.steam = self.dir / "casa", self.dir / "Steam"

    def test_steam_com_o_nome_do_jogo_e_pastas_de_video(self):
        a = steam_falsa(self.steam, "111", "Reino das Brumas")
        steam_falsa(self.steam, "222", "Corrida Veloz")
        (self.casa / "Videos" / "Radeon ReLive").mkdir(parents=True)
        s = pc.sugestoes(self.casa, [self.steam])
        self.assertIn(("Steam · Reino das Brumas", a), s["screenshots"])
        self.assertEqual(s["videos"], [("AMD Adrenalin", self.casa / "Videos" / "Radeon ReLive")])
        self.assertEqual(pc.do_jogo("reino das brumas", self.casa, [self.steam]), a)   # pelo nome que a Steam guarda
        self.assertIsNone(pc.do_jogo("Outro Jogo Qualquer", self.casa, [self.steam]))

    def test_sem_nada_conhecido_abre_em_imagens_ou_videos_do_usuario(self):
        (self.casa / "Pictures").mkdir(parents=True)
        (self.casa / "Videos").mkdir()
        self.assertEqual(pc.inicio("screenshots", self.casa, []), self.casa / "Pictures")
        self.assertEqual(pc.inicio("videos", self.casa, []), self.casa / "Videos")
        self.assertEqual(pc.inicio("videos", self.dir / "vazia", []), self.dir / "vazia")


class TestJogosInstalados(unittest.TestCase):
    def test_launchers_e_o_exe_principal_sem_instaladores(self):
        from gamemind.nucleo import jogos_instalados as ji
        d = Path(tempfile.mkdtemp(dir=_tmp.name))
        steam_falsa(d / "Steam", "111", "Reino das Brumas")
        steam_falsa(d / "Steam", "333", "Steamworks Common Redistributables")   # não é jogo
        jogo = d / "Steam" / "steamapps" / "common" / "Reino"
        (jogo / "bin").mkdir(parents=True)
        (d / "Steam" / "steamapps" / "appmanifest_111.acf").write_text('"name"\t"Reino das Brumas"\n"installdir"\t"Reino"\n', encoding="utf-8")
        for nome, tamanho in (("unins000.exe", 900), ("ReinoDasBrumas.exe", 500), ("CrashReporter.exe", 800), ("ferramenta.exe", 100)):
            (jogo / "bin" / nome).write_bytes(b"x" * tamanho)
        epic, corrida = d / "Epic", d / "Jogos" / "Corrida"
        epic.mkdir()
        corrida.mkdir(parents=True)
        (corrida / "Corrida.exe").write_bytes(b"x")
        (epic / "a.item").write_text('{"DisplayName": "Corrida Veloz", "InstallLocation": "%s"}' % corrida.as_posix(), encoding="utf-8")
        jogos = ji.listar(raizes_steam=[d / "Steam"], pasta_epic=epic)
        self.assertEqual([(j.nome, j.origem) for j in jogos], [("Corrida Veloz", "Epic Games"), ("Reino das Brumas", "Steam")])
        self.assertEqual(jogos[1].executavel.name, "ReinoDasBrumas.exe")         # não o desinstalador nem o relatório de erro


class TestEscolhasDoJogo(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(dir=_tmp.name))
        self.jogo = Jogo(self.dir / "jogo")
        self.addCleanup(self.jogo.fechar)

    def test_escolhas_do_jogo_por_cima_da_configuracao_global(self):
        global_ = Config(ia="ollama", regioes_por_imagem=True, revisar_entidades=True)
        self.assertEqual(global_.do_jogo(self.jogo), global_)                     # jogo sem escolhas: vale a global
        self.jogo.set("ia", "")
        self.jogo.set("revisar_entidades", False)
        c = global_.do_jogo(self.jogo)
        self.assertEqual((c.ia, c.revisar_entidades, c.regioes_por_imagem), ("", False, True))

    def test_duas_pastas_lidas_e_reinicio_mantem_as_escolhas(self):
        fotos, videos = self.dir / "fotos", self.dir / "videos"
        fotos.mkdir()
        videos.mkdir()
        (fotos / "a.jpg").write_bytes(b"x")
        (videos / "b.mp4").write_bytes(b"y")
        self.jogo.set("pasta_capturas", str(fotos))
        self.jogo.set("pasta_videos", str(videos))
        self.jogo.set("ia", "")
        vazia = {"tipo": "imagem", "quadros": [{"t": 0.0, "secoes": {"tela": ""}, "dic": {}, "cands": [], "rels": []}]}
        with mock.patch.object(pl, "ler", side_effect=lambda *a, **k: (vazia, 0.0)):
            rel = pl.Pipeline(self.jogo, Config(ia="")).processar()
        self.assertEqual(rel.novas, 2)                                           # screenshots e vídeos
        self.jogo.reiniciar()
        self.assertEqual((self.jogo.get("pasta_videos"), self.jogo.get("ia")), (str(videos), ""))   # escolhas ficam
        self.assertEqual(self.jogo.midias(), [])


class TestApagarJogo(unittest.TestCase):
    def test_apaga_so_a_pasta_do_jogo(self):
        capturas = Path(tempfile.mkdtemp(dir=_tmp.name)) / "capturas"
        capturas.mkdir()
        (capturas / "a.jpg").write_bytes(b"x")
        jogo = Jogo.abrir("Jogo Para Apagar")
        jogo.set("pasta_capturas", str(capturas))
        (jogo.pasta_vault / "nota.md").parent.mkdir(parents=True, exist_ok=True)
        (jogo.pasta_vault / "nota.md").write_text("x", encoding="utf-8")
        pasta = jogo.pasta
        jogo.fechar()
        Jogo.apagar("Jogo Para Apagar")
        self.assertFalse(pasta.exists())
        self.assertNotIn("Jogo Para Apagar", Jogo.listar())
        self.assertTrue((capturas / "a.jpg").exists())                          # as capturas do usuário ficam
        with self.assertRaises(ValueError):                                      # só apaga o que é jogo do GameMind
            Jogo.apagar("Nao Existe")


@unittest.skipUnless(__import__("importlib").util.find_spec("PySide6"), "PySide6 não instalado")
class TestJanela(unittest.TestCase):
    def test_biblioteca_assistente_e_pagina_do_jogo(self):
        from PySide6.QtWidgets import QApplication, QDialog
        app = QApplication.instance() or QApplication([])
        from gamemind.ui.assistente import AssistenteJogo
        from gamemind.ui.janela import Janela
        pasta = Path(tempfile.mkdtemp(dir=_tmp.name))
        j = Janela()
        self.addCleanup(j.close)
        antes = len(Jogo.listar())
        self.assertEqual(len(j.biblioteca.cartoes), antes + 1)                   # um cartão por jogo e o de adicionar

        def responder(assistente):   # o usuário responde o questionário: nome, pasta, só OCR
            assistente.nome.setText("Jogo do Teste")
            assistente._avancar()
            assistente.pasta_capturas.setText(str(pasta))
            assistente._avancar()
            assistente.sem_ia.setChecked(True)
            assistente._avancar()
            self.assertEqual(assistente.proximo.text(), "Concluir")              # sem IA: as perguntas da IA são puladas
            assistente._avancar()
            return QDialog.Accepted
        with mock.patch.object(AssistenteJogo, "exec", responder):
            j._novo_jogo()
        app.processEvents()
        self.assertEqual(j.telas.currentIndex(), 1)                              # foi para a página do jogo
        self.assertEqual((j.jogo.nome, j.jogo.get("pasta_capturas"), j.jogo.get("ia")), ("Jogo do Teste", str(pasta), ""))
        self.assertIn("só com OCR", j.resumo_jogo.text())
        j._ocupado(True)                                                         # durante a leitura nada que mexa no jogo
        self.assertFalse(any(a.isEnabled() for a in j.acoes_jogo + j.acoes_app) or j.botao_mais.isEnabled())
        j._ocupado(False)
        j._mostrar_biblioteca()
        self.assertEqual(len(j.biblioteca.cartoes), antes + 2)

        # apagar pelo "⋯" do cartão: o menu tem a opção, e confirmar apaga o jogo
        from PySide6.QtWidgets import QMessageBox
        cartao = next(c for c in j.biblioteca.cartoes if c.nome.text() == "Jogo do Teste")
        apagar = next(a for a in cartao.menu.actions() if a.text() == "Apagar jogo...")
        with mock.patch.object(QMessageBox, "exec", lambda self: 0), \
             mock.patch.object(QMessageBox, "clickedButton", lambda self: next(b for b in self.buttons() if b.text() == "Apagar jogo")):
            apagar.trigger()
        app.processEvents()
        self.assertNotIn("Jogo do Teste", Jogo.listar())
        self.assertEqual(len(j.biblioteca.cartoes), antes + 1)
        self.assertTrue(pasta.is_dir())                                          # a pasta de capturas fica

    def test_assistente_so_oferece_ollama_e_claude_com_login(self):
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
        from gamemind.ui import assistente as a
        with mock.patch.object(a, "achar_claude", return_value="claude"):
            w = a.AssistenteJogo(None, ia_padrao="gemini")                      # IA retirada numa configuração antiga
            self.assertEqual(set(w.opcoes_ia), {"ollama", "claude-code"})
            self.assertTrue(w.opcoes_ia["ollama"].isChecked())
            self.assertTrue(w.entrar.isHidden())                                 # o login só aparece para o Claude
            w.opcoes_ia["claude-code"].setChecked(True)
            self.assertFalse(w.entrar.isHidden())
            self.assertTrue(w.entrar.isEnabled())
        r = w.resultado()
        self.assertEqual(r["ia"], "claude-code")
        self.assertNotIn("chave", r)
        w.deleteLater()

    def test_menus_ajuda_e_sobre(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        from gamemind.ui.ajuda import JanelaAjuda, JanelaSobre
        from gamemind.ui.janela import Janela
        j = Janela()
        self.addCleanup(j.close)
        self.assertEqual([a.text() for a in j.menuBar().actions()], ["Jogo", "Aplicativo", "Ajuda", "Sobre"])
        j._ajuda("ollama")
        texto = j._janela_ajuda.texto.toHtml()
        self.assertIn("https://ollama.com/download", texto)
        self.assertIn("ollama pull qwen2.5:7b", texto)
        chamou = []
        a = JanelaAjuda(None, "ollama", acoes={"verificar": lambda: chamou.append(1)})
        a._link(QUrl("copiar:ollama%20pull%20qwen2.5%3A7b"))                     # o link "copiar" ao lado do comando
        self.assertEqual(app.clipboard().text(), "ollama pull qwen2.5:7b")
        a._link(QUrl("acao:verificar"))
        self.assertEqual(chamou, [1])
        JanelaSobre(None, "C:/dados").deleteLater()
        a.deleteLater()

    def test_espera_mostra_os_passos_e_devolve_o_resultado(self):
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
        from gamemind.ui.espera import Espera
        vistos = []

        def trabalho(x, avisar):
            avisar(1)
            vistos.append(x)
            return x * 2
        e = Espera(None, "Teste", ["um", "dois"])
        self.assertEqual(e.executar(trabalho, 21, avisar=True), (True, 42))
        self.assertEqual((vistos, e.atual), ([21], 2))
        ok, erro = Espera(None, "Teste", ["um"]).executar(lambda: 1 / 0)
        self.assertFalse(ok)
        self.assertIn("ZeroDivisionError", erro)

    def test_tema_fica_no_menu(self):
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        from gamemind.ui import aparencia, temas
        from gamemind.ui.janela import Janela
        j = Janela()
        self.addCleanup(j.close)
        from PySide6.QtCore import Qt
        self.assertIs(j.menuBar().cornerWidget(Qt.TopLeftCorner), j.logo)         # o logo à esquerda do menu
        self.assertFalse(j.logo.pixmap().isNull())
        menu = next(m for m in j.findChildren(aparencia.MenuTemas))
        acoes = {a.data(): a for a in menu.actions()}
        self.assertEqual(list(acoes), list(temas.TEMAS))
        menu.hovered.emit(acoes["terminal"])                                     # passar o mouse mostra o tema
        self.assertIs(aparencia.ATUAL, temas.TEMAS["terminal"])
        menu.aboutToHide.emit()                                                  # fechou sem escolher: volta
        app.processEvents()
        self.assertIs(aparencia.ATUAL, temas.TEMAS[j.config.tema])


if __name__ == "__main__":
    unittest.main()
