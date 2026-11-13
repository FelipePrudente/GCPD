# -*- coding: utf-8 -*-
"""Migra dados do SQLite antigo para o Supabase (PostgreSQL) em lotes."""
import sqlite3
import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

load_dotenv()

SQLITE_PATH = Path("banco/gcpd.sqlite")
DATABASE_URL = os.getenv("DATABASE_URL")

if not SQLITE_PATH.exists():
    raise SystemExit(f"Arquivo SQLite não encontrado: {SQLITE_PATH}")

if not DATABASE_URL:
    raise SystemExit("Defina DATABASE_URL no .env")

def migrar():
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row
    pg_conn = None
    try:
        pg_conn = psycopg2.connect(DATABASE_URL)
        pg_conn.autocommit = False
        # Aumenta o timeout da sessão
        with pg_conn.cursor() as cur:
            cur.execute("SET statement_timeout = '120s'")

        def inserir_lote(sql, dados, descricao):
            if not dados:
                print(f"{descricao}: nada para migrar.")
                return
            print(f"{descricao}: {len(dados)} registros...")
            with pg_conn.cursor() as cur:
                for i in range(0, len(dados), 50):
                    lote = dados[i:i+50]
                    cur.executemany(sql, lote)
                    pg_conn.commit()
                    print(f"  → {min(i+50, len(dados))}/{len(dados)}")

        # Assuntos
        assuntos = [(r["nome"], r["id_sei"]) for r in sqlite_conn.execute("SELECT nome, id_sei FROM assunto_sei")]
        inserir_lote(
            "INSERT INTO assunto_sei (nome, id_sei) VALUES (%s, %s) ON CONFLICT (nome) DO NOTHING",
            assuntos,
            "Assuntos"
        )

        # Tipos de processo
        tipos_proc = [(r["nome"], r["id_sei"]) for r in sqlite_conn.execute("SELECT nome, id_sei FROM tipo_processo_sei")]
        inserir_lote(
            "INSERT INTO tipo_processo_sei (nome, id_sei) VALUES (%s, %s) ON CONFLICT (nome) DO NOTHING",
            tipos_proc,
            "Tipos de processo"
        )

        # Tipos de documento
        tipos_doc = [(r["id"], r["nome"], r["ordem"]) for r in sqlite_conn.execute("SELECT id, nome, ordem FROM tipo_documento_sei")]
        inserir_lote(
            "INSERT INTO tipo_documento_sei (id, nome, ordem) VALUES (%s, %s, %s) ON CONFLICT (id) DO NOTHING",
            tipos_doc,
            "Tipos de documento"
        )

        # Processos
        processos = []
        for r in sqlite_conn.execute("""
            SELECT codigo, tipo, numero_sei, id_procedimento_sei, assunto, status, pasta_id, cadastro, criado_em
            FROM processo
        """):
            processos.append((
                r["codigo"], r["tipo"], r["numero_sei"],
                r["id_procedimento_sei"], r["assunto"], r["status"],
                r["pasta_id"], r["cadastro"], r["criado_em"]
            ))
        inserir_lote(
            """INSERT INTO processo
               (codigo, tipo, numero_sei, id_procedimento_sei, assunto, status, pasta_id, cadastro, criado_em)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (codigo) DO NOTHING""",
            processos,
            "Processos"
        )

        print("Migração concluída com sucesso.")
    except Exception as e:
        print(f"Erro na migração: {type(e).__name__}: {e}")
        if pg_conn and not pg_conn.closed:
            try:
                pg_conn.rollback()
            except Exception:
                pass
        raise
    finally:
        sqlite_conn.close()
        if pg_conn and not pg_conn.closed:
            pg_conn.close()

if __name__ == "__main__":
    migrar()
