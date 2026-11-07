import psycopg
import pytest

from app.db import apply_schema


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
