import sys
from pathlib import Path

import psycopg

from app.config import get_settings
from app.db import apply_schema, connect
from app.llm import LLM
from app.parsing import Chunk, extract_text, numbering_gaps, parse_articles, split_chunks

BATCH_SIZE = 32


def store_chunks(conn: psycopg.Connection, llm: LLM, chunks: list[Chunk], source_version: str) -> int:
    embeddings: list[list[float]] = []
    for start in range(0, len(chunks), BATCH_SIZE):
        embeddings.extend(llm.embed([chunk.text for chunk in chunks[start : start + BATCH_SIZE]]))

    with conn.transaction():
        conn.execute("delete from chunks where source_version = %s", (source_version,))
        with conn.cursor() as cursor:
            cursor.executemany(
                "insert into chunks (source_version, article, part, text, embedding) "
                "values (%s, %s, %s, %s, %s::vector)",
                [
                    (source_version, chunk.article, chunk.part, chunk.text, embedding)
                    for chunk, embedding in zip(chunks, embeddings)
                ],
            )
    conn.commit()
    return len(chunks)


def main(path: str) -> None:
    settings = get_settings()
    articles = parse_articles(extract_text(Path(path)))
    chunks = split_chunks(articles)
    print(f"articles: {len(articles)}  chunks: {len(chunks)}  gaps: {numbering_gaps(articles)}")
    with connect(settings.database_url) as conn:
        apply_schema(conn)
        stored = store_chunks(conn, LLM(settings), chunks, settings.source_version)
    print(f"stored: {stored}  version: {settings.source_version}")


if __name__ == "__main__":
    main(sys.argv[1])
