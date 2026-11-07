from dataclasses import dataclass

import psycopg


@dataclass(frozen=True)
class Hit:
    article: str
    part: int
    text: str
    similarity: float


def search(
    conn: psycopg.Connection, embedding: list[float], source_version: str, top_k: int
) -> list[Hit]:
    rows = conn.execute(
        "select article, part, text, 1 - (embedding <=> %(query)s::vector) as similarity "
        "from chunks where source_version = %(version)s "
        "order by embedding <=> %(query)s::vector limit %(limit)s",
        {"query": embedding, "version": source_version, "limit": top_k},
    ).fetchall()
    return [Hit(*row) for row in rows]


def article_text(conn: psycopg.Connection, source_version: str, article: str) -> str:
    rows = conn.execute(
        "select text from chunks where source_version = %s and article = %s order by part",
        (source_version, article),
    ).fetchall()
    return "\n".join(row[0] for row in rows)
