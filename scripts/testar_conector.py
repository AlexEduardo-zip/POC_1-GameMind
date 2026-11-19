"""Testa a IA com uma chamada real e minúscula (um texto de tela inventado).
Uso: python scripts/testar_conector.py claude-code       (ou ollama, ou provedor:modelo)
     python scripts/testar_conector.py todos             (Ollama e Claude Code)
O Claude Code usa o login da sua assinatura e desconta da cota do plano. Veja docs/ia-publica.md."""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))
from extracao.ia_publica import MODELOS_PADRAO, ErroConector, criar_backend  # noqa: E402

SECOES = {"missao": "MISSÃO ATUALIZADA!\nO Campo de Feira\nFale com Lena na estalagem de Vale Claro."}
DETECTADO = ["missao: O Campo de Feira"]


def testar(spec: str) -> bool:
    try:
        b = criar_backend(spec)
        saida, meta = b.extrair(SECOES, DETECTADO)
    except (ErroConector, OSError) as e:
        print(f"FALHOU  {spec}: {e}")
        return False
    print(f"OK      {b.nome}: {meta['tempo_s']}s, {meta['tokens_entrada']} tokens de entrada, {meta['tokens_saida']} de saída")
    print(f"        entidades: {[(e['nome'], e['tipo']) for e in saida['entidades']]}")
    print(f"        relações:  {[(r['sujeito'], r['predicado'], r['objeto']) for r in saida['relacoes']]}")
    return True


if __name__ == "__main__":
    alvo = sys.argv[1] if len(sys.argv) > 1 else "todos"
    specs = list(MODELOS_PADRAO) if alvo == "todos" else [alvo]
    sys.exit(0 if all([testar(s) for s in specs]) else 1)
