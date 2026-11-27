# -*- coding: utf-8 -*-
"""Conexão SQLite (local) ou PostgreSQL/Supabase (Render) via DATABASE_URL."""
from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent / ".env")
except Exception:
    pass

try:
    import psycopg2
    import psycopg2.extras
    from psycopg2 import IntegrityError as PgIntegrityError
except ImportError:  # ambiente local sem Postgres
    psycopg2 = None
    PgIntegrityError = None

RAIZ = Path(__file__).resolve().parent
ARQUIVO_SQLITE = RAIZ / "banco" / "gcpd.sqlite"

IntegrityError = (sqlite3.IntegrityError,) + ((PgIntegrityError,) if PgIntegrityError else ())
ErroBanco = (sqlite3.Error,) + ((psycopg2.Error,) if psycopg2 else ())


def database_url():
    return (os.environ.get("DATABASE_URL") or "").strip()


def usar_postgres():
    return bool(database_url())


def _dsn_postgres():
    url = database_url()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    partes = urlparse(url)
    query = dict(parse_qsl(partes.query, keep_blank_values=True))
    query.setdefault("sslmode", "require")
    return urlunparse(partes._replace(query=urlencode(query)))


def _sql_pg(sql):
    texto = str(sql or "").strip()
    if not texto:
        return texto
    # INSERT OR IGNORE → ON CONFLICT DO NOTHING
    if re.match(r"INSERT\s+OR\s+IGNORE\s+INTO", texto, flags=re.IGNORECASE):
        texto = re.sub(
            r"INSERT\s+OR\s+IGNORE\s+INTO",
            "INSERT INTO",
            texto,
            count=1,
            flags=re.IGNORECASE,
        )
        if "ON CONFLICT" not in texto.upper():
            texto = texto.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
    # json_extract(col, '$.campo') → (col::jsonb->>'campo')
    texto = re.sub(
        r"json_extract\s*\(\s*([^,]+?)\s*,\s*'\$\.([^']+)'\s*\)",
        r"(\1::jsonb->>'\2')",
        texto,
        flags=re.IGNORECASE,
    )
    texto = texto.replace("COLLATE NOCASE", "")
    texto = re.sub(r"ON CONFLICT\((\w+)\)", r"ON CONFLICT (\1)", texto, flags=re.IGNORECASE)
    # placeholders posicionais
    texto = re.sub(r"\?", "%s", texto)
    return texto


class _PgCursorResult:
    def __init__(self, cursor, lastrowid=None, rowcount=None):
        self._cursor = cursor
        self.lastrowid = lastrowid
        self.rowcount = cursor.rowcount if rowcount is None else rowcount

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def __iter__(self):
        return iter(self._cursor)


class _PgConnection:
    def __init__(self, dsn):
        if psycopg2 is None:
            raise RuntimeError(
                "psycopg2 não instalado. Inclua psycopg2-binary no requirements.txt."
            )
        self._conn = psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)

    def execute(self, sql, params=None):
        sql_pg = _sql_pg(sql)
        upper = sql_pg.lstrip().upper()
        # Só pede RETURNING id em INSERT simples (sem upsert); tabelas sem coluna id
        # (ex.: tipo_processo_assunto) usam ON CONFLICT e não precisam de lastrowid.
        precisa_id = (
            upper.startswith("INSERT INTO")
            and "RETURNING" not in upper
            and "ON CONFLICT" not in upper
        )
        if precisa_id:
            sql_pg = sql_pg.rstrip().rstrip(";") + " RETURNING id"
        cur = self._conn.cursor()
        cur.execute(sql_pg, tuple(params) if params is not None else None)
        lastrowid = None
        rowcount = cur.rowcount
        if precisa_id and cur.description:
            row = cur.fetchone()
            if row:
                lastrowid = row["id"] if isinstance(row, dict) else row[0]
                # Já consumimos o RETURNING; devolve cursor vazio e lastrowid preenchido.
                cur = self._conn.cursor()
                rowcount = 1
        return _PgCursorResult(cur, lastrowid=lastrowid, rowcount=rowcount)

    def executemany(self, sql, seq_of_params):
        sql_pg = _sql_pg(sql)
        cur = self._conn.cursor()
        cur.executemany(sql_pg, list(seq_of_params))
        return _PgCursorResult(cur, lastrowid=None)

    def executescript(self, script):
        # Divide por ; em nível simples (nossos schemas não têm funções com ; interno).
        partes = [p.strip() for p in str(script or "").split(";") if p.strip()]
        cur = self._conn.cursor()
        for parte in partes:
            cur.execute(_sql_pg(parte))
        return _PgCursorResult(cur)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                self._conn.commit()
            else:
                self._conn.rollback()
        finally:
            self._conn.close()
        return False


def conectar():
    if usar_postgres():
        try:
            return _PgConnection(_dsn_postgres())
        except Exception as erro:
            raise RuntimeError(
                "Falha ao conectar no Postgres (DATABASE_URL). "
                "No Supabase: Project Settings → Database → URI (pooler ou direct). "
                "No Render: Environment → DATABASE_URL com a mesma string. "
                f"Detalhe: {erro}"
            ) from erro
    ARQUIVO_SQLITE.parent.mkdir(exist_ok=True)
    conexao = sqlite3.connect(ARQUIVO_SQLITE)
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON")
    return conexao
