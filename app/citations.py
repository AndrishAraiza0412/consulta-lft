import re

CITATION = re.compile(
    r"\bart(?:[íi]culos?|s?\.?)\s*(?P<number>\d+)\s*"
    r"(?:-\s*(?P<letter>[a-zñ])\b|[oº°]\b\.?)?"
    r"(?:\s*(?P<word>bis|ter|qu[áa]ter)\b(?:\s*(?P<word_number>\d+)\b)?)?",
    re.IGNORECASE,
)


def extract_citations(answer: str) -> list[str]:
    cited: dict[str, None] = {}
    for match in CITATION.finditer(answer):
        article = match["number"]
        if match["letter"]:
            article += f"-{match['letter'].upper()}"
        if match["word"]:
            article += f" {match['word'].capitalize()}"
        if match["word_number"]:
            article += f" {match['word_number']}"
        cited[article] = None
    return list(cited)


def split_citations(cited: list[str], allowed: set[str]) -> tuple[list[str], list[str]]:
    valid = [article for article in cited if article in allowed]
    unverified = [article for article in cited if article not in allowed]
    return valid, unverified
