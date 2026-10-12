"""Testes offline do conector de IA pública: pedido montado e resposta lida para cada provedor (HTTP simulado, sem chave nem rede).
Uso: python -m unittest discover -s tests -v"""
import io
import json
import os
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from extracao import ia_publica as ip  # noqa: E402
from extracao.llm import OllamaBackend  # noqa: E402

SAIDA = {"entidades": [{"nome": "Lena", "tipo": "personagem"}], "relacoes": []}
SECOES = {"missao": "Fale com Lena."}


class Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


def resp(obj):
    return Resp(json.dumps(obj).encode())


class TestConector(unittest.TestCase):
    def setUp(self):
        for v in ("OPENAI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "ANTHROPIC_API_KEY", "CLAUDE_API_KEY"):
            os.environ.pop(v, None)
        self.env = mock.patch.object(ip, "carregar_env")
        self.env.start()
        self.addCleanup(self.env.stop)

    def chamar(self, backend, retorno):
        with mock.patch("urllib.request.urlopen", return_value=resp(retorno)) as u:
            saida, meta = backend.extrair(SECOES, ["missao: X"])
        return saida, meta, u.call_args[0][0]

    def test_openai(self):
        os.environ["OPENAI_API_KEY"] = "k"
        b = ip.criar_backend("codex:gpt-x")
        saida, meta, req = self.chamar(b, {"choices": [{"message": {"content": json.dumps(SAIDA)}}], "usage": {"prompt_tokens": 7, "completion_tokens": 3}})
        corpo = json.loads(req.data)
        self.assertEqual(saida, SAIDA)
        self.assertEqual((meta["tokens_entrada"], meta["tokens_saida"]), (7, 3))
        self.assertTrue(req.full_url.endswith("/v1/chat/completions"))
        self.assertEqual(req.get_header("Authorization"), "Bearer k")
        esq = corpo["response_format"]["json_schema"]["schema"]
        self.assertFalse(esq["additionalProperties"])
        self.assertEqual(esq["properties"]["entidades"]["items"]["required"], ["nome", "tipo"])

    def test_gemini(self):
        os.environ["GOOGLE_API_KEY"] = "g"
        b = ip.criar_backend("google")
        self.assertEqual(b.nome, "gemini:gemini-2.5-flash")
        saida, meta, req = self.chamar(b, {"candidates": [{"content": {"parts": [{"text": json.dumps(SAIDA)}]}}],
                                           "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 2}})
        corpo = json.loads(req.data)
        self.assertEqual(saida, SAIDA)
        self.assertEqual(meta["tokens_entrada"], 5)
        self.assertIn("gemini-2.5-flash:generateContent", req.full_url)
        self.assertEqual(req.get_header("X-goog-api-key"), "g")
        esq = corpo["generationConfig"]["responseSchema"]
        self.assertEqual(esq["type"], "OBJECT")
        self.assertNotIn("additionalProperties", json.dumps(esq))

    def test_claude(self):
        os.environ["ANTHROPIC_API_KEY"] = "c"
        b = ip.criar_backend("anthropic")
        saida, meta, req = self.chamar(b, {"content": [{"type": "tool_use", "input": SAIDA}], "usage": {"input_tokens": 9, "output_tokens": 4}})
        corpo = json.loads(req.data)
        self.assertEqual(saida, SAIDA)
        self.assertEqual(corpo["tool_choice"]["name"], "registrar_extracao")
        self.assertEqual(req.get_header("X-api-key"), "c")
        self.assertEqual(req.get_header("Anthropic-version"), "2023-06-01")

    def test_resposta_invalida_vira_vazio(self):
        os.environ["OPENAI_API_KEY"] = "k"
        saida, _, _ = self.chamar(ip.criar_backend("openai"), {"choices": [{"message": {"content": "não é json"}}]})
        self.assertEqual(saida, {"entidades": [], "relacoes": []})

    def test_sem_chave(self):
        with self.assertRaises(ip.ErroConector) as c:
            ip.criar_backend("gemini")
        self.assertIn("GEMINI_API_KEY", str(c.exception))

    def test_erro_http_claro(self):
        os.environ["ANTHROPIC_API_KEY"] = "c"
        erro = urllib.error.HTTPError("u", 401, "x", {}, io.BytesIO(b"invalid key"))
        with mock.patch("urllib.request.urlopen", side_effect=erro):
            with self.assertRaises(ip.ErroConector) as c:
                ip.criar_backend("claude").extrair(SECOES, [])
        self.assertIn("chave inválida", str(c.exception))

    def test_repete_em_429(self):
        os.environ["OPENAI_API_KEY"] = "k"
        limite = urllib.error.HTTPError("u", 429, "x", {"Retry-After": "0"}, io.BytesIO(b""))
        ok = resp({"choices": [{"message": {"content": json.dumps(SAIDA)}}]})
        with mock.patch("urllib.request.urlopen", side_effect=[limite, ok]), mock.patch("time.sleep"):
            saida, _ = ip.criar_backend("openai").extrair(SECOES, [])
        self.assertEqual(saida, SAIDA)

    def test_ollama_e_compatibilidade(self):
        self.assertIsInstance(ip.criar_backend("qwen2.5:7b"), OllamaBackend)
        self.assertEqual(ip.criar_backend("ollama").modelo, "qwen2.5:7b")
        self.assertEqual(ip.criar_backend("ollama:qwen2.5:3b").modelo, "qwen2.5:3b")

    def test_claude_code(self):
        b = ip.criar_backend("claudecode")
        self.assertEqual(b.nome, "claude-code:haiku")
        b.exe = "claude"
        d = {"is_error": False, "structured_output": SAIDA, "usage": {"input_tokens": 10, "output_tokens": 5}, "duration_api_ms": 1500}
        feito = mock.Mock(returncode=0, stdout=json.dumps(d), stderr="")
        with mock.patch("subprocess.run", return_value=feito) as run:
            saida, meta = b.extrair(SECOES, [])
        self.assertEqual(saida, {**SAIDA})
        self.assertEqual((meta["tokens_entrada"], meta["tempo_geracao_s"]), (10, 1.5))
        self.assertIn("--json-schema", run.call_args[0][0])
        erro = mock.Mock(returncode=1, stdout=json.dumps({"is_error": True, "result": "Not logged in"}), stderr="")
        with mock.patch("subprocess.run", return_value=erro):
            with self.assertRaises(ip.ErroConector) as c:
                b.extrair(SECOES, [])
        self.assertIn("login", str(c.exception))


if __name__ == "__main__":
    unittest.main()
