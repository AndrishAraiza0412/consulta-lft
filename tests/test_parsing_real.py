from pathlib import Path

import pytest

from app.parsing import extract_text, numbering_gaps, parse_articles


@pytest.fixture(scope="module")
def articles():
    parsed = parse_articles(extract_text(Path("data/LFT.pdf")))
    return {a.article: a.text for a in parsed}, parsed


def test_real_law_extracts_key_articles(articles):
    by_number, _ = articles
    assert "vacaciones" in by_number["76"] and "doce días" in by_number["76"]
    assert "aguinaldo" in by_number["87"] and "quince días" in by_number["87"]
    assert "153-A" in by_number
    assert "22 Bis" in by_number


def test_no_article_is_parsed_twice(articles):
    by_number, parsed = articles
    assert len(by_number) == len(parsed)


def test_page_furniture_and_notes_do_not_remain(articles):
    by_number, _ = articles
    for text in by_number.values():
        assert "Secretaría de Servicios Parlamentarios" not in text
        assert "DOF" not in text
        assert "CAPITULO" not in text and "TITULO" not in text


def test_transitory_articles_are_excluded(articles):
    by_number, _ = articles
    assert "se harán efectivas" in by_number["1010"]
    assert "Esta Ley entrará en vigor" not in by_number["1010"]


def test_numbering_has_no_gaps_and_keeps_suffixed_siblings(articles):
    by_number, parsed = articles
    assert numbering_gaps(parsed) == []
    assert {"3", "3 Bis", "3 Ter", "890"} <= by_number.keys()
