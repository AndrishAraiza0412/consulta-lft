import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Response
from pydantic import BaseModel, StringConstraints

from app.ask import AskResult, BudgetExceeded, ask
from app.config import Settings, get_settings
from app.db import apply_schema, connect
from app.llm import LLM, LLMUnavailable

logger = logging.getLogger("consulta_lft")

DATABASE_DOWN = "La base de datos no está disponible."
OLLAMA_DOWN = "Ollama no está disponible. Comprueba que esté corriendo y que el modelo exista."
BUDGET_EXHAUSTED = "Se agotó el presupuesto mensual de consultas."


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    try:
        with connect(get_settings().database_url) as conn:
            apply_schema(conn)
    except psycopg.OperationalError as error:
        logger.warning("schema not applied at startup: %s", error)
    yield


app = FastAPI(title="Consulta LFT", lifespan=lifespan)


def get_llm(settings: Annotated[Settings, Depends(get_settings)]) -> LLM:
    return LLM(settings)


class Question(BaseModel):
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500, pattern=r"^[^\x00]*$")]


@app.post("/ask")
def post_ask(
    body: Question,
    settings: Annotated[Settings, Depends(get_settings)],
    llm: Annotated[LLM, Depends(get_llm)],
) -> AskResult:
    try:
        # ponytail: one connection per request; add a pool if concurrent traffic ever matters.
        with connect(settings.database_url) as conn:
            return ask(conn, llm, settings, body.question)
    except BudgetExceeded as error:
        raise HTTPException(429, BUDGET_EXHAUSTED) from error
    except LLMUnavailable as error:
        logger.error("LLM unavailable: %s", error)
        raise HTTPException(503, OLLAMA_DOWN) from error
    except psycopg.OperationalError as error:
        logger.error("database unavailable: %s", error)
        raise HTTPException(503, DATABASE_DOWN) from error


@app.get("/health")
def health(
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
    llm: Annotated[LLM, Depends(get_llm)],
) -> dict[str, bool]:
    try:
        with connect(settings.database_url) as conn:
            conn.execute("select 1")
        postgres = True
    except psycopg.OperationalError:
        postgres = False
    try:
        llm.ping()
        ollama = True
    except LLMUnavailable:
        ollama = False
    if not (postgres and ollama):
        response.status_code = 503
    return {"postgres": postgres, "ollama": ollama}
