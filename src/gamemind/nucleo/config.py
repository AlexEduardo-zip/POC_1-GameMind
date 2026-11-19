"""Configuração global do aplicativo (vale para todos os jogos), gravada em JSON na pasta do usuário."""
import json
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path

from .recursos import pasta_usuario


# o que cada jogo escolhe por conta própria (o resto da configuração vale para todos os jogos)
PREFERENCIAS_DO_JOGO = ("ia", "regioes_por_imagem", "revisar_entidades")


@dataclass
class Config:
    ia: str = ""                  # "" = sem LLM; senão provedor[:modelo] (ollama ou claude-code), ver docs/ia-publica.md
    workers: int = 4              # processos de OCR em paralelo (o OCR usa só a CPU)
    intervalo_video_s: int = 2    # um quadro a cada N segundos (B4: 2 s foi o melhor custo-benefício)
    observar_intervalo_s: int = 10
    idioma_ocr: str = "por+eng"        # idiomas do Tesseract (ex.: por+eng, eng, spa); vale para todos os jogos
    aprender_regioes: bool = False     # opcional: sem modelo de imagem, refina as regiões só com a IA de texto local (menos preciso)
    regioes_por_imagem: bool = True    # na rodada com IA, se há um modelo de imagem no Ollama, aprende as regiões de cada jogo com ele (uma vez)
    modelo_visao: str = ""             # "" = o melhor modelo com visão instalado no Ollama; "nenhum" desliga; ou um nome (ex.: qwen2.5vl:3b)
    aprender_dicionario: bool = True   # False: só os nomes de dicionario_manual.json
    ultimo_jogo: str = ""
    revisar_entidades: bool = True     # na rodada com IA, revisa e resume cada entidade (resumos.py)
    tema: str = "hydra"                # tema da janela (ui/temas.py); só muda a aparência

    @staticmethod
    def caminho() -> Path:
        return pasta_usuario() / "config.json"

    @classmethod
    def carregar(cls) -> "Config":
        try:
            dados = json.loads(cls.caminho().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        validos = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in dados.items() if k in validos})

    def do_jogo(self, jogo) -> "Config":
        """Esta configuração com as escolhas feitas para o jogo (no assistente de novo jogo) por cima: IA, regiões, revisão."""
        return replace(self, **{k: v for k in PREFERENCIAS_DO_JOGO if (v := jogo.get(k)) is not None})

    def salvar(self) -> None:
        self.caminho().write_text(json.dumps(asdict(self), ensure_ascii=False, indent=1), encoding="utf-8")
