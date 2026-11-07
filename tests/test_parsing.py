from app.parsing import Article, numbering_gaps, parse_articles, split_chunks, strip_page_furniture


def test_parses_ordinal_suffix_and_bis():
    arts = parse_articles("Artículo 1o.- Uno.\nArtículo 153-A.- Dos.\nArtículo 311 Bis.- Tres.")
    assert [a.article for a in arts] == ["1", "153-A", "311 Bis"]
    assert arts[0].text == "Uno."


def test_parses_spacing_variants_found_in_the_real_pdf():
    text = "Artículo 76 .- A.\nArtículo 100. - B.\nArtículo 153 -E. C.\nArtículo 22 Bis. D."
    assert [a.article for a in parse_articles(text)] == ["76", "100", "153-E", "22 Bis"]


def test_inline_reference_does_not_start_an_article():
    arts = parse_articles("Artículo 5o.- Texto conforme al\nartículo 76 de esta ley.")
    assert [a.article for a in arts] == ["5"]
    assert "artículo 76" in arts[0].text


def test_stops_at_transitorios():
    arts = parse_articles("Artículo 1o.- Uno.\nTRANSITORIOS\nArtículo Primero.- X.\nArtículo 2o.- Y.")
    assert [a.article for a in arts] == ["1"]


def test_reform_notes_are_removed():
    text = (
        "Artículo 3o.- Texto.\n"
        "Párrafo reformado DOF 01-05-2019, 15-01-2026\n"
        "Sigue el texto.\n"
        "Artículo reformado DOF 27-12-2022\n"
        "Artículo 4o.- Otro."
    )
    arts = parse_articles(text)
    assert [a.article for a in arts] == ["3", "4"]
    assert arts[0].text == "Texto.\nSigue el texto."


def test_chapter_headings_do_not_leak_into_the_previous_article():
    text = "Artículo 75.- Fin.\nCAPITULO IV\nVacaciones\nArtículo 76.- Inicio."
    assert parse_articles(text)[0].text == "Fin."


def test_page_furniture_is_removed_but_body_is_kept():
    pages = [f"LEY FEDERAL DEL TRABAJO\nSecretaría General\n{n} de 3\nCuerpo {n}" for n in (1, 2, 3)]
    assert strip_page_furniture(pages) == "Cuerpo 1\nCuerpo 2\nCuerpo 3"


def test_long_article_splits_by_paragraph_with_same_number():
    text = "\n".join(["p" * 900, "q" * 900])
    chunks = split_chunks([Article("76", text)])
    assert [(c.article, c.part) for c in chunks] == [("76", 0), ("76", 1)]


def test_short_article_is_one_chunk():
    chunks = split_chunks([Article("87", "uno\ndos")])
    assert [(c.part, c.text) for c in chunks] == [(0, "uno\ndos")]


def test_single_paragraph_over_limit_is_hard_split():
    chunks = split_chunks([Article("76", "x" * 3200)])
    assert len(chunks) == 3 and all(len(c.text) <= 1500 for c in chunks)
    assert "".join(c.text for c in chunks) == "x" * 3200


def test_numbering_gaps_ignore_suffixes():
    arts = [Article(n, "t") for n in ("1", "2", "2 Bis", "5", "6-A")]
    assert numbering_gaps(arts) == [3, 4]


def test_parses_ordinal_followed_by_word_suffix():
    text = "Artículo 3o. Bis.- A.\nArtículo 3o. Ter.- B.\nArtículo 3o.- C."
    assert [a.article for a in parse_articles(text)] == ["3 Bis", "3 Ter", "3"]


def test_parses_dash_without_period():
    assert [a.article for a in parse_articles("Artículo 890- Se deroga.")] == ["890"]
    assert parse_articles("Artículo 890- Se deroga.")[0].text == "Se deroga."


def test_other_editorial_notes_are_removed():
    text = (
        "Artículo 13.- Texto.\n"
        "Fe de erratas al artículo DOF 30-04-1970. Reformado DOF 23-04-2021\n"
        "Reforma DOF 01-05-2026: Derogó del artículo el entonces párrafo segundo\n"
        "VII. La Falta (sic DOF 04-06-2019) de los documentos."
    )
    assert parse_articles(text)[0].text == "Texto.\nVII. La Falta de los documentos."


def test_repealed_articles_produce_no_chunks():
    articles = [Article("16", "Se deroga."), Article("169", "(Se deroga)."), Article("87", "Aguinaldo.")]
    assert [c.article for c in split_chunks(articles)] == ["87"]


def test_parses_letter_with_word_suffix_and_enye():
    text = "Artículo 153-F Bis. A.\nArtículo 353-Ñ.- B.\nArtículo 512-D Ter. C."
    assert [a.article for a in parse_articles(text)] == ["153-F Bis", "353-Ñ", "512-D Ter"]


def test_any_line_dated_in_the_official_gazette_is_a_note():
    text = (
        "Artículo 641-A.- Texto.\n"
        "Nota: El decreto de reforma DOF 01-05-2019 no derogó el artículo.\n"
        "Derogado DOF 01-05-2019\n"
        "de trabajo” DOF 04-12-2023\n"
        "TITULO QUINCE\n"
        "Procedimientos de Ejecución\n"
        "Título reubicado y denominación reformada DOF 04-01-1980\n"
        "Artículo 642.- Otro."
    )
    assert parse_articles(text)[0].text == "Texto."
