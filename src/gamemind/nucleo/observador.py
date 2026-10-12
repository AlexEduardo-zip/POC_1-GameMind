"""Observa a pasta de capturas (onde a ferramenta de captura do jogador grava) e avisa quando há mídia nova e pronta.
Por consulta periódica, sem dependência extra: funciona com OneDrive e pastas de rede, onde avisos do sistema falham.
Um arquivo só é dado como pronto quando o tamanho para de mudar entre duas consultas (o clipe pode estar sendo gravado)."""
import threading
from pathlib import Path
from typing import Callable

from .pipeline import tipo_midia


class Observador:
    def __init__(self, pasta: Path, ao_detectar: Callable[[list[Path]], None] | None = None, intervalo_s: float = 10.0,
                 ja_conhecidos: dict[Path, int] | None = None):
        self.pasta, self.ao_detectar, self.intervalo_s = Path(pasta), ao_detectar, intervalo_s
        self._parar = threading.Event()
        self._thread: threading.Thread | None = None
        self._vistos: dict[Path, int] = {Path(p).resolve(): t for p, t in (ja_conhecidos or {}).items()}  # já entregues, com o tamanho
        self._candidatos: dict[Path, int] = {}   # tamanho na consulta anterior

    def consultar(self) -> list[Path]:
        """Uma consulta: devolve os arquivos novos (ou alterados) cujo tamanho se manteve desde a consulta anterior."""
        if not self.pasta.is_dir():
            return []
        atuais = {}
        for p in self.pasta.iterdir():
            if p.is_file() and tipo_midia(p):
                try:
                    atuais[p.resolve()] = p.stat().st_size
                except OSError:
                    continue
        prontos = []
        for p, tam in atuais.items():
            if self._vistos.get(p) == tam:
                continue
            if self._candidatos.get(p) == tam and tam > 0:
                prontos.append(p)
                self._vistos[p] = tam
        self._candidatos = {p: t for p, t in atuais.items() if self._vistos.get(p) != t}
        return sorted(prontos)

    def iniciar(self) -> None:
        self._parar.clear()
        self._thread = threading.Thread(target=self._laco, name="observador", daemon=True)
        self._thread.start()

    def parar(self) -> None:
        self._parar.set()

    @property
    def ativo(self) -> bool:
        return bool(self._thread and self._thread.is_alive() and not self._parar.is_set())

    def _laco(self) -> None:
        while not self._parar.wait(self.intervalo_s):
            prontos = self.consultar()
            if prontos and self.ao_detectar:
                self.ao_detectar(prontos)
