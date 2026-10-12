"""Jogo: tudo o que o GameMind sabe de um jogo, guardado numa pasta própria (`jogos/<nome>/`) com um banco SQLite.
O banco guarda o que é caro de refazer (leitura de cada mídia e resposta do LLM); anotações, grafo e vault são derivados
e podem ser apagados e refeitos a qualquer momento. As mídias não são copiadas: só caminho, tamanho e data."""
import json
import re
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path

from .recursos import pasta_jogos

ESQUEMA_BD = 1
SQL = """
CREATE TABLE IF NOT EXISTS meta (chave TEXT PRIMARY KEY, valor TEXT);
CREATE TABLE IF NOT EXISTS midia (
    id INTEGER PRIMARY KEY,
    caminho TEXT UNIQUE NOT NULL,
    tipo TEXT NOT NULL CHECK (tipo IN ('imagem', 'clipe')),
    tamanho INTEGER NOT NULL,
    capturada_em REAL NOT NULL,          -- data do arquivo: dá a ordem do tempo de jogo
    estado TEXT NOT NULL DEFAULT 'pendente' CHECK (estado IN ('pendente', 'lida', 'erro')),
    erro TEXT NOT NULL DEFAULT '',
    versao_leitura INTEGER NOT NULL DEFAULT 0,
    leitura TEXT,                        -- JSON de leitura.py (texto do OCR, candidatos, quadros)
    tempo_leitura_s REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS llm (
    midia_id INTEGER NOT NULL REFERENCES midia(id) ON DELETE CASCADE,
    backend TEXT NOT NULL,               -- ex.: ollama:qwen2.5:7b; trocar de IA não apaga a resposta da outra
    saida TEXT NOT NULL,
    meta TEXT NOT NULL,
    PRIMARY KEY (midia_id, backend)
);
CREATE TABLE IF NOT EXISTS anotacao (
    midia_id INTEGER PRIMARY KEY REFERENCES midia(id) ON DELETE CASCADE,
    json TEXT NOT NULL                   -- Anotacao (schema.py) depois da consolidação; derivada
);
"""


@dataclass
class Midia:
    id: int
    caminho: str
    tipo: str
    tamanho: int
    capturada_em: float
    estado: str
    erro: str
    versao_leitura: int
    tempo_leitura_s: float

    @property
    def nome(self) -> str:
        return Path(self.caminho).name


def nome_valido(nome: str) -> str:
    n = re.sub(r'[\\/:*?"<>|]', "", nome).strip().strip(".")
    if not n:
        raise ValueError("nome de jogo vazio ou inválido")
    return n


class Jogo:
    """Acesso à pasta e ao banco de um jogo. Seguro para uso em mais de uma thread (uma conexão, com trava)."""

    def __init__(self, pasta: Path):
        self.pasta = Path(pasta)
        self.pasta.mkdir(parents=True, exist_ok=True)
        self._trava = threading.RLock()
        self._bd = sqlite3.connect(self.pasta / "gamemind.db", check_same_thread=False)
        self._bd.execute("PRAGMA foreign_keys = ON")
        self._bd.execute("PRAGMA journal_mode = WAL")
        self._bd.executescript(SQL)
        if self.get("esquema") is None:
            self.set("esquema", ESQUEMA_BD)

    # ---- jogos
    @staticmethod
    def raiz() -> Path:
        return pasta_jogos()

    @classmethod
    def listar(cls) -> list[str]:
        return sorted(p.name for p in cls.raiz().iterdir() if (p / "gamemind.db").exists())

    @classmethod
    def abrir(cls, nome: str) -> "Jogo":
        return cls(cls.raiz() / nome_valido(nome))

    @property
    def nome(self) -> str:
        return self.pasta.name

    def fechar(self) -> None:
        with self._trava:
            self._bd.close()

    # ---- configuração do jogo (pasta observada)
    def get(self, chave: str, padrao=None):
        with self._trava:
            r = self._bd.execute("SELECT valor FROM meta WHERE chave = ?", (chave,)).fetchone()
        return json.loads(r[0]) if r else padrao

    def set(self, chave: str, valor) -> None:
        with self._trava, self._bd:
            self._bd.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (chave, json.dumps(valor, ensure_ascii=False)))

    @property
    def pasta_vault(self) -> Path:
        return self.pasta / "vault"

    @property
    def caminho_grafo(self) -> Path:
        return self.pasta / "grafo.json"

    # ---- mídias
    def registrar(self, caminho: Path, tipo: str) -> bool:
        """Registra a mídia (ou a marca para reler, se o arquivo mudou). Devolve True se é nova ou mudou."""
        caminho = Path(caminho).resolve()
        st = caminho.stat()
        with self._trava, self._bd:
            r = self._bd.execute("SELECT id, tamanho FROM midia WHERE caminho = ?", (str(caminho),)).fetchone()
            if r and r[1] == st.st_size:
                return False
            if r:
                self._bd.execute("UPDATE midia SET tamanho = ?, capturada_em = ?, estado = 'pendente', leitura = NULL WHERE id = ?",
                                 (st.st_size, st.st_mtime, r[0]))
                self._bd.execute("DELETE FROM llm WHERE midia_id = ?", (r[0],))
            else:
                self._bd.execute("INSERT INTO midia (caminho, tipo, tamanho, capturada_em) VALUES (?, ?, ?, ?)",
                                 (str(caminho), tipo, st.st_size, st.st_mtime))
        return True

    def midias(self, estado: str | None = None) -> list[Midia]:
        sql = "SELECT id, caminho, tipo, tamanho, capturada_em, estado, erro, versao_leitura, tempo_leitura_s FROM midia"
        args: tuple = ()
        if estado:
            sql, args = sql + " WHERE estado = ?", (estado,)
        with self._trava:
            linhas = self._bd.execute(sql + " ORDER BY capturada_em, caminho", args).fetchall()
        return [Midia(*l) for l in linhas]

    def remover(self, midia_id: int) -> None:
        with self._trava, self._bd:
            self._bd.execute("DELETE FROM midia WHERE id = ?", (midia_id,))

    def marcar_para_reler(self, versao_atual: int | None = None) -> int:
        """Volta para 'pendente' as mídias com erro ou lidas por uma versão antiga do extrator."""
        with self._trava, self._bd:
            cur = self._bd.execute("UPDATE midia SET estado = 'pendente' WHERE estado = 'erro' OR (? IS NOT NULL AND versao_leitura < ?)",
                                   (versao_atual, versao_atual))
            return cur.rowcount

    def gravar_leitura(self, midia_id: int, leitura: dict, versao: int, tempo_s: float) -> None:
        with self._trava, self._bd:
            self._bd.execute("UPDATE midia SET estado = 'lida', erro = '', leitura = ?, versao_leitura = ?, tempo_leitura_s = ? WHERE id = ?",
                             (json.dumps(leitura, ensure_ascii=False), versao, round(tempo_s, 2), midia_id))
            self._bd.execute("DELETE FROM llm WHERE midia_id = ?", (midia_id,))

    def gravar_erro(self, midia_id: int, erro: str) -> None:
        with self._trava, self._bd:
            self._bd.execute("UPDATE midia SET estado = 'erro', erro = ? WHERE id = ?", (erro[:2000], midia_id))

    def leituras(self) -> list[tuple[Midia, dict]]:
        """Mídias lidas, na ordem do tempo de jogo, com a leitura decodificada."""
        with self._trava:
            linhas = self._bd.execute("SELECT id, leitura FROM midia WHERE estado = 'lida'").fetchall()
        dados = {i: json.loads(l) for i, l in linhas}
        return [(m, dados[m.id]) for m in self.midias("lida")]

    # ---- respostas do LLM
    def llm(self, midia_id: int, backend: str) -> dict | None:
        with self._trava:
            r = self._bd.execute("SELECT saida FROM llm WHERE midia_id = ? AND backend = ?", (midia_id, backend)).fetchone()
        return json.loads(r[0]) if r else None

    def gravar_llm(self, midia_id: int, backend: str, saida: dict, meta: dict) -> None:
        with self._trava, self._bd:
            self._bd.execute("INSERT OR REPLACE INTO llm VALUES (?, ?, ?, ?)",
                             (midia_id, backend, json.dumps(saida, ensure_ascii=False), json.dumps(meta)))

    # ---- anotações (derivadas)
    def gravar_anotacoes(self, anotacoes: dict[int, dict]) -> None:
        with self._trava, self._bd:
            self._bd.execute("DELETE FROM anotacao")
            self._bd.executemany("INSERT INTO anotacao VALUES (?, ?)", [(i, json.dumps(a, ensure_ascii=False)) for i, a in anotacoes.items()])

    def anotacoes(self) -> dict[int, dict]:
        with self._trava:
            return {i: json.loads(j) for i, j in self._bd.execute("SELECT midia_id, json FROM anotacao")}

    def resumo(self) -> dict:
        with self._trava:
            cont = dict(self._bd.execute("SELECT estado, COUNT(*) FROM midia GROUP BY estado").fetchall())
        return {"pendente": cont.get("pendente", 0), "lida": cont.get("lida", 0), "erro": cont.get("erro", 0)}
