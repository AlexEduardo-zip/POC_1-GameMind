"""Jogos instalados no computador, para sugerir no assistente de novo jogo (opcional). Em vez de varrer o disco atrás de .exe
(lento), lê o que os próprios launchers registram: Steam (steamapps/appmanifest_*.acf), Epic (manifestos em ProgramData) e GOG
(registro do Windows). O .exe principal é procurado só dentro da pasta de cada jogo, com limite de profundidade e de tempo."""
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from .pastas_conhecidas import _raizes_steam

log = logging.getLogger("gamemind")
PROFUNDIDADE = 3          # pastas abaixo da do jogo onde o .exe principal é procurado
MAX_ARQUIVOS = 3000       # por jogo
# executáveis que não são o jogo (instaladores, dependências, relatórios de erro, anticheat)
NAO_E_O_JOGO = re.compile(r"unins|setup|install|redist|vcredist|vc_redist|dxsetup|directx|dotnet|crash|report|easyanticheat|"
                          r"battleye|anticheat|launcherhelper|helper|updater|update|cefprocess|webhelper|ue4prereq|prereq|touchup|"
                          r"cleanup|unitycrash|overlay|benchmark|server|console|editor|tools?\b|shader|compiler|"
                          r"start_protected|protected_game", re.I)
# o que a Steam instala mas não é jogo
NAO_E_JOGO_STEAM = re.compile(r"redistributable|steamworks|proton|steam linux runtime|sdk|dedicated server|soundtrack", re.I)


@dataclass
class Instalado:
    nome: str
    pasta: Path
    executavel: Path | None
    origem: str


def executavel_principal(pasta: Path, nome: str = "") -> Path | None:
    """O .exe do jogo dentro da pasta dele: fora instaladores e afins, o de nome mais parecido com o do jogo (ou da pasta) e,
    no empate, o maior."""
    alvo = re.sub(r"[^a-z0-9]", "", (nome or pasta.name).lower())
    achados, vistos = [], 0
    for raiz, dirs, arquivos in os.walk(pasta):
        if len(Path(raiz).relative_to(pasta).parts) >= PROFUNDIDADE:
            dirs[:] = []
        for a in arquivos:
            vistos += 1
            if a.lower().endswith(".exe") and not NAO_E_O_JOGO.search(a):
                p = Path(raiz) / a
                parecido = SequenceMatcher(None, alvo, re.sub(r"[^a-z0-9]", "", p.stem.lower())).ratio()
                try:
                    achados.append((round(parecido, 1), p.stat().st_size, p))
                except OSError:
                    pass
        if vistos > MAX_ARQUIVOS:
            break
    return max(achados)[2] if achados else None


def _steam(raizes: list[Path]) -> list[tuple[str, Path, str]]:
    bibliotecas = []
    for raiz in raizes:
        bibliotecas.append(raiz / "steamapps")
        vdf = raiz / "steamapps" / "libraryfolders.vdf"
        if vdf.exists():
            bibliotecas += [Path(m.replace("\\\\", "\\")) / "steamapps"
                            for m in re.findall(r'"path"\s+"([^"]+)"', vdf.read_text(encoding="utf-8", errors="ignore"))]
    jogos = []
    for b in dict.fromkeys(bibliotecas):
        for acf in b.glob("appmanifest_*.acf") if b.is_dir() else []:
            texto = acf.read_text(encoding="utf-8", errors="ignore")
            nome, pasta = re.search(r'"name"\s+"([^"]+)"', texto), re.search(r'"installdir"\s+"([^"]+)"', texto)
            if nome and pasta and not NAO_E_JOGO_STEAM.search(nome.group(1)):
                jogos.append((nome.group(1), b / "common" / pasta.group(1), "Steam"))
    return jogos


def _epic(pasta: Path) -> list[tuple[str, Path, str]]:
    jogos = []
    for item in pasta.glob("*.item") if pasta.is_dir() else []:
        try:
            d = json.loads(item.read_text(encoding="utf-8", errors="ignore"))
        except ValueError:
            continue
        if d.get("DisplayName") and d.get("InstallLocation") and not d.get("bIsIncompleteInstall"):
            jogos.append((d["DisplayName"], Path(d["InstallLocation"]), "Epic Games"))
    return jogos


def _gog() -> list[tuple[str, Path, str]]:
    jogos = []
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\GOG.com\Games") as k:
            for i in range(winreg.QueryInfoKey(k)[0]):
                with winreg.OpenKey(k, winreg.EnumKey(k, i)) as g:
                    jogos.append((winreg.QueryValueEx(g, "gameName")[0], Path(winreg.QueryValueEx(g, "path")[0]), "GOG"))
    except (ImportError, OSError):
        pass
    return jogos


def listar(prazo_s: float = 15.0, raizes_steam: list[Path] | None = None, pasta_epic: Path | None = None) -> list[Instalado]:
    """Os jogos instalados, em ordem alfabética. Passado o prazo, os que faltam vêm sem o .exe (o usuário pode escolher)."""
    t0 = time.monotonic()
    pasta_epic = pasta_epic or Path(os.environ.get("ProgramData", "C:/ProgramData")) / "Epic" / "EpicGamesLauncher" / "Data" / "Manifests"
    registrados = _steam(raizes_steam if raizes_steam is not None else _raizes_steam()) + _epic(pasta_epic)
    registrados += _gog() if raizes_steam is None else []
    saida, vistos = [], set()
    for nome, pasta, origem in sorted(registrados, key=lambda j: j[0].lower()):
        if not pasta.is_dir() or pasta in vistos:
            continue
        vistos.add(pasta)
        exe = executavel_principal(pasta, nome) if time.monotonic() - t0 < prazo_s else None
        saida.append(Instalado(nome, pasta, exe, origem))
    log.info("%d jogo(s) instalado(s) encontrado(s) em %.1f s", len(saida), time.monotonic() - t0)
    return saida


__all__ = ["Instalado", "listar", "executavel_principal"]
