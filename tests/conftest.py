import os

import psycopg
import pytest

from app.db import apply_schema, connect

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://lft:lft@127.0.0.1:15433/lft_test"
)


@pytest.fixture(scope="session")
def database_url():
    server_url, name = TEST_DATABASE_URL.rsplit("/", 1)
    with psycopg.connect(f"{server_url}/postgres", autocommit=True) as admin:
        exists = admin.execute("select 1 from pg_database where datname = %s", (name,)).fetchone()
        if not exists:
            admin.execute(f'create database "{name}"')
    with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as setup:
        apply_schema(setup)
    return TEST_DATABASE_URL


@pytest.fixture
def conn(database_url):
    with connect(database_url) as connection:
        connection.execute("truncate chunks, traces")
        connection.commit()
        yield connection
