from pathlib import Path

import psycopg
from pgvector.psycopg import register_vector

SCHEMA = Path(__file__).with_name("schema.sql")


def apply_schema(conn: psycopg.Connection) -> None:
    conn.execute(SCHEMA.read_text())
    conn.commit()


def connect(url: str) -> psycopg.Connection:
    conn = psycopg.connect(url)
    register_vector(conn)
    return conn
