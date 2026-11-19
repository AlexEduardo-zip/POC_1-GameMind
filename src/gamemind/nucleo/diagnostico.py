"""Verifica o que o aplicativo precisa no computador e diz o que falta, em linguagem de usuário."""
import json
import shutil
import subprocess
import urllib.request
from dataclasses import dataclass

from extracao.ia_publica import APELIDOS, MODELOS_PADRAO, RETIRADOS, ErroConector, criar_backend



@dataclass
class Item:
    nome: str
    ok: bool
    detalhe: str
    obrigatorio: bool = True


def _versao(cmd: list[str]) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return ((r.stdout or r.stderr).strip().splitlines() or ["?"])[0]
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"erro: {e}"


def provedor(ia: str) -> str:
    """Provedor de uma especificação `provedor[:modelo]`; sem prefixo conhecido, é um modelo do Ollama."""
    p = ia.split(":")[0].lower()
    p = APELIDOS.get(p, p)
    return p if p in MODELOS_PADRAO or p in RETIRADOS else "ollama"


def _sem_aviso(_passo: int) -> None:
    pass


def passos_do_teste(ia: str) -> list[str]:
    """Os passos de `testar_ia`, para a janela mostrar o andamento."""
    if provedor(ia) == "ollama":
        return ["Procurando o Ollama no computador", "Carregando o modelo e pedindo uma resposta de teste (a primeira vez demora mais)"]
    return ["Procurando o Claude Code no computador", "Pedindo uma resposta de teste com o seu login (uns 10 s)"]


def testar_ia(ia: str, avisar=_sem_aviso) -> str:
    """Uma chamada real e mínima à IA configurada (texto de tela inventado). Levanta ErroConector/OSError se falhar.
    `avisar(i)`: começou o passo i de `passos_do_teste`."""
    avisar(0)
    if provedor(ia) == "ollama":
        try:
            urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3).close()
        except OSError:
            raise OSError("o Ollama não está aberto: abra o Ollama ou rode `ollama serve`") from None
    b = criar_backend(ia)
    avisar(1)
    saida, meta = b.extrair({"missao": "MISSÃO ATUALIZADA!\nO Campo de Feira\nFale com Lena na estalagem de Vale Claro."},
                            ["missao: O Campo de Feira"])
    ents = ", ".join(f"{e.get('nome')} ({e.get('tipo')})" for e in saida["entidades"]) or "nenhuma"
    return f"{b.nome} respondeu em {meta['tempo_s']} s ({meta['tokens_entrada']}+{meta['tokens_saida']} tokens). Entidades: {ents}"


PASSOS_VERIFICAR = ("OCR (Tesseract)", "Clipes (FFmpeg)", "Modelo de imagem no Ollama", "IA")


def verificar(ia: str = "", idioma: str = "por+eng", avisar=_sem_aviso) -> list[Item]:
    """`avisar(i)`: começou o passo i de PASSOS_VERIFICAR."""
    itens = []
    avisar(0)
    tess = shutil.which("tesseract")
    if not tess:
        itens.append(Item("Tesseract (OCR)", False, "não encontrado no PATH; instale com o idioma do seu jogo"))
    else:
        r = subprocess.run([tess, "--list-langs"], capture_output=True, text=True)
        instalados = (r.stdout + r.stderr).split()
        faltam = [l for l in idioma.split("+") if l and l not in instalados]
        itens.append(Item("Tesseract (OCR)", not faltam, _versao([tess, "--version"]) + (f"; faltam os idiomas {', '.join(faltam)}" if faltam else f"; idiomas {idioma}")))
    avisar(1)
    ff = shutil.which("ffmpeg")
    itens.append(Item("FFmpeg (clipes)", bool(ff), _versao([ff, "-version"]) if ff else "não encontrado: imagens funcionam, clipes dão erro",
                      obrigatorio=False))
    avisar(2)
    from . import visao
    modelos = visao.modelos_de_visao()
    itens.append(Item("Modelo de imagem (Ollama)", bool(modelos),
                      f"{modelos[0]} (aprende as regiões de leitura de cada jogo na rodada com IA)" if modelos else
                      "nenhum instalado: as regiões de leitura ficam as genéricas (opcional: ollama pull qwen2.5vl:7b)", obrigatorio=False))
    avisar(3)
    if not ia:
        itens.append(Item("IA", True, "desligada: o grafo sai do OCR e dos nomes aprendidos (sem relações, criaturas, itens e missões)", obrigatorio=False))
    elif provedor(ia) == "ollama":
        try:
            with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3) as r:
                modelos = [m["name"] for m in json.load(r).get("models", [])]
            itens.append(Item("Ollama", True, "em execução; modelos: " + (", ".join(modelos) or "nenhum (rode `ollama pull`)"), obrigatorio=False))
        except OSError:
            itens.append(Item("Ollama", False, "não está em execução: abra o Ollama ou rode `ollama serve`", obrigatorio=False))
    else:
        try:
            b = criar_backend(ia)
            itens.append(Item("IA", True, f"{b.nome} em {getattr(b, 'exe', '')} (o teste de conexão faz uma chamada real com o seu login)", obrigatorio=False))
        except ErroConector as e:
            itens.append(Item("IA", False, str(e), obrigatorio=False))
    return itens
