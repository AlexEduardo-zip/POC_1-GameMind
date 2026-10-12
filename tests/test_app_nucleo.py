"""Testes offline do núcleo do aplicativo (sem OCR, Tesseract nem Qt): repositório, consolidação, vault e observador.
As leituras são sintéticas, no formato de src/gamemind/nucleo/leitura.py.
Uso: python -m unittest discover -s tests -v"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
_tmp = tempfile.TemporaryDirectory()
os.environ["GAMEMIND_DADOS"] = _tmp.name  # nunca toca nos dados reais do usuário

from gamemind.nucleo import pipeline as pl  # noqa: E402
from gamemind.nucleo.config import Config  # noqa: E402
from gamemind.nucleo.consolidacao import consolidar_base, entrada_llm, somar_llm  # noqa: E402
from gamemind.nucleo import obsidian, regioes as reg  # noqa: E402
from gamemind.nucleo.dicionario import aprender, para_gazetteer  # noqa: E402
from gamemind.nucleo.leitura import VERSAO_LEITURA  # noqa: E402
from gamemind.nucleo.observador import Observador  # noqa: E402
from gamemind.nucleo.repositorio import Jogo  # noqa: E402


def quadro(texto="", dic=None, cands=(), rels=()):
    return {"secoes": {"tela": texto}, "dic": dic or {}, "cands": list(cands), "rels": list(rels)}


def missao(nome, fonte="hud"):
    return {"nome": nome, "tipo": "missao", "fonte": fonte, "estado": "", "subtipo": "", "evidencia": nome}


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(dir=_tmp.name))
        self.capturas = self.dir / "capturas"
        self.capturas.mkdir()
        self.jogo = Jogo(self.dir / "jogo")
        self.addCleanup(self.jogo.fechar)
        # dicionário que o usuário não precisa criar; os testes de consolidação o usam como se já tivesse sido aprendido
        self.nomes = {"Aldric": {"tipo": "personagem", "aliases": []}, "Brisalda": {"tipo": "personagem", "aliases": ["Brisa"]}}
        (self.jogo.pasta / "dicionario_manual.json").write_text(json.dumps(self.nomes), encoding="utf-8")

    def midia(self, nome, conteudo=b"x"):
        p = self.capturas / nome
        p.write_bytes(conteudo)
        return p

    def lida(self, nome, leitura):
        self.jogo.registrar(self.midia(nome), "imagem" if nome.endswith(".jpg") else "clipe")
        m = next(m for m in self.jogo.midias() if m.nome == nome)
        self.jogo.gravar_leitura(m.id, leitura, VERSAO_LEITURA, 1.0)
        return m


class TestRepositorio(Base):
    def test_registro_e_releitura(self):
        p = self.midia("a.jpg")
        self.assertTrue(self.jogo.registrar(p, "imagem"))
        self.assertFalse(self.jogo.registrar(p, "imagem"))   # igual: não registra de novo
        m = self.jogo.midias()[0]
        self.jogo.gravar_leitura(m.id, {"tipo": "imagem", "quadros": []}, VERSAO_LEITURA, 2.0)
        self.jogo.gravar_llm(m.id, "ollama:x", {"entidades": []}, {})
        p.write_bytes(b"outro conteudo")                       # arquivo mudou: volta a pendente e perde a resposta do LLM
        self.assertTrue(self.jogo.registrar(p, "imagem"))
        self.assertEqual(self.jogo.midias()[0].estado, "pendente")
        self.assertIsNone(self.jogo.llm(m.id, "ollama:x"))

    def test_versao_antiga_e_erro_voltam_a_pendente(self):
        m = self.lida("a.jpg", {"tipo": "imagem", "quadros": []})
        self.jogo.registrar(self.midia("b.jpg"), "imagem")
        b = next(x for x in self.jogo.midias() if x.nome == "b.jpg")
        self.jogo.gravar_erro(b.id, "falhou")
        self.assertEqual(self.jogo.marcar_para_reler(VERSAO_LEITURA), 1)
        self.assertEqual(self.jogo.marcar_para_reler(VERSAO_LEITURA + 1), 2)
        self.assertEqual({x.estado for x in self.jogo.midias()}, {"pendente"})
        del m

    def test_meta(self):
        self.assertEqual(self.jogo.pasta_vault, self.jogo.pasta / "vault")   # o vault fica sempre dentro da pasta do jogo


class TestConsolidacao(Base):
    def setUp(self):
        super().setUp()
        self.gaz = para_gazetteer(self.nomes)

    def test_base_sao_os_nomes_do_dicionario_que_aparecem_no_texto(self):
        a = self.lida("a.jpg", {"tipo": "imagem", "quadros": [quadro("Aldric fala com um estranho")]})
        b = self.lida("b.jpg", {"tipo": "imagem", "quadros": [quadro("nada de nome aqui")]})
        base = consolidar_base(self.jogo.leituras(), self.gaz)
        self.assertEqual([(e["nome"], e["tipo"]) for e in base[a.id]["entidades"]], [("Aldric", "personagem")])
        self.assertEqual(base[b.id]["entidades"], [])

    def test_clipe_conta_em_quantos_quadros_o_nome_aparece(self):
        c = self.lida("c.mp4", {"tipo": "clipe", "quadros": [quadro("Aldric"), quadro("Aldric e Brisa"), quadro("")]})
        an = consolidar_base(self.jogo.leituras(), self.gaz)[c.id]
        self.assertEqual({e["nome"]: e["evidencia"] for e in an["entidades"]},
                         {"Aldric": "OCR em 2 quadro(s)", "Brisalda": "OCR em 1 quadro(s)"})

    def test_llm_soma_so_o_que_tem_lastro(self):
        texto = "Fale com Aldric na estalagem de Vale Alto"
        a = self.lida("a.jpg", {"tipo": "imagem", "quadros": [quadro(texto)]})
        leituras = self.jogo.leituras()
        base = consolidar_base(leituras, self.gaz)
        secoes, detectado = entrada_llm(leituras[0][1], base[a.id])
        self.assertEqual(detectado, ["personagem: Aldric"])
        resp = {a.id: {"entidades": [{"nome": "Brisa", "tipo": "personagem"}, {"nome": "Aldric", "tipo": "personagem"}], "relacoes": []}}
        final = somar_llm(base, leituras, resp, self.gaz)
        self.assertEqual([e["nome"] for e in final[a.id]["entidades"]], ["Aldric"])   # Brisa não está no texto: descartada
        self.assertEqual(len(base[a.id]["entidades"]), 1)                              # a base não é alterada


class TestPipelineSemOCR(Base):
    def test_grafo_e_vault_preservam_notas_do_usuario(self):
        self.jogo.set("pasta_capturas", str(self.capturas))
        self.lida("a.jpg", {"tipo": "imagem", "quadros": [quadro("Aldric e Brisa")]})
        pipe = pl.Pipeline(self.jogo, Config(ia=""))
        rel = pipe.processar()
        self.assertEqual((rel.nos, rel.notas), (2, 2))
        vault = self.jogo.pasta_vault
        self.assertTrue((vault / "Personagens" / "Aldric.md").exists())
        (vault / "minhas notas.md").write_text("minha", encoding="utf-8")
        # a captura com Brisa some da partida: a nota gerada dela sai, a do usuário fica
        m = self.jogo.midias()[0]
        self.jogo.gravar_leitura(m.id, {"tipo": "imagem", "quadros": [quadro("Aldric")]}, VERSAO_LEITURA, 1)
        with mock.patch.object(pl.Jogo, "registrar", return_value=False):
            rel = pipe.processar()
        self.assertEqual(rel.nos, 1)
        self.assertFalse((vault / "Personagens" / "Brisalda.md").exists())
        self.assertTrue((vault / "minhas notas.md").exists())
        g = json.loads(self.jogo.caminho_grafo.read_text(encoding="utf-8"))
        self.assertEqual([n["nome"] for n in g["nos"]], ["Aldric"])

    def test_progresso_informa_arquivo_lido_e_notas_criadas(self):
        self.jogo.set("pasta_capturas", str(self.capturas))
        self.midia("quebrada.jpg", b"nao e imagem")
        self.lida("a.jpg", {"tipo": "imagem", "quadros": [quadro("Aldric")]})
        eventos = []
        pl.Pipeline(self.jogo, Config(ia=""), eventos.append).processar()
        lendo = [Path(e.arquivo).name for e in eventos if e.etapa == "leitura" and e.arquivo]
        self.assertEqual(lendo, ["quebrada.jpg"])   # só a pendente é lida; o evento traz o caminho para a prévia
        criadas = {Path(e.arquivo).name for e in eventos if e.etapa == "vault"}
        self.assertIn("Aldric.md", criadas)
        self.assertIn("Quadro da partida.canvas", criadas)

    def test_erro_de_leitura_nao_para_a_rodada(self):
        self.jogo.set("pasta_capturas", str(self.capturas))
        self.midia("quebrada.jpg", b"nao e imagem")
        rel = pl.Pipeline(self.jogo, Config(ia="")).processar()
        self.assertEqual((rel.novas, rel.erros), (1, 1))
        self.assertEqual(self.jogo.midias()[0].estado, "erro")

    def test_ia_sem_chave_gera_grafo_sem_llm(self):
        self.jogo.set("pasta_capturas", str(self.capturas))
        self.lida("a.jpg", {"tipo": "imagem", "quadros": [quadro("Aldric")]})
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "", "GOOGLE_API_KEY": ""}), mock.patch("extracao.ia_publica.carregar_env"):
            rel = pl.Pipeline(self.jogo, Config(ia="gemini")).processar()
        self.assertIn("GEMINI_API_KEY", rel.erro_llm)
        self.assertEqual(rel.nos, 1)


class TestCanvas(Base):
    # Planalto Norte > Vale Alto; Aldric fica em Vale Alto; Brisa só divide uma tela curta com Vale Alto; Dario e Tomas só dividem
    # uma tela longa (lista) com Planalto Norte; Torre Velha não tem nada; Ordem do Corvo tem um membro sem lugar (Marek)
    GRAFO = {"nos": [
        {"nome": "Planalto Norte", "tipo": "local", "fontes": [{"arquivo": "a.png"}, {"arquivo": "d.png"}]},
        {"nome": "Vale Alto", "tipo": "local", "fontes": [{"arquivo": "a.png"}, {"arquivo": "b.png"}]},
        {"nome": "Aldric", "tipo": "personagem", "fontes": [{"arquivo": "a.png"}]},
        {"nome": "Brisa", "tipo": "personagem", "fontes": [{"arquivo": "b.png"}]},
        {"nome": "Dario", "tipo": "personagem", "fontes": [{"arquivo": "lista.png"}]},
        {"nome": "Tomas", "tipo": "personagem", "fontes": [{"arquivo": "lista.png"}]},
        {"nome": "Torre Velha", "tipo": "local", "fontes": [{"arquivo": "lista.png"}]},
        {"nome": "Ordem do Corvo", "tipo": "faccao", "fontes": [{"arquivo": "e.png"}]},
        {"nome": "Marek", "tipo": "personagem", "fontes": [{"arquivo": "e.png"}]},
        {"nome": "A Colheita Perdida", "tipo": "missao", "fontes": [{"arquivo": "a.png"}]}],
        "arestas": [{"sujeito": "Vale Alto", "predicado": "parte_de", "objeto": "Planalto Norte"},
                    {"sujeito": "Aldric", "predicado": "localizado_em", "objeto": "Vale Alto"},
                    {"sujeito": "Marek", "predicado": "membro_de", "objeto": "Ordem do Corvo"},
                    {"sujeito": "Aldric", "predicado": "participa_de", "objeto": "A Colheita Perdida"}]}

    def gerar(self):
        from PIL import Image
        from exportar_vault import exportar
        from gamemind.nucleo import canvas
        midias = {}
        for nome in ("a.png", "b.png", "d.png", "e.png", "lista.png"):
            Image.new("RGB", (1920, 1080), "gray").save(self.capturas / nome)
            midias[nome] = (self.capturas / nome, "imagem", None)
        g = json.loads(json.dumps(self.GRAFO))
        g["nos"].append({"nome": "Recorrente", "tipo": "personagem", "fontes": [{"arquivo": "b.png"}] + [{"arquivo": f"x{i}.png"} for i in range(9)]})
        for i in range(5):   # com estes, lista.png passa de 6 entidades: é tela de lista e não conta como "vistos juntos"
            g["nos"].append({"nome": f"Extra {i}", "tipo": "item", "fontes": [{"arquivo": "lista.png"}]})
        self.g = g
        vault = self.dir / "vault"
        anexos, geradas = canvas.gerar(g, vault, midias)
        exportar(g, vault, anexos)
        return vault, geradas

    @staticmethod
    def sobrepoe(a, b):
        return a["x"] < b["x"] + b["width"] and b["x"] < a["x"] + a["width"] and a["y"] < b["y"] + b["height"] and b["y"] < a["y"] + a["height"]

    def verificar(self, vault, caminho):
        c = json.loads((vault / caminho).read_text(encoding="utf-8"))
        ids = {n["id"] for n in c["nodes"]}
        self.assertEqual(len(ids), len(c["nodes"]))
        for n in c["nodes"]:
            if n["type"] == "file":
                self.assertTrue((vault / n["file"]).exists(), n["file"])
        for e in c["edges"]:
            self.assertIn(e["fromNode"], ids)
            self.assertIn(e["toNode"], ids)
        soltos = [n for n in c["nodes"] if n["type"] != "group"]
        for i, a in enumerate(soltos):
            for b in soltos[i + 1:]:
                self.assertFalse(self.sobrepoe(a, b), (a.get("file") or a.get("text"), b.get("file") or b.get("text")))
        return c

    def test_mundo_da_partida_por_lugar_com_missoes_por_ultimo(self):
        vault, geradas = self.gerar()
        c = self.verificar(vault, "Quadro da partida.canvas")
        cartoes = [n["file"] for n in c["nodes"] if n["type"] == "file" and n["file"].endswith(".md")]
        self.assertEqual(len(cartoes), len(set(cartoes)))                       # cada entidade uma vez só
        self.assertEqual(len(cartoes), len(self.g["nos"]))
        grupos = [g["label"] for g in c["nodes"] if g["type"] == "group"]
        self.assertEqual(grupos[0], "Planalto Norte")                                    # coluna por lugar; Vale Alto está dentro de Planalto Norte
        self.assertNotIn("Vale Alto", grupos)
        self.assertTrue(grupos[-1].startswith("Missões"))                       # missões por último
        self.assertNotIn("A Colheita Perdida", grupos)                            # missão não é coluna
        self.assertIn("Ordem do Corvo", grupos)                                 # facção com membro sem lugar ganha coluna
        por_id = {n["id"]: n for n in c["nodes"]}

        def coluna(arquivo):
            n = next(n for n in c["nodes"] if n.get("file") == arquivo)
            g = next(g for g in c["nodes"] if g["type"] == "group" and g["x"] <= n["x"] and n["x"] + n["width"] <= g["x"] + g["width"]
                     and g["y"] <= n["y"] and n["y"] + n["height"] <= g["y"] + g["height"])
            return g["label"]
        self.assertEqual(coluna("Locais/Vale Alto.md"), "Planalto Norte")
        self.assertEqual(coluna("Personagens/Aldric.md"), "Planalto Norte")             # localizado_em Vale Alto, que é parte de Planalto Norte
        self.assertEqual(coluna("Personagens/Brisa.md"), "Planalto Norte")                # tela curta com Vale Alto: vista junto
        self.assertEqual(coluna("Personagens/Dario.md"), "Personagens")         # tela de lista não conta como "junto"
        self.assertEqual(coluna("Personagens/Marek.md"), "Ordem do Corvo")
        self.assertEqual(coluna("Personagens/Recorrente.md"), "Personagens")    # em mais de 8 capturas: está em toda parte, não é situado por proximidade
        self.assertEqual(coluna("Locais/Torre Velha.md"), "Outros lugares")
        self.assertEqual(coluna("Missoes/A Colheita Perdida.md"), "Missões (referência: o jogo já mostra)")
        arestas = {(por_id[e["fromNode"]].get("file"), por_id[e["toNode"]].get("file")) for e in c["edges"]}
        self.assertNotIn(("Personagens/Aldric.md", "Missoes/A Colheita Perdida.md"), arestas)   # nenhuma seta para missão
        self.assertIn(("Locais/Vale Alto.md", "Locais/Planalto Norte.md"), arestas)
        self.assertIn(("Personagens/Marek.md", "Faccoes/Ordem do Corvo.md"), arestas)
        ciri = next(n["id"] for n in c["nodes"] if n.get("file") == "Personagens/Brisa.md")
        self.assertFalse(any(ciri in (e["fromNode"], e["toNode"]) for e in c["edges"]))   # vista junto não vira seta
        self.assertIn("_midia/a.jpg", geradas)

    def test_canvas_de_entidade_e_link_na_nota(self):
        vault, geradas = self.gerar()
        self.assertIn("_canvas/Personagens/Aldric.canvas", geradas)
        self.assertNotIn("_canvas/Missoes/A Colheita Perdida.canvas", geradas)    # missão não tem canvas
        self.assertFalse(any("Extra" in g for g in geradas))                    # item não tem canvas
        self.assertNotIn("_canvas/Personagens/Dario.canvas", geradas)           # nada além da própria nota: sem canvas
        c = self.verificar(vault, "_canvas/Locais/Vale Alto.canvas")
        arquivos = [n["file"] for n in c["nodes"] if n["type"] == "file"]
        self.assertIn("Personagens/Aldric.md", arquivos)                       # relação lida
        self.assertIn("Personagens/Brisa.md", arquivos)                          # vista junto, no grupo próprio
        self.assertTrue(any(n["type"] == "group" and "mesmas telas" in n["label"] for n in c["nodes"]))
        v = self.verificar(vault, "_canvas/Personagens/Aldric.canvas")
        textos = [n["text"] for n in v["nodes"] if n["type"] == "text"]
        self.assertTrue(any("Missões (referência)" in t and "A Colheita Perdida" in t for t in textos))   # missão vira linha de texto
        self.assertFalse(any(n.get("file", "").startswith("Missoes/") for n in v["nodes"]))
        nota = (vault / "Personagens" / "Aldric.md").read_text(encoding="utf-8")
        self.assertIn("[[_canvas/Personagens/Aldric.canvas|canvas de Aldric]]", nota)


class TestObservador(Base):
    def test_so_entrega_arquivo_com_tamanho_estavel(self):
        obs = Observador(self.capturas, intervalo_s=0.01)
        p = self.midia("clipe.mp4", b"12")
        self.assertEqual(obs.consultar(), [])            # visto pela primeira vez: espera estabilizar
        p.write_bytes(b"1234")
        self.assertEqual(obs.consultar(), [])            # ainda crescendo
        self.assertEqual(obs.consultar(), [p.resolve()])  # estável: pronto
        self.assertEqual(obs.consultar(), [])            # já entregue
        self.midia("notas.txt")
        self.assertEqual(obs.consultar(), [])            # extensão que não é mídia


if __name__ == "__main__":
    unittest.main()


class TestDicionarioAprendido(unittest.TestCase):
    """O dicionário de nomes sai do texto lido, sem lista escrita à mão."""

    @staticmethod
    def midia(*linhas):
        return [{"secoes": {"tela": "", "legenda": chr(10).join(linhas), "hud": "", "aviso": ""}}]

    def test_falante_de_legenda_e_personagem(self):
        d = aprender([self.midia("Iolanda: Venha comigo ao celeiro."), self.midia("Iolanda: Cuidado com o lobo.")])
        self.assertEqual(d["Iolanda"]["tipo"], "personagem")

    def test_palavra_comum_no_comeco_da_frase_nao_e_nome(self):
        d = aprender([self.midia("Seguindo o caminho, ela parou.", "A estrada segue em frente."), self.midia("Ela foi seguindo adiante.")])
        self.assertNotIn("Seguindo", d)

    def test_nome_so_vale_com_indicio_de_tipo(self):
        # aparece em duas mídias, mas nada diz o que é: não entra (um tipo chutado sujaria o grafo)
        d = aprender([self.midia("Viu Zorgan ontem."), self.midia("Zorgan sumiu.")])
        self.assertNotIn("Zorgan", d)

    def test_lugar_pelo_contexto_e_apelido_pelo_prefixo(self):
        d = aprender([self.midia("Fomos para Brumavale cedo.", "Ravena de Altamira: Olá."), self.midia("Voltamos para Brumavale.", "Ravena: Oi."),
                      self.midia("Ravena de Altamira: Adeus.")])
        self.assertEqual(d["Brumavale"]["tipo"], "local")
        nome = next(n for n in d if "Ravena" in n)
        self.assertEqual(d[nome]["tipo"], "personagem")
        self.assertEqual(len(d[nome]["aliases"]), 1)   # "Ravena" e "Ravena de Altamira" são o mesmo personagem


class IAFalsa:
    """Responde à pergunta de papéis como uma IA que acerta: fala embaixo é legenda, canto de cima à direita é objetivo."""
    nome = "falsa"

    def perguntar(self, instrucoes, pedido, esquema):
        linhas = []
        for l in pedido.splitlines():
            i = int(l.split(".")[0])
            y = float(l.split("y=")[1].split()[0])
            x = float(l.split("x=")[1].split("-")[0])
            linhas.append({"id": i, "papel": "legenda" if y > 0.75 else "objetivo" if x > 0.7 and y < 0.3 else "menu"})
        return {"linhas": linhas + [{"id": 999, "papel": "legenda"}, {"id": 0, "papel": "inventado"}]}   # ids e papéis inválidos são ignorados


def linha(x0, y0, x1=None, texto="Uma linha de texto qualquer"):
    return {"texto": texto, "x0": x0, "y0": y0, "x1": x1 if x1 is not None else x0 + 0.3, "y1": y0 + 0.03, "altura": 0.03}


class TestRegioes(unittest.TestCase):
    def setUp(self):
        self.pasta = Path(tempfile.mkdtemp(dir=_tmp.name))

    def test_jogo_novo_comeca_com_padroes_genericos_e_grava_o_arquivo(self):
        r = reg.carregar(self.pasta)
        self.assertEqual(r.caixas, reg.PADRAO)
        self.assertEqual(set(r.origem.values()), {"padrao"})
        self.assertTrue(reg.caminho(self.pasta).exists())
        self.assertFalse(r.aprendida)

    def test_arquivo_com_defeito_volta_aos_padroes(self):
        reg.caminho(self.pasta).write_text("{ isto nao e json", encoding="utf-8")
        self.assertEqual(reg.carregar(self.pasta).caixas, reg.PADRAO)

    def test_ia_define_a_regiao_pela_posicao_das_linhas_e_o_arquivo_guarda(self):
        amostras = [[linha(0.2, 0.80, 0.8), linha(0.25, 0.83, 0.75), linha(0.1, 0.1, 0.4), linha(0.80, 0.10, 0.98)] for _ in range(3)]
        r = reg.aprender(amostras, IAFalsa(), reg.Regioes(), ["a", "b", "c"])
        x0, y0, x1, y1 = r.caixas["legenda"]
        self.assertTrue(0.15 <= x0 <= 0.22 and 0.75 <= y0 <= 0.8 and 0.78 <= x1 <= 0.86 and 0.84 <= y1 <= 0.9, r.caixas["legenda"])
        self.assertEqual(r.origem["legenda"], "ia")
        self.assertEqual(r.origem["aviso"], "padrao")   # a IA não achou aviso: fica o padrão
        self.assertTrue(r.aprendida)
        reg.salvar(self.pasta, r)
        r2 = reg.carregar(self.pasta)
        self.assertEqual(r2.caixas["legenda"], tuple(round(v, 3) for v in r.caixas["legenda"]))
        self.assertTrue(r2.aprendida)

    def test_linha_com_papel_errado_longe_das_outras_nao_estica_a_regiao(self):
        # a IA rotulou duas linhas do HUD (canto de cima) como legenda; a região continua só na faixa de baixo
        certas = [(linha(0.2, 0.80, 0.8), "legenda"), (linha(0.25, 0.83, 0.75), "legenda"), (linha(0.3, 0.86, 0.7), "legenda")]
        erradas = [(linha(0.85, 0.27, 0.95), "legenda"), (linha(0.86, 0.31, 0.97), "legenda")]
        caixa = reg.caixa_dos_papeis([certas + erradas, certas + erradas])["legenda"]["caixa"]
        self.assertTrue(caixa[1] > 0.7 and caixa[0] < 0.3, caixa)

    def test_ia_que_rotula_tudo_como_legenda_nao_leva_a_regiao_para_longe_do_padrao(self):
        # frases de um menu, no meio da tela, rotuladas como legenda: ficam fora (longe do padrão), a região não se mexe
        menu = [(linha(0.1, 0.25 + 0.05 * k, 0.9), "legenda") for k in range(8)]
        self.assertEqual(reg.caixa_dos_papeis([menu, menu, menu]), {})

    def test_regiao_manual_nunca_e_refeita(self):
        atual = reg.Regioes()
        atual.caixas["legenda"] = (0.0, 0.5, 1.0, 0.6)
        atual.meta = {"regioes": {"legenda": {"origem": "manual"}}}
        amostras = [[linha(0.2, 0.80, 0.8), linha(0.25, 0.83, 0.75)] for _ in range(3)]
        r = reg.aprender(amostras, IAFalsa(), atual)
        self.assertEqual(r.caixas["legenda"], (0.0, 0.5, 1.0, 0.6))
        self.assertEqual(r.origem["legenda"], "manual")

    def test_poucas_linhas_ou_caixa_absurda_nao_viram_regiao(self):
        self.assertEqual(reg.caixa_dos_papeis([[(linha(0.2, 0.8), "legenda")], [(linha(0.2, 0.8), "legenda")]]), {})   # 2 linhas só
        espalhadas = [[(linha(0.0, 0.0, 1.0), "legenda"), (linha(0.0, 0.95, 1.0), "legenda"), (linha(0.0, 0.5, 1.0), "legenda")]] * 2
        self.assertNotIn("legenda", reg.caixa_dos_papeis(espalhadas))   # ocuparia a tela toda

    def test_escolha_de_amostras_espalha_e_prefere_imagens(self):
        class M:
            def __init__(self, i, tipo="imagem"):
                self.i, self.tipo = i, tipo
        ms = [M(i) for i in range(30)] + [M(99, "clipe")]
        escolhidas = reg.escolher_amostras(ms, 4)
        self.assertEqual([m.i for m in escolhidas], [0, 10, 19, 29])


class TestObsidian(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(dir=_tmp.name))
        self.config = self.dir / "obsidian"
        self.vault = self.dir / "jogos" / "Meu jogo" / "vault"
        patcher = mock.patch.object(obsidian, "obsidian_aberto", return_value=False)
        self.aberto = patcher.start()
        self.addCleanup(patcher.stop)

    def test_vault_novo_e_registrado_no_obsidian_json_e_o_resto_do_arquivo_fica(self):
        self.config.mkdir()
        (self.config / "obsidian.json").write_text(json.dumps({"vaults": {"abc": {"path": str(self.dir / "outro"), "ts": 1}}, "cli": True}), encoding="utf-8")
        url, aviso = obsidian.link(self.vault, config=self.config)
        d = json.loads((self.config / "obsidian.json").read_text(encoding="utf-8"))
        self.assertEqual(aviso, "")
        self.assertIn("abc", d["vaults"])   # o vault que já existia continua
        self.assertTrue(d["cli"])
        vid = obsidian.vault_registrado(self.vault, self.config)
        self.assertEqual(url, f"obsidian://open?vault={vid}")
        self.assertTrue((self.config / "obsidian.json.gamemind.bak").exists())

    def test_vault_ja_registrado_nao_e_registrado_de_novo(self):
        self.config.mkdir()
        self.vault.mkdir(parents=True)
        (self.config / "obsidian.json").write_text(json.dumps({"vaults": {"v1": {"path": str(self.vault), "ts": 1}}}), encoding="utf-8")
        url, _ = obsidian.link(self.vault, config=self.config)
        self.assertEqual(url, "obsidian://open?vault=v1")
        self.assertEqual(len(json.loads((self.config / "obsidian.json").read_text(encoding="utf-8"))["vaults"]), 1)

    def test_link_de_uma_nota_leva_o_caminho_dela_sem_a_extensao(self):
        self.config.mkdir()
        self.vault.mkdir(parents=True)
        (self.config / "obsidian.json").write_text(json.dumps({"vaults": {"v1": {"path": str(self.vault)}}}), encoding="utf-8")
        nota = self.vault / "Personagens" / "Aldric Voss.md"
        url, _ = obsidian.link(self.vault, nota, self.config)
        self.assertEqual(url, "obsidian://open?vault=v1&file=Personagens/Aldric%20Voss")

    def test_obsidian_aberto_nao_tem_o_arquivo_reescrito_e_o_usuario_e_avisado(self):
        self.config.mkdir()
        (self.config / "obsidian.json").write_text(json.dumps({"vaults": {}}), encoding="utf-8")
        self.aberto.return_value = True
        url, aviso = obsidian.link(self.vault, config=self.config)
        self.assertIsNone(url)
        self.assertIn("Feche o Obsidian", aviso)
        self.assertEqual(json.loads((self.config / "obsidian.json").read_text(encoding="utf-8"))["vaults"], {})

    def test_sem_obsidian_instalado_diz_o_que_fazer(self):
        url, aviso = obsidian.link(self.vault, config=self.dir / "nao-existe")
        self.assertIsNone(url)
        self.assertIn(str(self.vault), aviso)
