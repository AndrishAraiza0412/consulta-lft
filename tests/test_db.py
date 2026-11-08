import psycopg
import pytest

from app.db import apply_schema, connect


def test_schema_creates_tables_and_is_idempotent(conn):
    apply_schema(conn)
    names = {
        row[0]
        for row in conn.execute("select tablename from pg_tables where schemaname = 'public'")
    }
    assert {"chunks", "traces"} <= names


def test_chunk_identity_is_unique(conn):
    insert = (
        "insert into chunks (source_version, article, part, text, embedding) "
        "values ('v', '76', 0, 'x', %s)"
    )
    conn.execute(insert, ([0.0] * 1024,))
    with pytest.raises(psycopg.errors.UniqueViolation):
        conn.execute(insert, ([0.0] * 1024,))


def test_connect_works_on_a_fresh_database_without_the_extension(database_url):
    server_url = database_url.rsplit("/", 1)[0]
    with psycopg.connect(f"{server_url}/postgres", autocommit=True) as admin:
        admin.execute("drop database if exists lft_fresh")
        admin.execute("create database lft_fresh")
    try:
        with connect(f"{server_url}/lft_fresh") as conn:
            apply_schema(conn)
            assert conn.execute("select count(*) from chunks").fetchone() == (0,)
    finally:
        with psycopg.connect(f"{server_url}/postgres", autocommit=True) as admin:
            admin.execute("drop database if exists lft_fresh")
