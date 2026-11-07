from app.ingest import store_chunks
from app.parsing import Chunk
from app.retrieval import article_text, search
from tests.fakes import FakeLLM, unit_vector


def blend(a: int, b: int) -> list[float]:
    vector = [0.0] * 1024
    vector[a] = 0.9
    vector[b] = 0.1
    return vector


def test_search_orders_by_similarity_and_filters_version(conn):
    vectors = {"far": blend(1, 0), "near": blend(0, 1), "other": unit_vector(0)}
    llm = FakeLLM([], vectors=vectors)
    store_chunks(conn, llm, [Chunk("a", 0, "near"), Chunk("b", 0, "far")], "v1")
    store_chunks(conn, llm, [Chunk("c", 0, "other")], "v2")

    hits = search(conn, unit_vector(0), "v1", 5)

    assert [hit.article for hit in hits] == ["a", "b"]
    assert hits[0].similarity > hits[1].similarity


def test_search_respects_top_k(conn):
    store_chunks(conn, FakeLLM([]), [Chunk(str(n), 0, f"t{n}") for n in range(4)], "v1")
    assert len(search(conn, unit_vector(0), "v1", 2)) == 2


def test_search_on_empty_table_returns_nothing(conn):
    assert search(conn, unit_vector(0), "v1", 5) == []


def test_article_text_joins_parts_in_order(conn):
    chunks = [Chunk("76", 1, "parte uno"), Chunk("76", 0, "parte cero"), Chunk("77", 0, "otro")]
    store_chunks(conn, FakeLLM([]), chunks, "v1")
    assert article_text(conn, "v1", "76") == "parte cero\nparte uno"
