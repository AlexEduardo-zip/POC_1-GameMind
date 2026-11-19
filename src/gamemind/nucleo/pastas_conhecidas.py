"""Pastas onde as ferramentas de captura mais comuns gravam (Steam, NVIDIA, AMD Adrenalin, Xbox Game Bar), para sugerir e para
abrir o seletor de pasta já no lugar certo. Só procura caminhos padrão dessas ferramentas; nada de um jogo específico. As pastas
de captura da Steam são uma por jogo (userdata/<conta>/760/remote/<id do jogo>/screenshots): a mais recente vem primeiro."""
import os
import re
from difflib import SequenceMatcher
from pathlib import Path

PASTAS_VIDEO = (("AMD Adrenalin", "Radeon ReLive"), ("AMD Adrenalin", "AMD"), ("NVIDIA", "NVIDIA"), ("NVIDIA ShadowPlay", "ShadowPlay"),
                ("Xbox Game Bar", "Captures"))
PASTAS_IMAGEM = (("Capturas de tela", "Screenshots"),)


def _raizes_steam() -> list[Path]:
    raizes = [Path(os.environ.get(v, "")) / "Steam" for v in ("ProgramFiles(x86)", "ProgramFiles") if os.environ.get(v)]
    raizes += [Path.home() / ".steam" / "steam", Path.home() / ".local" / "share" / "Steam"]
    try:   # onde a Steam está instalada, se não for no lugar padrão
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
            raizes.insert(0, Path(winreg.QueryValueEx(k, "SteamPath")[0]))
    except (ImportError, OSError):
        pass
    return list(dict.fromkeys(raizes))


def _recente(p: Path) -> float:
    try:
        return p.stat().st_mtime
    except OSError:
        return 0.0


def capturas_steam(raizes: list[Path] | None = None) -> list[Path]:
    """Pastas de captura da Steam (uma por jogo), da usada mais recentemente para a menos."""
    pastas = {p for r in (raizes if raizes is not None else _raizes_steam()) if r.is_dir()
              for p in r.glob("userdata/*/760/remote/*/screenshots") if p.is_dir()}
    return sorted(pastas, key=_recente, reverse=True)


def nome_steam(pasta: Path) -> str:
    """O nome do jogo de uma pasta de capturas da Steam (.../userdata/<conta>/760/remote/<id>/screenshots), pelo manifesto que
    a própria Steam guarda de cada jogo instalado (steamapps/appmanifest_<id>.acf). "" se o jogo não está instalado."""
    try:
        appid, raiz = pasta.parent.name, pasta.parents[5]
    except IndexError:
        return ""
    bibliotecas = [raiz / "steamapps"]
    vdf = raiz / "steamapps" / "libraryfolders.vdf"
    if vdf.exists():
        bibliotecas += [Path(m) / "steamapps" for m in re.findall(r'"path"\s+"([^"]+)"', vdf.read_text(encoding="utf-8", errors="ignore"))]
    for b in bibliotecas:
        acf = b / f"appmanifest_{appid}.acf"
        if acf.exists():
            m = re.search(r'"name"\s+"([^"]+)"', acf.read_text(encoding="utf-8", errors="ignore"))
            if m:
                return m.group(1).replace("\\\\", "\\")
    return ""


def _pessoais(casa: Path, inglesa: str, portuguesa: str) -> list[Path]:
    """A pasta pessoal (Imagens ou Vídeos), também a do OneDrive, onde o Windows costuma redirecioná-la."""
    return [casa / inglesa, casa / "OneDrive" / inglesa, casa / "OneDrive" / portuguesa]


def sugestoes(casa: Path | None = None, raizes_steam: list[Path] | None = None) -> dict[str, list[tuple[str, Path]]]:
    """{"screenshots": [(origem, pasta)], "videos": [(origem, pasta)]}: só as que existem, das mais prováveis para as menos."""
    casa = casa or Path.home()
    imagens = [(f"Steam · {nome_steam(p) or p.parent.name}", p) for p in capturas_steam(raizes_steam)]
    imagens += [(rotulo, b / nome) for b in _pessoais(casa, "Pictures", "Imagens") for rotulo, nome in PASTAS_IMAGEM]
    videos = [(rotulo, b / nome) for b in _pessoais(casa, "Videos", "Vídeos") for rotulo, nome in PASTAS_VIDEO]
    videos.sort(key=lambda s: _recente(s[1]), reverse=True)
    return {"screenshots": [(r, p) for r, p in imagens if p.is_dir()], "videos": [(r, p) for r, p in videos if p.is_dir()]}


def inicio(tipo: str, casa: Path | None = None, raizes_steam: list[Path] | None = None) -> Path:
    """Onde abrir o seletor de pasta: a sugestão mais provável; sem nenhuma, a pasta de Imagens ou de Vídeos do usuário."""
    casa = casa or Path.home()
    achadas = sugestoes(casa, raizes_steam)[tipo]
    if achadas:
        return achadas[0][1]
    pessoais = _pessoais(casa, "Pictures", "Imagens") if tipo == "screenshots" else _pessoais(casa, "Videos", "Vídeos")
    return next((p for p in pessoais if p.is_dir()), casa)


def do_jogo(nome: str, casa: Path | None = None, raizes_steam: list[Path] | None = None) -> Path | None:
    """A pasta de capturas da Steam do jogo com esse nome (ou parecido o bastante), se houver."""
    alvo = re.sub(r"[^a-z0-9]", "", nome.lower())
    for p in capturas_steam(raizes_steam):
        n = re.sub(r"[^a-z0-9]", "", nome_steam(p).lower())
        if n and alvo and (alvo in n or n in alvo or SequenceMatcher(None, alvo, n).ratio() >= 0.75):
            return p
    return None


__all__ = ["sugestoes", "inicio", "capturas_steam", "nome_steam", "do_jogo"]
