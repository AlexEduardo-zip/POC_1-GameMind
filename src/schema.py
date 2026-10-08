"""Esquema do GameMind, versão 1.1 da ontologia (ver docs/ontologia.md).
Usado no gabarito e, depois, como formato de saída da extração."""
from typing import Literal

from pydantic import BaseModel, Field

TipoEntidade = Literal["personagem", "criatura", "local", "missao", "item", "evento", "decisao", "faccao"]
Predicado = Literal[
    "participa_de",   # personagem/criatura -> missão/evento
    "ocorre_em",      # missão/evento -> local
    "localizado_em",  # personagem/criatura/item -> local
    "parte_de",       # local -> local; missão -> missão; decisão/evento -> missão
    "concede",        # personagem -> missão
    "obtido_em",      # item -> missão/evento
    "gera",           # decisão/evento -> evento
    "membro_de",      # personagem/criatura -> facção
    "relacionado_a",  # personagem/criatura -> personagem/criatura (usar `rotulo`)
]
SIMETRICOS = {"relacionado_a"}  # relações sem direção: (A, B) e (B, A) são a mesma
TipoTela = Literal["dialogo", "escolhas", "diario", "item", "mapa", "glossario", "hud", "cutscene", "outro"]


class Entidade(BaseModel):
    nome: str
    tipo: TipoEntidade
    subtipo: str = ""    # opcional, não avaliado (ex.: principal, secundaria, contrato, ingrediente)
    estado: str = ""     # opcional, só para missão (ativa, disponivel, concluida, falhou)
    evidencia: str = ""  # trecho visível na tela que justifica a anotação


class Relacao(BaseModel):
    sujeito: str
    predicado: Predicado
    objeto: str
    rotulo: str = ""     # opcional, não avaliado (ex.: "ex-amante" em relacionado_a)
    evidencia: str = ""


class Anotacao(BaseModel):
    arquivo: str                      # nome do screenshot ou vídeo
    tipo_tela: TipoTela
    entidades: list[Entidade] = Field(default_factory=list)
    relacoes: list[Relacao] = Field(default_factory=list)
    observacoes: str = ""
