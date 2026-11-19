"""Testes offline do núcleo do aplicativo (sem OCR, Tesseract nem Qt): repositório, consolidação, vault e observador.
As leituras são sintéticas, no formato de src/gamemind/nucleo/leitura.py.
Uso: python -m unittest discover -s tests -v"""
import io
import json
import os
import re
import sys
import tempfile
import time
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
from gamemind.nucleo.dicionario import aprender, grupos_de_nomes, para_gazetteer, unificar  # noqa: E402
from gamemind.nucleo.leitura import VERSAO_LEITURA  # noqa: E402
from gamemind.nucleo import leitura as leitura_mod  # noqa: E402
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

    def test_notas_aparecem_durante_a_leitura_e_nao_so_no_final(self):
        self.jogo.set("pasta_capturas", str(self.capturas))
        self.midia("a.jpg")
        self.midia("b.jpg")
        textos = {"a.jpg": "Aldric", "b.jpg": "Brisa"}
        ler = lambda caminho, *a, **k: ({"tipo": "imagem", "quadros": [quadro(textos[caminho.name])]}, 0.1)
        eventos = []
        with mock.patch.object(pl, "ler", ler), mock.patch.object(pl, "INTERVALO_PARCIAL_S", 0):
            pl.Pipeline(self.jogo, Config(ia="", workers=1), eventos.append).processar()
        etapas = [e.etapa for e in eventos]
        inicio_final = etapas.index("grafo")
        parciais = {Path(e.arquivo).name for e in eventos[:inicio_final] if e.etapa == "vault"}
        self.assertTrue(all(e.parcial for e in eventos[:inicio_final] if e.etapa == "vault"))
        self.assertIn("Aldric.md", parciais)    # gravada logo depois da primeira leitura, antes da geração final
        # a geração final só regrava o que mudou; a nota de Aldric já estava pronta
        finais = [Path(e.arquivo).name for e in eventos[inicio_final:] if e.etapa == "vault"]
        self.assertNotIn("Aldric.md", finais)
        self.assertTrue((self.jogo.pasta_vault / "Personagens" / "Brisalda.md").exists())

    def test_limpar_apaga_so_o_que_foi_gerado_e_a_rodada_refaz(self):
        self.jogo.set("pasta_capturas", str(self.capturas))
        self.lida("a.jpg", {"tipo": "imagem", "quadros": [quadro("Aldric e Brisa")]})
        pipe = pl.Pipeline(self.jogo, Config(ia=""))
        pipe.processar()
        vault = self.jogo.pasta_vault
        (vault / ".obsidian").mkdir()
        (vault / ".obsidian" / "app.json").write_text("{}", encoding="utf-8")
        (vault / "Personagens" / "minha nota.md").write_text("minha", encoding="utf-8")
        fora = self.dir / "fora.md"
        fora.write_text("não é do vault", encoding="utf-8")
        manifesto = json.loads((vault / pl.MANIFESTO).read_text(encoding="utf-8"))
        (vault / pl.MANIFESTO).write_text(json.dumps(manifesto + ["../fora.md"]), encoding="utf-8")   # nunca apaga fora do vault

        n = pl.limpar(self.jogo)
        self.assertEqual(n, len(manifesto))
        self.assertFalse((vault / "Personagens" / "Aldric.md").exists())
        self.assertFalse((vault / "Quadro da partida.canvas").exists())
        self.assertFalse((vault / pl.MANIFESTO).exists())
        self.assertFalse(self.jogo.caminho_grafo.exists())
        self.assertTrue((vault / "Personagens" / "minha nota.md").exists())     # do usuário: fica
        self.assertTrue((vault / ".obsidian" / "app.json").exists())
        self.assertTrue(fora.exists())
        self.assertEqual(self.jogo.midias()[0].estado, "lida")                  # só o vault: a leitura fica guardada

        with mock.patch.object(pl.Jogo, "registrar", return_value=False):
            rel = pipe.processar()
        self.assertEqual((rel.lidas, rel.notas), (0, 2))                        # refeito sem ler de novo
        self.assertTrue((vault / "Personagens" / "Aldric.md").exists())

    def test_limpar_tudo_faz_a_proxima_rodada_ler_de_novo(self):
        self.jogo.set("pasta_capturas", str(self.capturas))
        m = self.lida("a.jpg", {"tipo": "imagem", "quadros": [quadro("Aldric")]})
        self.jogo.gravar_llm(m.id, "falsa", {"entidades": [], "relacoes": []}, {})
        pl.Pipeline(self.jogo, Config(ia="")).processar()
        (self.jogo.pasta / "resumos.json").write_text("{}", encoding="utf-8")
        (self.jogo.pasta / "chat.json").write_text("[]", encoding="utf-8")
        r = reg.carregar(self.jogo.pasta)
        r.caixas["legenda"] = (0.1, 0.7, 0.9, 0.95)
        r.meta.update({"aprendido_em": "2026-01-01", "regioes": {"legenda": {"origem": "ia"}}})
        reg.salvar(self.jogo.pasta, r)
        vault = self.jogo.pasta_vault
        (vault / "_midia").mkdir(exist_ok=True)
        (vault / "_midia" / "antiga.jpg").write_bytes(b"x")                    # fora do manifesto: de uma versão anterior
        (vault / "_canvas").mkdir()
        (vault / "_canvas" / "velho.canvas").write_text("{}", encoding="utf-8")

        pl.limpar(self.jogo, tudo=True)
        self.assertEqual(self.jogo.midias(), [])                                # como um jogo recém-criado
        self.assertIsNone(self.jogo.llm(m.id, "falsa"))
        self.assertEqual(self.jogo.anotacoes(), {})
        self.assertEqual(self.jogo.get("pasta_capturas"), str(self.capturas))   # só a pasta de capturas fica
        for nome in ("dicionario.json", "resumos.json", "regioes.json", "grafo.json", "chat.json"):
            self.assertFalse((self.jogo.pasta / nome).exists(), nome)
        self.assertFalse(reg.carregar(self.jogo.pasta).aprendida)               # regiões voltam aos padrões genéricos
        self.assertFalse((vault / "_midia").exists())
        self.assertFalse((vault / "_canvas").exists())
        self.assertTrue((self.jogo.pasta / "dicionario_manual.json").exists())   # escrito à mão: fica

        rel = pl.Pipeline(self.jogo, Config(ia="")).processar()                  # a rodada seguinte começa do zero
        self.assertEqual((rel.novas, rel.lidas + rel.erros), (1, 1))             # registra e lê de novo (a.jpg do teste não é imagem)

    def test_limpar_tudo_mantem_so_a_regiao_editada_a_mao(self):
        r = reg.carregar(self.jogo.pasta)
        r.caixas["legenda"], r.caixas["hud"] = (0.1, 0.7, 0.9, 0.95), (0.6, 0.1, 1.0, 0.5)
        r.meta.update({"aprendido_em": "2026-01-01", "regioes": {"legenda": {"origem": "manual"}, "hud": {"origem": "ia"}}})
        reg.salvar(self.jogo.pasta, r)
        pl.limpar(self.jogo, tudo=True)
        r = reg.carregar(self.jogo.pasta)
        self.assertEqual(r.caixas["legenda"], (0.1, 0.7, 0.9, 0.95))
        self.assertEqual(r.caixas["hud"], reg.PADRAO["hud"])
        self.assertFalse(r.aprendida)

    def test_erro_de_leitura_nao_para_a_rodada(self):
        self.jogo.set("pasta_capturas", str(self.capturas))
        self.midia("quebrada.jpg", b"nao e imagem")
        rel = pl.Pipeline(self.jogo, Config(ia="")).processar()
        self.assertEqual((rel.novas, rel.erros), (1, 1))
        self.assertEqual(self.jogo.midias()[0].estado, "erro")

    def test_ia_indisponivel_gera_grafo_sem_llm(self):
        self.jogo.set("pasta_capturas", str(self.capturas))
        self.lida("a.jpg", {"tipo": "imagem", "quadros": [quadro("Aldric")]})
        rel = pl.Pipeline(self.jogo, Config(ia="gemini")).processar()          # IA retirada, guardada numa configuração antiga
        self.assertIn("Configurar jogo", rel.erro_llm)
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
        anexos, secoes, geradas = canvas.gerar(g, vault, midias)
        exportar(g, vault, anexos, secoes=secoes)
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

    def test_mundo_da_partida_destaques_no_centro_vizinhos_dos_lados(self):
        from gamemind.nucleo import canvas
        vault, geradas = self.gerar()
        c = self.verificar(vault, "Quadro da partida.canvas")
        cartoes = {n["file"]: n for n in c["nodes"] if n["type"] == "file" and n["file"].endswith(".md")}
        lista = [n["file"] for n in c["nodes"] if n["type"] == "file" and n["file"].endswith(".md")]
        self.assertEqual(len(lista), len(set(lista)))                            # cada entidade uma vez só
        topo = min(cartoes.values(), key=lambda n: n["y"])
        self.assertEqual((topo["file"], topo["width"]), ("Personagens/Recorrente.md", canvas.W_PROT))   # protagonista no alto

        def coluna(arquivo):   # a coluna (grupo sem rótulo) em que o cartão está
            n = cartoes[arquivo]
            return next((g["id"] for g in c["nodes"] if g["type"] == "group" and not g.get("label")
                         and g["x"] <= n["x"] < g["x"] + g["width"] and g["y"] <= n["y"] < g["y"] + g["height"]), None)
        planalto = coluna("Locais/Planalto Norte.md")
        for membro in ("Locais/Vale Alto.md", "Personagens/Aldric.md", "Personagens/Brisa.md"):   # parte, fica em, vista junto
            self.assertEqual(coluna(membro), planalto, membro)
            self.assertGreater(cartoes[membro]["y"], cartoes["Locais/Planalto Norte.md"]["y"])     # embaixo do lugar
        self.assertEqual(coluna("Personagens/Marek.md"), coluna("Faccoes/Ordem do Corvo.md"))    # facção sem lugar, com membro
        self.assertNotEqual(coluna("Faccoes/Ordem do Corvo.md"), planalto)                      # outra coluna, ao lado
        for solto in ("Personagens/Dario.md", "Locais/Torre Velha.md"):                          # sem ligação: embaixo, menor
            self.assertEqual((cartoes[solto]["width"], coluna(solto)), (canvas.W_MENOR, None))
        self.assertNotIn("Missoes/A Colheita Perdida.md", cartoes)              # missão: só na lista de referência
        textos = [n["text"] for n in c["nodes"] if n["type"] == "text"]
        self.assertTrue(any(t.startswith("**Missões**") and "[[A Colheita Perdida]]" in t for t in textos))
        self.assertTrue(any("[[Vale Alto]] parte de Planalto Norte" in t for t in textos))   # só informação do jogo no bloco
        self.assertFalse(any("captura" in t or "%" in t or "GameMind" in t for t in textos))   # nada de estatística ou legenda
        por_id = {n["id"]: n for n in c["nodes"]}
        aldric = next(e for e in c["edges"] if por_id[e["fromNode"]].get("file") == "Personagens/Aldric.md")
        self.assertEqual((por_id[aldric["toNode"]]["file"], aldric["label"], aldric["fromSide"]), ("Locais/Vale Alto.md", "fica em", "right"))
        self.assertFalse(any(e["label"] and "tela" in e["label"] for e in c["edges"]))
        self.assertFalse(any(por_id[e[k]].get("file", "").startswith("Missoes/") for e in c["edges"] for k in ("fromNode", "toNode")))
        self.assertIn("_midia/a.jpg", geradas)

    def test_quadro_grande_colapsa_o_que_pesa_pouco(self):
        import random
        from gamemind.nucleo import canvas
        rnd = random.Random(1)
        tipos = ["personagem"] * 4 + ["local"] * 3 + ["faccao", "criatura", "item", "missao"]
        nos = [{"nome": f"N{i}", "tipo": rnd.choice(tipos),
                "fontes": [{"arquivo": f"c{rnd.randrange(400)}.png"} for _ in range(min(60, int(rnd.paretovariate(1.2))))]} for i in range(300)]
        mundo = [n for n in nos if n["tipo"] in canvas.TIPOS_MUNDO]
        arestas = [{"sujeito": a["nome"], "predicado": "relacionado_a", "objeto": b["nome"]} for a, b in (rnd.sample(mundo, 2) for _ in range(120))]
        vault = self.dir / "grande"
        from exportar_vault import exportar
        canvas.gerar({"nos": nos, "arestas": arestas}, vault, {})
        exportar({"nos": nos, "arestas": arestas}, vault)
        c = self.verificar(vault, "Quadro da partida.canvas")
        cartoes = [n for n in c["nodes"] if n["type"] == "file"]
        notas = [n for n in cartoes if n["file"].endswith(".md")]
        self.assertLessEqual(len(notas), canvas.MAX_PROTAGONISTAS + canvas.MAX_COLUNAS * (1 + canvas.MAX_MEMBROS) + canvas.MAX_OUTROS)
        self.assertLess(len(cartoes), len(mundo) / 2)
        textos = [n["text"] for n in c["nodes"] if n["type"] == "text"]
        self.assertTrue(any(t.endswith("· …") for t in textos))                  # listas de links têm limite
        nomes_visiveis = {Path(n["file"]).stem for n in cartoes} | {m for t in textos for m in re.findall(r"\[\[([^\]|]+)", t)}
        self.assertGreater(len(nomes_visiveis), len(cartoes))                   # quem não ganhou cartão continua alcançável por link

    def test_contexto_vai_na_propria_nota_sem_canvas_por_entidade(self):
        vault, geradas = self.gerar()
        self.assertEqual([g for g in geradas if g.endswith(".canvas")], ["Quadro da partida.canvas"])   # um canvas só: o do mundo
        self.assertFalse((vault / "_canvas").exists())
        aldric = (vault / "Personagens" / "Aldric.md").read_text(encoding="utf-8")
        self.assertIn("[[Quadro da partida.canvas|Ver no mundo da partida]]", aldric)
        self.assertIn("## Capturas", aldric)
        self.assertIn("![[_midia/a.jpg|240]]", aldric)
        self.assertTrue((vault / "_midia" / "a.jpg").exists())
        self.assertIn("[[A Colheita Perdida]]", aldric)                        # missão continua só como relação na nota
        vale = (vault / "Locais" / "Vale Alto.md").read_text(encoding="utf-8")
        co = vale.split("## Vistos nas mesmas telas", 1)[1].split("##", 1)[0]
        self.assertIn("[[Brisa]]", co)                                          # vista junto, sem relação afirmada
        self.assertNotIn("[[Aldric]]", co)                                      # relação lida não se repete como "vistos junto"
        self.assertLess(vale.index("## Vistos nas mesmas telas"), vale.index("## Fontes"))
        dario = (vault / "Personagens" / "Dario.md").read_text(encoding="utf-8")
        self.assertNotIn("## Vistos nas mesmas telas", dario)                   # tela de lista não conta como "junto"
        missao = (vault / "Missoes" / "A Colheita Perdida.md").read_text(encoding="utf-8")
        self.assertNotIn("## Capturas", missao)                                 # missões e itens ficam só com as fontes
        self.assertNotIn("mundo da partida", missao)

    def test_canvas_antigo_de_entidade_e_apagado(self):
        self.jogo.set("pasta_capturas", str(self.capturas))
        self.lida("a.jpg", {"tipo": "imagem", "quadros": [quadro("Aldric e Brisa")]})
        vault = self.jogo.pasta_vault
        velho = vault / "_canvas" / "Personagens" / "Aldric.canvas"
        velho.parent.mkdir(parents=True)
        velho.write_text("{}", encoding="utf-8")
        (vault / pl.MANIFESTO).write_text(json.dumps(["_canvas/Personagens/Aldric.canvas"]), encoding="utf-8")
        pl.Pipeline(self.jogo, Config(ia="")).processar()
        self.assertFalse((vault / "_canvas").exists())                          # o arquivo e as pastas que ficaram vazias


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


class TestRegioesComImagem(Base):
    """Regiões aprendidas durante a leitura: cada captura de cena vai ao modelo logo depois do OCR, até as estimativas
    pararem de mudar; o que falta ler já usa as regiões novas. Só na rodada com IA e só neste jogo."""
    CENA = "Aldric: vamos embora daqui\nObjetivo: siga a estrada\nNovo marcador no mapa"
    MENU = "\n".join(f"Entrada {i} do diário com bastante texto" for i in range(30))

    def rodada(self, config, cenas=8, menus=0, ja_lidas=0):
        """Uma rodada com o OCR e a IA falsos. Devolve (relatório, caixas passadas a cada OCR, mídias relidas, IA)."""
        self.jogo.set("pasta_capturas", str(self.capturas))
        for i in range(ja_lidas):
            self.lida(f"antiga{i}.jpg", {"tipo": "imagem", "quadros": [quadro(self.CENA)]})
        textos = {}
        for i in range(cenas):
            self.midia(f"cena{i}.jpg", bytes([i]))
            textos[f"cena{i}.jpg"] = self.CENA
        for i in range(menus):
            self.midia(f"menu{i}.jpg", bytes([100 + i]))
            textos[f"menu{i}.jpg"] = self.MENU
        caixas_do_ocr, relidas, ia = [], [], IAFalsa()

        def ler(caminho, tipo, intervalo, workers, lang, rois):
            caixas_do_ocr.append(rois["legenda"])
            return {"tipo": "imagem", "quadros": [quadro(textos[caminho.name])], "rois": leitura_mod._caixas(rois)}, 0.01

        def reler(caminho, tipo, leitura, rois, lang):
            relidas.append(caminho.name)
            return {**leitura, "rois": {**leitura.get("rois", {}), **leitura_mod._caixas(rois)}}

        with mock.patch.multiple(pl.regioes_mod, quadro_da_midia=mock.DEFAULT, linhas_com_posicao=mock.DEFAULT) as m, \
                mock.patch.object(pl.visao, "escolher", return_value="visao-falsa"), \
                mock.patch.object(pl.visao, "imagem_marcada", return_value="img"), mock.patch.object(pl, "OllamaBackend", return_value=ia), \
                mock.patch.object(pl, "ler", side_effect=ler), mock.patch.object(pl, "reler_regioes", side_effect=reler), \
                mock.patch.object(pl.Pipeline, "_gerar"):
            m["quadro_da_midia"].return_value = object()
            m["linhas_com_posicao"].return_value = [linha(0.05, 0.62, 0.95), linha(0.25, 0.66, 0.75), linha(0.3, 0.70, 0.7)]
            rel = pl.Pipeline(self.jogo, config).processar()
        return rel, caixas_do_ocr, relidas, ia

    def test_aprende_durante_a_leitura_ate_parar_de_ajustar_e_o_resto_usa_as_regioes_novas(self):
        outro = Jogo(self.dir / "outro")
        self.addCleanup(outro.fechar)
        _, caixas_do_ocr, relidas, ia = self.rodada(Config(ia="ollama", workers=1), cenas=8)
        r = reg.carregar(self.jogo.pasta)
        self.assertTrue(r.aprendida and r.meta["convergiu"] and r.meta["com_imagem"])
        self.assertEqual(r.meta["capturas_lidas"], reg.MINIMO_CONVERGIR + reg.ESTAVEIS - 1)   # parou sem ajuste expressivo
        self.assertLess(len(ia.imagens), 8)                                       # nem todas as cenas foram ao modelo
        self.assertLess(r.caixas["legenda"][1], reg.PADRAO["legenda"][1])
        antigas = [c for c in caixas_do_ocr if c != r.caixas["legenda"]]
        self.assertEqual(len(relidas), len(antigas))                             # só o que foi lido antes de concluir é relido
        for m, l in self.jogo.leituras():
            self.assertEqual(leitura_mod.recortes_desatualizados(l, r.caixas), [], m.nome)
        self.assertEqual(reg.carregar(outro.pasta).caixas, reg.PADRAO)          # o outro jogo não muda

    def test_poucas_capturas_de_cena_espera_a_proxima_rodada(self):
        self.rodada(Config(ia="ollama"), cenas=2, menus=5)
        self.assertFalse(reg.carregar(self.jogo.pasta).aprendida)               # tenta de novo quando houver mais

    def test_jogo_ja_lido_aprende_pelas_leituras_guardadas(self):
        _, caixas_do_ocr, relidas, _ = self.rodada(Config(ia="ollama"), cenas=0, ja_lidas=6)
        self.assertEqual(caixas_do_ocr, [])                                      # nada para ler: só as leituras guardadas
        self.assertTrue(reg.carregar(self.jogo.pasta).aprendida)
        self.assertEqual(len(relidas), 6)                                         # todas lidas com a região antiga: só o recorte

    def test_so_ocr_nao_usa_modelo_de_imagem_e_opcao_desligada_tambem_nao(self):
        with mock.patch.object(pl.visao, "escolher", return_value="visao-falsa"):
            self.assertIsNone(pl.Pipeline(self.jogo, Config(ia=""))._aprendiz())
            self.assertIsNone(pl.Pipeline(self.jogo, Config(ia="ollama", regioes_por_imagem=False))._aprendiz())

    def test_recorte_feito_com_outra_caixa_esta_desatualizado(self):
        lido = {"rois": leitura_mod._caixas(reg.PADRAO)}
        novas = {**reg.PADRAO, "legenda": (0.08, 0.6, 0.92, 0.92)}
        self.assertEqual(leitura_mod.recortes_desatualizados(lido, novas), ["legenda"])
        self.assertEqual(leitura_mod.recortes_desatualizados({}, reg.PADRAO), [])   # leitura antiga, sem registro: os padrões

    def test_releitura_troca_so_o_recorte_que_mudou(self):
        from PIL import Image
        from gamemind.nucleo.leitura import reler_regioes
        Image.new("RGB", (640, 360), "black").save(self.capturas / "p.png")
        leitura = {"tipo": "imagem", "quadros": [{"t": 0.0, "secoes": {"tela": "TELA", "legenda": "VELHA", "hud": "HUD"}}]}
        nova = reler_regioes(self.capturas / "p.png", "imagem", leitura, {"legenda": (0.1, 0.5, 0.9, 0.9)}, "eng")
        self.assertEqual(nova["quadros"][0]["secoes"]["tela"], "TELA")
        self.assertEqual(nova["quadros"][0]["secoes"]["hud"], "HUD")
        self.assertNotEqual(nova["quadros"][0]["secoes"]["legenda"], "VELHA")
        self.assertEqual(leitura["quadros"][0]["secoes"]["legenda"], "VELHA")   # a original não é alterada

    def test_conector_descarrega_e_repete_quando_o_ollama_trava(self):
        from extracao.llm import OllamaBackend

        class Resp:
            def __init__(self, corpo):
                self.corpo = json.dumps(corpo).encode()

            def __enter__(self):
                return io.BytesIO(self.corpo)

            def __exit__(self, *a):
                return False
        respostas = [Resp({"done": False, "message": {"content": ""}}), Resp({}), Resp({"done": True, "message": {"content": '{"ok": 1}'}})]
        with mock.patch("urllib.request.urlopen", side_effect=respostas) as u:
            self.assertEqual(OllamaBackend("m").perguntar("i", "p", {}, ["img"]), {"ok": 1})
        self.assertEqual([json.loads(c.args[0].data).get("keep_alive") for c in u.call_args_list], ["10m", 0, "10m"])   # descarregou no meio


class TestTipoCorrigidoPelaIA(Base):
    def test_ia_corrige_tipo_aprendido_pelo_texto_mas_nao_o_manual(self):
        pipe = pl.Pipeline(self.jogo, Config(ia=""))
        pipe.entidades = {"Vale Alto": {"tipo": "personagem", "aliases": []}, "Aldric": {"tipo": "personagem", "aliases": []},
                          "Odo": {"tipo": "personagem", "aliases": []}}
        (self.jogo.pasta / "dicionario_manual.json").write_text(json.dumps({"Aldric": {"tipo": "personagem"}}), encoding="utf-8")
        gaz = para_gazetteer(pipe.entidades)
        lugar = lambda *nomes: {"entidades": [{"nome": n, "tipo": "local"} for n in nomes]}   # noqa: E731
        respostas = {1: lugar("vale alto", "Aldric", "Odo"), 2: lugar("Vale Alto", "Aldric"), 3: {"entidades": [{"nome": "Vale Alto", "tipo": "local"}]}}
        self.assertEqual(pipe._tipos_da_ia(respostas, gaz), {"Vale Alto": "local"})   # Aldric é manual; Odo, uma captura só
        self.assertEqual(pipe.entidades["Vale Alto"]["tipo"], "local")
        self.assertEqual(pipe.entidades["Vale Alto"]["tipo_pelo_texto"], "personagem")


class TestRevisaoDasEntidades(Base):
    """Revisão de cada entidade pela IA, com o texto de todas as capturas dela: resumo, tipo certo, "não é entidade" e "mesmo
    que" outro nome; guardada e refeita só quando o pedido muda."""
    LEITURAS = {"a.jpg": {"quadros": [{"secoes": {"tela": "Aldric guarda a ponte de Vale Alto.\nO ferreiro de Vale Alto fala com Aldric"}}]},
                "b.jpg": {"quadros": [{"secoes": {"legenda": "Ric: Ninguém passa por Vale Alto."}}]},
                "c.jpg": {"quadros": [{"secoes": {"tela": "Vale Aldo, a vila"}}]}}

    def grafo(self):
        return {"nos": [{"nome": "Aldric", "tipo": "personagem", "aliases": ["Ric"], "fontes": [{"arquivo": "a.jpg"}, {"arquivo": "b.jpg"}]},
                        {"nome": "Vale Alto", "tipo": "local", "aliases": [], "fontes": [{"arquivo": "a.jpg"}, {"arquivo": "b.jpg"}]},
                        {"nome": "Vale Aldo", "tipo": "personagem", "aliases": [], "fontes": [{"arquivo": "c.jpg"}]},
                        {"nome": "Ferreiro", "tipo": "local", "aliases": [], "fontes": [{"arquivo": "a.jpg"}]}],
                "arestas": [{"sujeito": "Vale Aldo", "predicado": "relacionado_a", "objeto": "Aldric", "fontes": []},
                            {"sujeito": "Ferreiro", "predicado": "relacionado_a", "objeto": "Aldric", "fontes": []}]}

    class IA:
        nome = "falsa"
        RESPOSTAS = {"Aldric": {"tipo": "personagem", "mesmo_que": "", "resumo": "Aldric guarda a ponte de Vale Alto."},
                     "Vale Alto": {"tipo": "local", "mesmo_que": "", "resumo": "Vale Alto tem uma ponte guardada."},
                     "Vale Aldo": {"tipo": "local", "mesmo_que": "Vale Alto", "resumo": ""},
                     "Ferreiro": {"tipo": "nenhum", "mesmo_que": "", "resumo": "Um ferreiro de Morgana."}}   # Morgana: inventado

        def __init__(self):
            self.pedidos = []

        def perguntar(self, instrucoes, pedido, esquema):
            self.pedidos.append(pedido)
            nomes = [l[4:] for l in pedido.splitlines() if l.startswith("### ")]
            return {"entidades": [{"nome": n, **self.RESPOSTAS[n]} for n in nomes]}

    def test_trechos_so_as_linhas_que_citam_o_nome_ou_apelido(self):
        from gamemind.nucleo import resumos
        no = self.grafo()["nos"][0]
        self.assertEqual(resumos.trechos(no, self.LEITURAS),
                         "Aldric guarda a ponte de Vale Alto.\nO ferreiro de Vale Alto fala com Aldric\nRic: Ninguém passa por Vale Alto.")
        self.assertEqual(resumos.trechos({"nome": "Ric", "fontes": [{"arquivo": "a.jpg"}]}, self.LEITURAS), "")   # palavra inteira

    def test_parecidos_de_qualquer_tipo(self):
        from gamemind.nucleo import resumos
        nos = self.grafo()["nos"]
        self.assertEqual(resumos.parecidos(nos[2], nos), ["Vale Alto"])

    def test_revisao_em_lote_guardada_e_aplicada(self):
        from gamemind.nucleo import resumos
        ia = self.IA()
        self.assertEqual(resumos.revisar(self.grafo(), self.LEITURAS, ia, self.dir), 1)   # 4 entidades, um lote
        self.assertEqual(resumos.revisar(self.grafo(), self.LEITURAS, ia, self.dir), 0)   # nada mudou: não pergunta de novo
        g = resumos.aplicar(self.grafo(), resumos.carregar(self.dir))
        nos = {n["nome"]: n for n in g["nos"]}
        self.assertEqual(sorted(nos), ["Aldric", "Vale Alto"])                  # Vale Aldo juntou; Ferreiro não é entidade
        self.assertIn("Vale Aldo", nos["Vale Alto"]["aliases"])
        self.assertEqual({f["arquivo"] for f in nos["Vale Alto"]["fontes"]}, {"a.jpg", "b.jpg", "c.jpg"})
        self.assertEqual(nos["Aldric"]["descricao"], "Aldric guarda a ponte de Vale Alto.")
        self.assertEqual([(a["sujeito"], a["objeto"]) for a in g["arestas"]], [("Vale Alto", "Aldric")])   # aresta seguiu o nome
        self.assertEqual(resumos.carregar(self.dir)["Ferreiro"]["resumo"], "")   # citava nome fora do texto lido

    def test_travas_da_revisao(self):
        from gamemind.nucleo import resumos
        resumos.revisar(self.grafo(), self.LEITURAS, self.IA(), self.dir)
        cache = resumos.carregar(self.dir)
        g = self.grafo()
        g["nos"][3]["fontes"] = [{"arquivo": f"x{i}.jpg"} for i in range(5)]   # visto em muitas capturas: não é descartado
        self.assertIn("Ferreiro", {n["nome"] for n in resumos.aplicar(g, cache)["nos"]})
        g = resumos.aplicar(self.grafo(), cache, manuais={"Vale Aldo"})          # nome do dicionário manual: não muda
        self.assertIn("Vale Aldo", {n["nome"] for n in g["nos"]})
        g = self.grafo()
        g["nos"][1]["tipo"] = "faccao"                                            # o grafo mudou: a revisão antiga não vale
        self.assertEqual(next(n for n in resumos.aplicar(g, cache)["nos"] if n["nome"] == "Vale Alto")["tipo"], "faccao")

    def test_mesmo_que_nos_dois_sentidos_fica_o_mais_visto_e_nao_junta_dois_nomes_estabelecidos(self):
        from gamemind.nucleo import resumos
        g = self.grafo()
        g["nos"][1]["fontes"] = [{"arquivo": f"v{i}.jpg"} for i in range(9)]       # Vale Alto: visto em muitas capturas
        cache = {"Vale Alto": {"tipo_atual": "local", "tipo": "local", "mesmo_que": "Vale Aldo", "resumo": ""},
                 "Vale Aldo": {"tipo_atual": "personagem", "tipo": "local", "mesmo_que": "Vale Alto", "resumo": ""}}
        nomes = {n["nome"] for n in resumos.aplicar(json.loads(json.dumps(g)), cache)["nos"]}
        self.assertIn("Vale Alto", nomes)                                         # o mais visto fica
        self.assertNotIn("Vale Aldo", nomes)
        g["nos"][2]["fontes"] = [{"arquivo": f"w{i}.jpg"} for i in range(5)]       # os dois bem vistos: são coisas diferentes
        nomes = {n["nome"] for n in resumos.aplicar(json.loads(json.dumps(g)), cache)["nos"]}
        self.assertTrue({"Vale Alto", "Vale Aldo"} <= nomes)

    def test_mesmo_que_fora_da_lista_de_parecidos_e_ignorado(self):
        from gamemind.nucleo import resumos

        class Inventa(self.IA):
            RESPOSTAS = {**self.IA.RESPOSTAS, "Aldric": {"tipo": "personagem", "mesmo_que": "Morgana", "resumo": ""}}
        resumos.revisar(self.grafo(), self.LEITURAS, Inventa(), self.dir)
        self.assertEqual(resumos.carregar(self.dir)["Aldric"]["mesmo_que"], "")

    def test_ia_sem_pergunta_livre_nao_quebra(self):
        from gamemind.nucleo import resumos
        from extracao.llm import Backend
        self.assertEqual(resumos.revisar(self.grafo(), self.LEITURAS, Backend(), self.dir), 0)


class TestNomesUnificados(Base):
    """Formas diferentes do mesmo nome que o OCR e a IA trazem em capturas diferentes viram um nó só."""

    def test_regras_de_juncao(self):
        m = grupos_de_nomes({("Ravena", "personagem"): 5, ("Ravena de Altamira", "personagem"): 3,
                             ("Grifo", "criatura"): 1, ("Grifos", "criatura"): 3,
                             ("Comandante Peter Saar", "personagem"): 1, ("Capitão Peter Saar", "personagem"): 1,
                             ("Exército", "faccao"): 2, ("Exército Imperial", "faccao"): 1, ("Exército do Norte", "faccao"): 1,
                             ("Vale", "local"): 1, ("Vale Alto", "faccao"): 1,
                             ("A Colheita", "missao"): 1, ("A Colheita Perdida", "missao"): 1})
        self.assertEqual(m, {"Ravena de Altamira": "Ravena",                   # forma completa: vale a mais vista
                             "Grifo": "Grifos",                                # singular e plural
                             "Capitão Peter Saar": "Comandante Peter Saar"})   # tratamento não faz parte do nome
        # "Exército" tem duas formas completas: ambíguo, fica; tipos diferentes e missões não se juntam

    def test_grafias_parecidas_sem_espaco_e_palavra_generica(self):
        m = grupos_de_nomes({("Monstro de Vale Alto", "criatura"): 9, ("Monstrodevale alto", "criatura"): 1,
                             ("Vila Saqueada", "local"): 2, ("Vila Sesáeada", "local"): 1,
                             ("Ilhas Vorna", "local"): 1, ("Vorna", "local"): 3,
                             ("Ordem do Corvo", "faccao"): 2, ("Ordem do Lobo", "faccao"): 2,
                             ("Cavaleiros Negros", "faccao"): 1, ("Cavaleiros Brancos", "faccao"): 1})
        self.assertEqual(m, {"Monstrodevale alto": "Monstro de Vale Alto", "Ilhas Vorna": "Vorna"})
        # parecidas, mas abaixo do limiar: continuam separadas. "Vila Sesáeada" (erro de leitura) fica para a revisão pela IA,
        # que a recebe como parecida de "Vila Saqueada"; um limiar que a pegasse juntaria também os Cavaleiros Negros e Brancos

    def test_relacionado_a_de_tela_de_lista_nao_vira_relacao(self):
        from gamemind.nucleo.consolidacao import TELA_LISTA, somar_llm
        lista = [f"Criatura {i}" for i in range(TELA_LISTA + 1)]
        base = {1: {"arquivo": "a.jpg", "tipo_tela": "glossario", "relacoes": [],
                    "entidades": [{"nome": n, "tipo": "criatura"} for n in lista]}}
        resposta = {1: {"entidades": [], "relacoes": [{"sujeito": lista[0], "predicado": "relacionado_a", "objeto": lista[1]}]}}
        m = self.lida("a.jpg", {"tipo": "imagem", "quadros": [quadro(" ".join(lista))]})
        base[m.id] = base.pop(1)
        resposta[m.id] = resposta.pop(1)
        gaz = para_gazetteer({n: {"tipo": "criatura", "aliases": []} for n in lista})
        anot = somar_llm(base, [(m, self.jogo.leituras()[0][1])], resposta, gaz)
        from gamemind.nucleo.consolidacao import EVIDENCIA_LISTA
        self.assertEqual([r["evidencia"] for r in anot[m.id]["relacoes"]], [EVIDENCIA_LISTA])   # marcada, não descartada
        pipe = pl.Pipeline(self.jogo, Config(ia=""))
        pipe.entidades = {}
        self.assertEqual(pipe._grafo(self.jogo.leituras(), anot)["arestas"], [])          # uma captura de lista só: fora
        n = self.lida("b.jpg", {"tipo": "imagem", "quadros": [quadro(" ".join(lista))]})
        anot[n.id] = {**anot[m.id], "arquivo": "b.jpg"}
        self.assertEqual(len(pipe._grafo(self.jogo.leituras(), anot)["arestas"]), 1)       # confirmada em outra captura: fica

    def test_nome_do_dicionario_manual_sempre_vence(self):
        m = grupos_de_nomes({("Ravena", "personagem"): 5, ("Ravena de Altamira", "personagem"): 1}, {"Ravena de Altamira"})
        self.assertEqual(m, {"Ravena": "Ravena de Altamira"})

    def test_unificar_leva_os_apelidos_e_nao_cria_nome_sozinho(self):
        ent = {"Ravena": {"tipo": "personagem", "aliases": ["Rav"]}, "Ravena de Altamira": {"tipo": "personagem", "aliases": ["Senhora de Altamira"]}}
        u = unificar(ent, {("Ravena", "personagem"): 4, ("Ravena de Altamira", "personagem"): 2, ("Odo", "personagem"): 1})
        self.assertEqual(set(u), {"Ravena"})
        self.assertEqual(sorted(u["Ravena"]["aliases"]), ["Rav", "Ravena de Altamira", "Senhora de Altamira"])
        self.assertIn("Ravena de Altamira", ent)                              # o dicionário original não muda

    def test_grafo_junta_nomes_da_ia_e_a_relacao_chega_ao_no_unico(self):
        leituras = [(self.lida(f"{c}.jpg", {"tipo": "imagem", "quadros": [quadro("x")]}), {}) for c in "abc"]
        anot = {leituras[0][0].id: {"arquivo": "a.jpg", "tipo_tela": "diario", "relacoes": [],
                                     "entidades": [{"nome": "Ravena", "tipo": "personagem"}, {"nome": "Aldric", "tipo": "personagem"}]},
                leituras[1][0].id: {"arquivo": "b.jpg", "tipo_tela": "glossario", "entidades": [
                    {"nome": "Ravena de Altamira", "tipo": "personagem"}, {"nome": "Aldric", "tipo": "personagem"},
                    {"nome": "Ravena", "tipo": "personagem"}],
                    "relacoes": [{"sujeito": "Aldric", "predicado": "relacionado_a", "objeto": "Ravena de Altamira"},
                                 {"sujeito": "Ravena", "predicado": "relacionado_a", "objeto": "Ravena de Altamira"}]},
                leituras[2][0].id: {"arquivo": "c.jpg", "tipo_tela": "diario", "relacoes": [],
                                     "entidades": [{"nome": "Ravena", "tipo": "personagem"}]}}
        pipe = pl.Pipeline(self.jogo, Config(ia=""))
        pipe.entidades = {}
        g = pipe._grafo(leituras, anot)
        ravena = next(n for n in g["nos"] if n["nome"] == "Ravena")
        self.assertEqual(sorted(n["nome"] for n in g["nos"]), ["Aldric", "Ravena"])
        self.assertEqual(ravena["aliases"], ["Ravena de Altamira"])
        self.assertEqual([f["arquivo"] for f in ravena["fontes"]], ["a.jpg", "b.jpg", "c.jpg"])   # b.jpg uma vez só
        self.assertEqual([(a["sujeito"], a["objeto"]) for a in g["arestas"]], [("Aldric", "Ravena")])   # sem Ravena -> Ravena


class IAFalsa:
    """Responde à pergunta de papéis como uma IA que acerta: fala embaixo é legenda, canto de cima à direita é objetivo."""
    nome = "falsa"

    def __init__(self, tela="cena"):
        self.tela, self.imagens = tela, []

    def carregar(self, com_imagem=False):
        self.carregado = com_imagem

    def perguntar(self, instrucoes, pedido, esquema, imagens=None):
        self.imagens.append(imagens)
        linhas = []
        for l in pedido.splitlines():
            i = int(l.split(".")[0])
            y = float(l.split("y=")[1].split()[0])
            x = float(l.split("x=")[1].split("-")[0])
            linhas.append({"id": i, "papel": "legenda" if y > 0.6 else "objetivo" if x > 0.7 and y < 0.3 else "menu"})
        resp = {"linhas": linhas + [{"id": 999, "papel": "legenda"}, {"id": 0, "papel": "inventado"}]}   # ids e papéis inválidos são ignorados
        if not imagens:
            return resp
        listas = {p: [l["id"] for l in linhas if l["papel"] == p] + [999, 0] for p in reg.PAPEIS_VISAO}   # com imagem: só os números
        return {"tela": self.tela, **listas}


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

    def amostra(self, linhas):
        papeis = reg.classificar(IAFalsa(), linhas)
        return [(l, papeis[i]) for i, l in enumerate(linhas) if i in papeis]

    def test_ia_define_a_regiao_pela_posicao_das_linhas_e_o_arquivo_guarda(self):
        # legendas um pouco mais altas que o padrão (y 0,62) e mais largas: a região cresce para alcançá-las
        linhas = [linha(0.05, 0.62, 0.95), linha(0.25, 0.66, 0.75), linha(0.1, 0.1, 0.4), linha(0.80, 0.10, 0.98)]
        r = reg.estimar(reg.Regioes(), [self.amostra(linhas)] * 3)
        x0, y0, x1, y1 = r.caixas["legenda"]
        p = reg.PADRAO["legenda"]
        self.assertTrue(x0 < p[0] and y0 < 0.62 and x1 > p[2], r.caixas["legenda"])          # cresceu até onde o texto foi visto
        self.assertTrue(y1 >= p[3])                                                           # e não encolheu do outro lado
        self.assertEqual(r.origem["legenda"], "ia")
        self.assertEqual(r.origem["aviso"], "padrao")   # a IA não achou aviso: fica o padrão
        reg.salvar(self.pasta, r)
        self.assertEqual(reg.carregar(self.pasta).caixas["legenda"], tuple(round(v, 3) for v in r.caixas["legenda"]))

    def aprendiz(self, ia, linhas_por_amostra, prazo_s=0):
        class M:
            def __init__(self, i):
                self.id, self.nome, self.caminho, self.tipo = i, f"m{i}", f"m{i}.jpg", "imagem"
        cena = {"quadros": [{"secoes": {"tela": "Aldric: vamos embora daqui\nObjetivo: siga a estrada\nNovo marcador no mapa"}}]}
        a = reg.Aprendiz(ia, reg.Regioes(), marcar=lambda q, l: "img", prazo_s=prazo_s)
        with mock.patch.object(reg, "quadro_da_midia", return_value=object()), \
                mock.patch.object(reg, "linhas_com_posicao", side_effect=linhas_por_amostra):
            usadas = [a.considerar(M(i), cena) for i in range(10)]
        return a, usadas

    def test_aprendiz_para_quando_as_estimativas_param_de_mudar(self):
        linhas = [linha(0.05, 0.62, 0.95), linha(0.25, 0.66, 0.75), linha(0.3, 0.70, 0.7)]
        a, usadas = self.aprendiz(IAFalsa(), [linhas] * 10)
        self.assertTrue(a.convergiu)
        self.assertEqual(sum(usadas), reg.MINIMO_CONVERGIR + reg.ESTAVEIS - 1)
        r = a.resultado()
        self.assertTrue(r.aprendida and r.meta["convergiu"])
        self.assertLess(r.caixas["legenda"][1], reg.PADRAO["legenda"][1])

    def test_aprendiz_continua_enquanto_a_estimativa_muda_e_para_no_teto(self):
        # a legenda aparece um pouco mais alta a cada captura (sempre acima de 0,6, onde a IA falsa a reconhece)
        subindo = [[linha(0.05, 0.70 - 0.025 * k, 0.95), linha(0.25, 0.71, 0.75), linha(0.3, 0.72, 0.7)] for k in range(10)]
        with mock.patch.object(reg, "MAX_AMOSTRAS", 4):
            a, usadas = self.aprendiz(IAFalsa(), subindo)
        self.assertEqual(sum(usadas), 4)                                         # cada amostra ainda mexia na região
        self.assertFalse(a.convergiu)
        self.assertFalse(a.resultado().meta["convergiu"])

    def test_aprendiz_falha_da_ia_perde_so_a_amostra_e_prazo_encerra(self):
        class Lenta(IAFalsa):
            chamadas = 0

            def perguntar(self, *a, **k):
                self.chamadas += 1
                time.sleep(0.05)
                if self.chamadas == 1:
                    raise OSError("tempo esgotado")   # a primeira amostra se perde; as outras seguem
                return super().perguntar(*a, **k)
        subindo = [[linha(0.05, 0.66 - 0.012 * k, 0.95), linha(0.25, 0.67, 0.75), linha(0.3, 0.70, 0.7)] for k in range(10)]
        ia = Lenta()
        a, usadas = self.aprendiz(ia, subindo, prazo_s=0.12)
        self.assertLess(ia.chamadas, 10)                                         # parou no prazo
        self.assertEqual(len(a.nomes), ia.chamadas - 1)                          # a que falhou não conta
        self.assertIsNone(reg.Aprendiz(IAFalsa(), reg.Regioes()).resultado())    # sem amostras: tenta numa próxima rodada

    def test_linha_com_papel_errado_longe_das_outras_nao_estica_a_regiao(self):
        # a IA rotulou duas linhas do HUD (canto de cima) como legenda; a região continua só na faixa de baixo
        certas = [(linha(0.2, 0.62, 0.8), "legenda"), (linha(0.25, 0.65, 0.75), "legenda"), (linha(0.3, 0.68, 0.7), "legenda")]
        erradas = [(linha(0.85, 0.27, 0.95), "legenda"), (linha(0.86, 0.31, 0.97), "legenda")]
        caixa = reg.caixa_dos_papeis([certas + erradas, certas + erradas])["legenda"]["caixa"]
        self.assertTrue(0.5 < caixa[1] < 0.62, caixa)                                       # subiu até as legendas, não até o HUD

    def test_texto_ja_dentro_do_padrao_nao_muda_nada_e_a_regiao_nunca_encolhe(self):
        dentro = [(linha(0.4, 0.80, 0.6), "legenda"), (linha(0.42, 0.83, 0.58), "legenda"), (linha(0.45, 0.86, 0.55), "legenda")]
        self.assertEqual(reg.caixa_dos_papeis([dentro, dentro]), {})   # legendas só no centro não cortam as longas de outras telas

    def test_ia_que_rotula_tudo_como_legenda_nao_leva_a_regiao_para_longe_do_padrao(self):
        # frases de um menu, no meio da tela, rotuladas como legenda: ficam fora (longe do padrão), a região não se mexe
        menu = [(linha(0.1, 0.20 + 0.04 * k, 0.9), "legenda") for k in range(8)]
        self.assertEqual(reg.caixa_dos_papeis([menu, menu, menu]), {})

    def test_com_imagem_tela_de_menu_nao_conta_e_resposta_invalida_e_ignorada(self):
        linhas = [linha(0.1, 0.62, 0.9), linha(0.1, 0.66, 0.9), linha(0.1, 0.7, 0.9)]
        self.assertEqual(set(reg.classificar(IAFalsa("menu"), linhas, "img").values()), {"menu"})
        self.assertEqual(reg.classificar(IAFalsa(None), linhas, "img"), {})
        ia = IAFalsa()
        self.assertEqual(reg.classificar(ia, linhas, "img")[0], "legenda")             # linha 1 do pedido = índice 0
        self.assertEqual(ia.imagens[-1], ["img"])

    def test_linhas_de_texto_contam_so_texto_de_verdade(self):
        leitura = {"quadros": [{"secoes": {"tela": "Uma frase de verdade\n@#!% ;;\nab\nOutra linha boa aqui"}}]}
        self.assertEqual(reg.linhas_de_texto(leitura), 2)
        legenda_sobre_a_cena = {"quadros": [{"secoes": {"tela": "ruido", "legenda": "Aldric: vamos embora\nAntes que escureça\nE chova"}}]}
        self.assertTrue(reg.parece_cena(legenda_sobre_a_cena))   # o OCR da tela inteira não achou a legenda; o do recorte achou
        self.assertFalse(reg.parece_cena({"quadros": [{"secoes": {"tela": "\n".join(["Uma linha de menu longa"] * 25)}}]}))

    def test_regiao_manual_nunca_e_refeita(self):
        atual = reg.Regioes()
        atual.caixas["legenda"] = (0.0, 0.5, 1.0, 0.6)
        atual.meta = {"regioes": {"legenda": {"origem": "manual"}}}
        r = reg.estimar(atual, [self.amostra([linha(0.2, 0.62, 0.8), linha(0.25, 0.66, 0.75), linha(0.3, 0.7, 0.7)])] * 3)
        self.assertEqual(r.caixas["legenda"], (0.0, 0.5, 1.0, 0.6))
        self.assertEqual(r.origem["legenda"], "manual")

    def test_poucas_linhas_ou_caixa_absurda_nao_viram_regiao(self):
        self.assertEqual(reg.caixa_dos_papeis([[(linha(0.2, 0.8), "legenda")], [(linha(0.2, 0.8), "legenda")]]), {})   # 2 linhas só
        espalhadas = [[(linha(0.0, 0.0, 1.0), "legenda"), (linha(0.0, 0.95, 1.0), "legenda"), (linha(0.0, 0.5, 1.0), "legenda")]] * 2
        self.assertNotIn("legenda", reg.caixa_dos_papeis(espalhadas))   # ocuparia a tela toda

    def test_ordem_sorteada_e_a_mesma_para_o_mesmo_jogo_e_muda_entre_jogos(self):
        itens = list(range(40))
        a = reg.ordem_sorteada(itens, "jogo A")
        self.assertEqual(sorted(a), itens)
        self.assertEqual(a, reg.ordem_sorteada(itens, "jogo A"))
        self.assertNotEqual(a, reg.ordem_sorteada(itens, "jogo B"))
        self.assertNotEqual(a, itens)


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
