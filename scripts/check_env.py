"""Verifica se as ferramentas da Semana 1 estão instaladas."""
import importlib.util
import shutil
import subprocess
import sys

FERRAMENTAS = {
    "git": ["git", "--version"],
    "tesseract": ["tesseract", "--version"],
    "ollama": ["ollama", "--version"],
    "ffmpeg": ["ffmpeg", "-version"],
}
PACOTES = ["pytesseract", "PIL", "cv2", "pydantic"]


def versao(cmd):
    try:
        saida = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        linha = (saida.stdout or saida.stderr).strip().splitlines()
        return linha[0] if linha else "(sem saída)"
    except Exception as e:  # noqa: BLE001
        return f"erro: {e}"


print(f"Python: {sys.version.split()[0]}\n")
print("Ferramentas externas:")
for nome, cmd in FERRAMENTAS.items():
    if shutil.which(cmd[0]):
        print(f"  [ok] {nome}: {versao(cmd)}")
    else:
        print(f"  [FALTA] {nome}")

print("\nPacotes Python:")
for p in PACOTES:
    ok = importlib.util.find_spec(p) is not None
    print(f"  [{'ok' if ok else 'FALTA'}] {p}")

if shutil.which("tesseract"):
    langs = subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True)
    print("\nIdiomas do Tesseract:", ", ".join(langs.stdout.split()[4:]) or "(nenhum)")
