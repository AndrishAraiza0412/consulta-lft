import re

ARTICLE = (
    r"(?P<number>\d+)\s*"
    r"(?:-\s*(?P<letter>[a-zñ])\b|[oº°]\b\.?)?"
    r"(?:\s*(?P<word>bis|ter|qu[áa]ter)\b(?:\s*(?P<word_number>\d+)\b)?)?"
)
UNNAMED = re.sub(r"\?P<\w+>", "?:", ARTICLE)
# "artículos 76, 87 y 999": the prefix once, then every number in the list
CITATION = re.compile(
    rf"\bart(?:[íi]culos?|s?\.?)\s*{ARTICLE}(?:\s*(?:,|\by\b|\be\b)\s*{UNNAMED})*",
    re.IGNORECASE,
)
ITEM = re.compile(ARTICLE, re.IGNORECASE)


def extract_citations(answer: str) -> list[str]:
    cited: dict[str, None] = {}
    for group in CITATION.finditer(answer):
        text = group[0]
        # skip the "art..." prefix so only the numbers are scanned
        for match in ITEM.finditer(re.sub(r"^art\S*\s*", "", text, flags=re.IGNORECASE)):
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
