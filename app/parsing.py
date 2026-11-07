import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pdfplumber

ARTICLE_START = re.compile(
    r"^\s*Artículo\s+(?P<number>\d+)\s*"
    r"(?:-\s*(?P<letter>[A-ZÑ])(?![a-záéíóúñ])|[oº°]\.?)?"
    r"\s*(?:(?P<word>Bis|Ter|Quáter|Quater)(?:\s*(?P<word_number>\d+))?)?"
    r"\s*(?:\.\s*-?|-)\s*",
    re.MULTILINE,
)
TRANSITORIOS = re.compile(r"^\s*TRANSITORIOS?\s*$", re.MULTILINE)
PAGE_NUMBER = re.compile(r"^\s*\d+\s+de\s+\d+\s*$")
GAZETTE_NOTE = re.compile(
    r"^[^\n]*DOF\s+\d{2}-\d{2}-\d{4}[^\n]*(?:\n\s*\d{2}-\d{2}-\d{4}[^\n]*)*$", re.MULTILINE
)
SIC_NOTE = re.compile(r"\s*\(sic DOF \d{2}-\d{2}-\d{4}\)")
REPEALED = re.compile(r"^\(?Se deroga\)?\.?\)?\.?$", re.IGNORECASE)
HEADING = re.compile(
    r"^\s*(?:T[IÍ]TULO|CAP[IÍ]TULO|SECCI[OÓ]N)\b[^\n]*(?:\n(?!\s*Artículo\s)[^\n]{1,120}(?<!\.))?\s*$",
    re.MULTILINE,
)


@dataclass(frozen=True)
class Article:
    article: str
    text: str


@dataclass(frozen=True)
class Chunk:
    article: str
    part: int
    text: str


def strip_page_furniture(pages: list[str]) -> str:
    seen = Counter(line.strip() for page in pages for line in set(page.splitlines()))
    repeated = {line for line, count in seen.items() if line and count > len(pages) / 2}
    kept = (
        line
        for page in pages
        for line in page.splitlines()
        if line.strip() not in repeated and not PAGE_NUMBER.match(line)
    )
    return "\n".join(kept)


def extract_text(path: Path) -> str:
    with pdfplumber.open(path) as pdf:
        return strip_page_furniture([page.extract_text() or "" for page in pdf.pages])


def _article_id(match: re.Match) -> str:
    article = match["number"]
    if match["letter"]:
        article += f"-{match['letter']}"
    if match["word"]:
        article += f" {match['word']}"
    if match["word_number"]:
        article += f" {match['word_number']}"
    return article


def _clean(text: str) -> str:
    text = HEADING.sub("", GAZETTE_NOTE.sub("", SIC_NOTE.sub("", text)))
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def parse_articles(text: str) -> list[Article]:
    end = TRANSITORIOS.search(text)
    body = text[: end.start()] if end else text
    matches = list(ARTICLE_START.finditer(body))
    articles = []
    for match, following in zip(matches, [*matches[1:], None]):
        stop = following.start() if following else len(body)
        articles.append(Article(_article_id(match), _clean(body[match.end() : stop])))
    return articles


def split_chunks(articles: list[Article], max_chars: int = 1500) -> list[Chunk]:
    chunks = []
    for article in articles:
        if REPEALED.match(article.text):
            continue
        pieces = []
        current = ""
        for line in article.text.split("\n"):
            while len(line) > max_chars:
                if current:
                    pieces.append(current)
                    current = ""
                pieces.append(line[:max_chars])
                line = line[max_chars:]
            candidate = f"{current}\n{line}" if current else line
            if len(candidate) > max_chars:
                pieces.append(current)
                current = line
            else:
                current = candidate
        if current:
            pieces.append(current)
        chunks.extend(Chunk(article.article, part, piece) for part, piece in enumerate(pieces))
    return chunks


def numbering_gaps(articles: list[Article]) -> list[int]:
    numbers = {int(re.match(r"\d+", a.article)[0]) for a in articles}
    return sorted(set(range(min(numbers), max(numbers) + 1)) - numbers)
