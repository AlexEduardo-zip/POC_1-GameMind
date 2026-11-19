"""Temas da janela: só atributos visuais mudam; o resto (folha, componentes, lógica) é o mesmo para todos."""
import os
import re
import sys
import tempfile
import unittest
from dataclasses import fields
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parent.parent / "src")]
os.environ.setdefault("GAMEMIND_DADOS", tempfile.mkdtemp())   # nunca a configuração do usuário
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from gamemind.ui import temas  # noqa: E402


class TestTemas(unittest.TestCase):
    def test_todo_tema_tem_todos_os_atributos_e_o_padrao_existe(self):
        self.assertIn(temas.PADRAO, temas.TEMAS)
        for t in temas.TEMAS.values():
            for f in fields(t):
                self.assertNotIn(getattr(t, f.name), ("", None), f"{t.nome}.{f.name}")
        self.assertIs(temas.tema("inexistente"), temas.TEMAS[temas.PADRAO])

    def test_a_folha_e_a_mesma_so_os_valores_mudam(self):
        def esqueleto(folha):   # tira cores e números: sobra a estrutura
            return re.sub(r"#[0-9A-Fa-f]{6}|rgba\([^)]*\)|\d+(\.\d+)?", "_", folha)
        esqueletos = {esqueleto(temas.folha(t)) for t in temas.TEMAS.values()}
        self.assertEqual(len(esqueletos), 1)

    def test_contraste_legivel_em_todos_os_temas(self):
        for t in temas.TEMAS.values():
            v, p = temas.valores(t), temas.painel_visto(t)
            casos = {"texto/painel": (t.texto, p, 4.5), "texto/campo": (t.texto, v["campo"], 4.5),
                     "apagado/painel": (v["apagado"], p, 4.5), "sobre o destaque": (v["sobre_destaque"], t.destaque, 4.5),
                     "destaque/painel": (t.destaque, p, 3.0)}   # destaque: aba ativa e cabeçalhos em negrito
            for caso, (a, b, minimo) in casos.items():
                self.assertGreaterEqual(temas.contraste(a, b), minimo, f"{t.nome}: {caso}")


@unittest.skipUnless(__import__("importlib").util.find_spec("PySide6"), "PySide6 não instalado")
class TestJanelaComTemas(unittest.TestCase):
    def test_trocar_tema_so_muda_a_aparencia_e_a_escolha_fica_salva(self):
        from PySide6.QtWidgets import QApplication, QWidget
        app = QApplication.instance() or QApplication([])
        from gamemind.nucleo.config import Config
        from gamemind.ui.janela import Janela
        j = Janela()
        self.addCleanup(j.close)
        arvores = set()
        for chave in temas.TEMAS:
            j._mudar_tema(chave, False)                                     # pré-visualização: não grava
            app.processEvents()
            self.assertEqual(app.styleSheet(), temas.folha(temas.TEMAS[chave]))
            arvores.add(tuple(sorted((type(c).__name__, c.objectName()) for c in j.findChildren(QWidget))))
        self.assertEqual(len(arvores), 1)                                    # mesmos componentes em todos os temas
        self.assertEqual(Config.carregar().tema, temas.PADRAO)
        j._mudar_tema("terminal", True)
        self.assertEqual(Config.carregar().tema, "terminal")                # escolhido: vale na próxima vez
        c = Config.carregar()
        c.tema = temas.PADRAO
        c.salvar()


if __name__ == "__main__":
    unittest.main()
