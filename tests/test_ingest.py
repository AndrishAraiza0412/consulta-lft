import pytest

from app.ingest import store_chunks
from app.llm import LLMUnavailable
from app.parsing import Chunk
from tests.fakes import FakeLLM


def texts(conn):
    return conn.execute("select text from chunks order by article, part").fetchall()


def test_reingest_replaces_chunks(conn):
    store_chunks(conn, FakeLLM([]), [Chunk("1", 0, "viejo"), Chunk("2", 0, "x")], "v1")
    assert store_chunks(conn, FakeLLM([]), [Chunk("1", 0, "nuevo")], "v1") == 1
    assert texts(conn) == [("nuevo",)]


def test_reingest_leaves_other_versions_alone(conn):
    store_chunks(conn, FakeLLM([]), [Chunk("1", 0, "antes")], "v1")
    store_chunks(conn, FakeLLM([]), [Chunk("1", 0, "ahora")], "v2")
    assert sorted(texts(conn)) == [("ahora",), ("antes",)]


def test_failed_reingest_keeps_previous_chunks(conn):
    store_chunks(conn, FakeLLM([]), [Chunk("1", 0, "viejo")], "v1")
    broken = FakeLLM([], embed_error=LLMUnavailable("down"))
    with pytest.raises(LLMUnavailable):
        store_chunks(conn, broken, [Chunk("1", 0, "nuevo")], "v1")
    assert texts(conn) == [("viejo",)]


def test_chunks_are_embedded_in_batches(conn):
    llm = FakeLLM([])
    sizes = []
    original = llm.embed
    llm.embed = lambda batch: (sizes.append(len(batch)), original(batch))[1]
    chunks = [Chunk(str(n), 0, f"t{n}") for n in range(40)]
    assert store_chunks(conn, llm, chunks, "v1") == 40
    assert sizes == [32, 8]
