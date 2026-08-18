"""Banco da plataforma — SQLite, sem ORM.

Um arquivo, sem servidor pra manter. Enquanto a operação couber num
processo isso é vantagem, não gambiarra: dá pra copiar o banco inteiro
como backup e abrir com qualquer ferramenta.

Convenção: toda data é ISO 8601 em UTC, texto. SQLite não tem tipo de data
e converter na borda evita a confusão de fuso que sempre aparece depois.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from esteira.config import DATA_DIR

BANCO = DATA_DIR / "acerolab.db"

ESQUEMA = """
-- `senha` fica vazia quando a pessoa entrou pelo Google: nesse caso quem
-- guarda a credencial é o Supabase, e aqui só existe o cadastro do produto.
CREATE TABLE IF NOT EXISTS usuarios (
    id            INTEGER PRIMARY KEY,
    email         TEXT NOT NULL UNIQUE COLLATE NOCASE,
    senha         TEXT NOT NULL DEFAULT '',   -- scrypt: sal$hash
    nome          TEXT NOT NULL DEFAULT '',
    supabase_id   TEXT NOT NULL DEFAULT '',   -- uuid do provedor, quando houver
    criado_em     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessoes (
    token       TEXT PRIMARY KEY,
    usuario_id  INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    criada_em   TEXT NOT NULL,
    expira_em   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessoes_usuario ON sessoes(usuario_id);

CREATE TABLE IF NOT EXISTS series (
    id             INTEGER PRIMARY KEY,
    usuario_id     INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    nome           TEXT NOT NULL,
    nicho          TEXT NOT NULL,           -- chave do catálogo ou 'personalizado'
    nicho_texto    TEXT NOT NULL,           -- o prompt de fato usado
    idioma         TEXT NOT NULL DEFAULT 'pt-BR',
    voz            TEXT NOT NULL DEFAULT '',
    musicas        TEXT NOT NULL DEFAULT '[]',   -- json: sorteia uma por vídeo
    estilo         TEXT NOT NULL,
    legenda        TEXT NOT NULL DEFAULT 'traco-forte',
    duracao        TEXT NOT NULL DEFAULT 'curto',
    -- 'imagem' (foto com zoom lento) ou 'video' (clipe gerado). A diferença
    -- de custo é de ~20x por vídeo, por isso o padrão é o barato.
    modo           TEXT NOT NULL DEFAULT 'imagem',
    modelo_video   TEXT NOT NULL DEFAULT 'wan',
    piloto_ativo   INTEGER NOT NULL DEFAULT 0,
    frequencia     TEXT NOT NULL DEFAULT 'semanal',
    proxima_geracao TEXT NOT NULL DEFAULT '',
    criada_em      TEXT NOT NULL,
    arquivada      INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_series_usuario ON series(usuario_id, arquivada);

-- Tema proposto pela série. O cliente lê o título e decide se vira vídeo:
-- é o que evita gerar (e pagar) o que ninguém quis.
CREATE TABLE IF NOT EXISTS temas (
    id          INTEGER PRIMARY KEY,
    serie_id    INTEGER NOT NULL REFERENCES series(id) ON DELETE CASCADE,
    titulo      TEXT NOT NULL,
    gancho      TEXT NOT NULL DEFAULT '',
    estado      TEXT NOT NULL DEFAULT 'proposto',   -- proposto|usado|descartado
    criado_em   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_temas_serie ON temas(serie_id, estado);

CREATE TABLE IF NOT EXISTS videos (
    id            INTEGER PRIMARY KEY,
    serie_id      INTEGER NOT NULL REFERENCES series(id) ON DELETE CASCADE,
    usuario_id    INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    tema_id       INTEGER REFERENCES temas(id) ON DELETE SET NULL,
    titulo        TEXT NOT NULL DEFAULT '',
    estado        TEXT NOT NULL DEFAULT 'na_fila',  -- na_fila|gerando|pronto|falhou
    etapa         TEXT NOT NULL DEFAULT '',         -- o que está rodando agora
    pasta         TEXT NOT NULL DEFAULT '',
    arquivo       TEXT NOT NULL DEFAULT '',
    custo_reais   REAL NOT NULL DEFAULT 0,
    segundos      REAL NOT NULL DEFAULT 0,
    erro          TEXT NOT NULL DEFAULT '',
    criado_em     TEXT NOT NULL,
    terminado_em  TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_videos_usuario ON videos(usuario_id, criado_em);
CREATE INDEX IF NOT EXISTS idx_videos_fila ON videos(estado, criado_em);

-- O Stripe é a fonte da verdade sobre pagamento; esta tabela guarda o que a
-- assinatura LIBERA, que é o que o resto do sistema precisa consultar.
CREATE TABLE IF NOT EXISTS assinaturas (
    id            INTEGER PRIMARY KEY,
    usuario_id    INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    stripe_id     TEXT NOT NULL UNIQUE,
    stripe_cliente TEXT NOT NULL DEFAULT '',   -- para abrir o portal do Stripe
    plano         TEXT NOT NULL,
    series        INTEGER NOT NULL DEFAULT 1,   -- quantas séries o plano cobre
    estado        TEXT NOT NULL DEFAULT 'ativa',-- ativa|vencida|cancelada
    renova_em     TEXT NOT NULL DEFAULT '',
    criada_em     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_assinaturas_usuario ON assinaturas(usuario_id, estado);
"""


def agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def conectar() -> sqlite3.Connection:
    BANCO.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(BANCO, timeout=30, isolation_level=None)
    con.row_factory = sqlite3.Row
    # WAL deixa o worker escrever enquanto a web lê, sem travar um no outro.
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=30000")
    return con


@contextmanager
def aberto() -> Iterator[sqlite3.Connection]:
    con = conectar()
    try:
        yield con
    finally:
        con.close()


# Colunas que nasceram depois do primeiro banco. `CREATE TABLE IF NOT EXISTS`
# não mexe em tabela que já existe, então quem já tinha banco precisa disto.
ACRESCIMOS: tuple[tuple[str, str, str], ...] = (
    ("usuarios", "supabase_id", "TEXT NOT NULL DEFAULT ''"),
    ("assinaturas", "stripe_cliente", "TEXT NOT NULL DEFAULT ''"),
    ("assinaturas", "renova_em", "TEXT NOT NULL DEFAULT ''"),
    ("series", "modo", "TEXT NOT NULL DEFAULT 'imagem'"),
    ("series", "modelo_video", "TEXT NOT NULL DEFAULT 'wan'"),
    ("series", "piloto_ativo", "INTEGER NOT NULL DEFAULT 0"),
    ("series", "frequencia", "TEXT NOT NULL DEFAULT 'semanal'"),
    ("series", "proxima_geracao", "TEXT NOT NULL DEFAULT ''"),
)


def preparar() -> None:
    with aberto() as con:
        con.executescript(ESQUEMA)
        for tabela, coluna, tipo in ACRESCIMOS:
            existentes = {c["name"] for c in con.execute(f"PRAGMA table_info({tabela})")}
            if coluna not in existentes:
                con.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")


# ─────────────────────── ajudantes de leitura ───────────────────────

def um(con: sqlite3.Connection, sql: str, *args: Any) -> sqlite3.Row | None:
    return con.execute(sql, args).fetchone()


def varios(con: sqlite3.Connection, sql: str, *args: Any) -> list[sqlite3.Row]:
    return con.execute(sql, args).fetchall()


def inserir(con: sqlite3.Connection, sql: str, *args: Any) -> int:
    cur = con.execute(sql, args)
    return int(cur.lastrowid or 0)


def lista_json(valor: str | None) -> list[str]:
    if not valor:
        return []
    try:
        dados = json.loads(valor)
    except json.JSONDecodeError:
        return []
    return [str(x) for x in dados] if isinstance(dados, list) else []
