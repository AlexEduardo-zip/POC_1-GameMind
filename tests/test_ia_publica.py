"""Testes offline do conector de IA fora do computador (Claude Code com o login da assinatura): pedido montado e resposta lida
(processo simulado, sem login nem rede), as IAs retiradas e a escolha do Ollama.
Uso: python -m unittest discover -s tests -v"""
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from extracao import ia_publica as ip  # noqa: E402
from extracao.llm import OllamaBackend  # noqa: E402

SAIDA = {"entidades": [{"nome": "Lena", "tipo": "personagem"}], "relacoes": []}
SECOES = {"missao": "Fale com Lena."}


def claude():
    with mock.patch.object(ip, "achar_claude", return_value="claude"):
        return ip.criar_backend("claude-code")


def feito(d, codigo=0):
    return mock.Mock(returncode=codigo, stdout=json.dumps(d), stderr="")


class TestConector(unittest.TestCase):
    def test_ollama_e_compatibilidade(self):
        self.assertIsInstance(ip.criar_backend("qwen2.5:7b"), OllamaBackend)
        self.assertEqual(ip.criar_backend("ollama").modelo, "qwen2.5:7b")
        self.assertEqual(ip.criar_backend("ollama:qwen2.5:3b").modelo, "qwen2.5:3b")

    def test_ias_por_chave_foram_retiradas(self):
        for spec in ("openai", "gemini:gemini-2.5-flash", "chatgpt"):
            with self.assertRaises(ip.ErroConector) as c:
                ip.criar_backend(spec)
            self.assertIn("Configurar jogo", str(c.exception))
        with mock.patch.object(ip, "achar_claude", return_value="claude"):
            self.assertEqual(ip.criar_backend("claude").nome, "claude-code:haiku")   # "claude" agora é o login

    def test_extrair(self):
        b = claude()
        d = {"is_error": False, "structured_output": SAIDA, "usage": {"input_tokens": 10, "output_tokens": 5}, "duration_api_ms": 1500}
        with mock.patch("subprocess.run", return_value=feito(d)) as run:
            saida, meta = b.extrair(SECOES, [])
        self.assertEqual(saida, SAIDA)
        self.assertEqual((meta["tokens_entrada"], meta["tempo_geracao_s"]), (10, 1.5))
        cmd = run.call_args[0][0]
        self.assertIn("--json-schema", cmd)
        self.assertEqual(cmd[cmd.index("--tools") + 1], "")                       # sem ferramentas: só responde

    def test_perguntar_so_com_texto(self):
        b = claude()
        esquema = {"type": "object", "properties": {"entidades": {"type": "array"}}}
        with mock.patch("subprocess.run", return_value=feito({"structured_output": {"entidades": []}})) as run:
            self.assertEqual(b.perguntar("instr", "pedido", esquema), {"entidades": []})
        self.assertEqual(json.loads(run.call_args[0][0][run.call_args[0][0].index("--json-schema") + 1]), esquema)
        with self.assertRaises(NotImplementedError):                              # imagens não saem do computador
            b.perguntar("instr", "pedido", esquema, imagens=["abc"])

    def test_sem_login_diz_o_que_fazer(self):
        b = claude()
        with mock.patch("subprocess.run", return_value=feito({"is_error": True, "result": "Not logged in"}, 1)):
            with self.assertRaises(ip.ErroConector) as c:
                b.extrair(SECOES, [])
        self.assertIn("Entrar com a conta Claude", str(c.exception))


if __name__ == "__main__":
    unittest.main()
