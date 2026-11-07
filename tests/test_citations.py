import pytest

from app.citations import extract_citations, split_citations


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Según [Art. 76].", ["76"]),
        ("[Artículo 76]", ["76"]),
        ("Art. 153-A", ["153-A"]),
        ("[art 311 Bis]", ["311 Bis"]),
        ("[Art. 76] y [Art. 76], [Art. 87]", ["76", "87"]),
        ("Sin citas.", []),
        ("[Art. 5o]", ["5"]),
        ("[ART. 153 -e]", ["153-E"]),
        ("[Art. 153-F BIS]", ["153-F Bis"]),
        ("[Art. 353-Ñ]", ["353-Ñ"]),
        ("[Articulo 87].", ["87"]),
        ("El artículo 87 dice", ["87"]),
        ("Son 15 días y 2 meses", []),
    ],
)
def test_extract_citations(text, expected):
    assert extract_citations(text) == expected


def test_split_citations():
    assert split_citations(["76", "999"], {"76", "87"}) == (["76"], ["999"])
