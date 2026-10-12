"""Configuração global do aplicativo (vale para todos os jogos), gravada em JSON na pasta do usuário."""
import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from .recursos import pasta_usuario


@dataclass
class Config:
    ia: str = ""                  # "" = sem LLM; senão provedor[:modelo] (ollama, openai, gemini, claude, claude-code), ver docs/ia-publica.md
    workers: int = 4              # processos de OCR em paralelo (o OCR usa só a CPU)
    intervalo_video_s: int = 2    # um quadro a cada N segundos (B4: 2 s foi o melhor custo-benefício)
    observar_intervalo_s: int = 10
    idioma_ocr: str = "por+eng"        # idiomas do Tesseract (ex.: por+eng, eng, spa); vale para todos os jogos
    aprender_regioes: bool = False     # opcional: com IA local, refina as regiões de leitura do jogo (regioes.json); por padrão ficam as genéricas
    aprender_dicionario: bool = True   # False: só os nomes de dicionario_manual.json
    ultimo_jogo: str = ""

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

    def salvar(self) -> None:
        self.caminho().write_text(json.dumps(asdict(self), ensure_ascii=False, indent=1), encoding="utf-8")
