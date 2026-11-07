from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.ingest import store_chunks
from app.llm import LLMUnavailable
from app.main import app, get_llm
from app.parsing import Chunk
from tests.fakes import FakeLLM

UNREACHABLE_DB = "postgresql://lft:lft@127.0.0.1:1/none"


@pytest.fixture
def make_client(conn, database_url):
    def build(llm, **overrides):
        settings = replace(
            Settings(source_version="v1", min_similarity=0.5),
            database_url=database_url,
            **overrides,
        )
        app.dependency_overrides[get_settings] = lambda: settings
        app.dependency_overrides[get_llm] = lambda: llm
        return TestClient(app)

    yield build
    app.dependency_overrides.clear()


@pytest.fixture
def seeded(conn):
    store_chunks(conn, FakeLLM([]), [Chunk("76", 0, "Doce días.")], "v1")


@pytest.mark.parametrize("question", ["", "   ", "\n\t", "x" * 501])
def test_invalid_question_is_422(make_client, question):
    client = make_client(FakeLLM([]))
    assert client.post("/ask", json={"question": question}).status_code == 422


def test_missing_question_is_422(make_client):
    assert make_client(FakeLLM([])).post("/ask", json={}).status_code == 422


def test_500_chars_is_accepted(make_client):
    assert make_client(FakeLLM([])).post("/ask", json={"question": "x" * 500}).status_code == 200


def test_surrounding_spaces_do_not_count_toward_the_limit(make_client):
    body = {"question": "  " + "x" * 500 + "  "}
    assert make_client(FakeLLM([])).post("/ask", json=body).status_code == 200


def test_answer_shape(make_client, seeded):
    client = make_client(FakeLLM(["Son doce [Art. 76]."]))
    response = client.post("/ask", json={"question": "vacaciones"})
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"status", "answer", "citations", "unverified_citations", "trace_id"}
    assert body["status"] == "answered"
    assert body["citations"] == [{"article": "76", "text": "Doce días."}]


def test_budget_is_429(make_client, conn, seeded):
    conn.execute(
        "insert into traces (question, status, model, cost_usd) values ('q', 'answered', 'm', 5)"
    )
    conn.commit()
    response = make_client(FakeLLM([])).post("/ask", json={"question": "vacaciones"})
    assert response.status_code == 429
    assert "presupuesto" in response.json()["detail"]


def test_llm_down_is_503_with_clear_message(make_client, conn, seeded):
    client = make_client(FakeLLM([LLMUnavailable("connection refused")]))
    response = client.post("/ask", json={"question": "vacaciones"})
    assert response.status_code == 503
    assert "Ollama" in response.json()["detail"]
    assert "connection refused" not in response.json()["detail"]
    row = conn.execute("select status from traces").fetchone()
    assert row == ("error",)


def test_database_down_is_503(make_client):
    client = make_client(FakeLLM([]))
    settings = app.dependency_overrides[get_settings]()
    app.dependency_overrides[get_settings] = lambda: replace(settings, database_url=UNREACHABLE_DB)
    response = client.post("/ask", json={"question": "vacaciones"})
    assert response.status_code == 503
    assert "base de datos" in response.json()["detail"]


def test_health_ok(make_client):
    response = make_client(FakeLLM([])).get("/health")
    assert (response.status_code, response.json()) == (200, {"postgres": True, "ollama": True})


def test_health_reports_each_dependency(make_client):
    client = make_client(FakeLLM([], embed_error=LLMUnavailable("down")))
    response = client.get("/health")
    assert (response.status_code, response.json()) == (503, {"postgres": True, "ollama": False})


def test_health_reports_database_down(make_client):
    client = make_client(FakeLLM([]))
    settings = app.dependency_overrides[get_settings]()
    app.dependency_overrides[get_settings] = lambda: replace(settings, database_url=UNREACHABLE_DB)
    response = client.get("/health")
    assert (response.status_code, response.json()) == (503, {"postgres": False, "ollama": True})


def test_startup_survives_unreachable_database(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", UNREACHABLE_DB)
    with TestClient(app):
        pass
