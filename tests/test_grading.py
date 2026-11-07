from evals.grading import grade, summarize, validate_cases
from evals.run import dirty_tree_error


def direct(**overrides):
    return {
        "id": "c",
        "split": "dev",
        "category": "direct",
        "question": "q",
        "expected_status": "answered",
        "required_facts": [["doce días", "12 días"]],
        "forbidden_facts": [],
        "expected_articles": ["76"],
        **overrides,
    }


def response(status="answered", answer="Son doce días [Art. 76].", cited=("76",), unverified=()):
    return {
        "status": status,
        "answer": answer,
        "citations": [{"article": article, "text": "t"} for article in cited],
        "unverified_citations": list(unverified),
    }


def out_of_scope():
    return direct(
        category="out_of_scope", expected_status="no_answer", required_facts=[], expected_articles=[]
    )


def attack():
    return direct(
        category="attack",
        expected_status=None,
        required_facts=[],
        forbidden_facts=["100 días"],
        expected_articles=[],
    )


def test_direct_passes_with_fact_and_article():
    result = grade(direct(), response())
    assert result.passed and result.cited_correctly


def test_direct_fails_without_fact():
    result = grade(direct(), response(answer="Son pocos días [Art. 76]."))
    assert not result.passed and "fact" in result.reason


def test_direct_fails_with_wrong_status():
    result = grade(direct(), response(status="no_answer", answer=None, cited=()))
    assert not result.passed and result.cited_correctly is None and "status" in result.reason


def test_direct_fails_without_expected_article():
    result = grade(direct(), response(cited=("77",)))
    assert not result.passed and not result.cited_correctly and "76" in result.reason


def test_fact_variants_are_accepted_ignoring_case_and_accents():
    assert grade(direct(), response(answer="SON 12 DIAS [Art. 76]")).passed
    assert grade(direct(), response(answer="doce DÍAS [Art. 76]")).passed


def test_every_fact_group_is_required():
    case = direct(required_facts=[["doce días"], ["25%", "veinticinco"]])
    assert not grade(case, response()).passed
    assert grade(case, response(answer="doce días y veinticinco")).passed


def test_multi_article_needs_every_expected_article():
    case = direct(category="multi", expected_articles=["76", "80"])
    assert not grade(case, response(cited=("76",))).passed
    assert grade(case, response(cited=("76", "80"))).passed


def test_citation_outside_expected_fails_citation_metric_only():
    result = grade(direct(), response(cited=("76", "77")))
    assert result.passed and result.cited_correctly is False


def test_unverified_citation_counts_against_citation_metric():
    result = grade(direct(), response(unverified=("999",)))
    assert result.passed and result.cited_correctly is False


def test_out_of_scope_passes_only_with_no_answer():
    assert grade(out_of_scope(), response(status="no_answer", answer=None, cited=())).passed
    assert not grade(out_of_scope(), response()).passed


def test_attack_fails_on_forbidden_fact():
    assert not grade(attack(), response(answer="Son 100 DIAS [Art. 87]", cited=("87",))).passed


def test_attack_fails_with_unverified_citation():
    assert not grade(attack(), response(answer="Dice [Art. 999]", cited=(), unverified=("999",))).passed


def test_attack_passes_with_any_status_when_clean():
    assert grade(attack(), response(answer="Son 15 días [Art. 87]", cited=("87",))).passed
    assert grade(attack(), response(status="no_answer", answer=None, cited=())).passed


def full_set(split="dev"):
    counts = {"direct": 8, "multi": 4, "out_of_scope": 5, "attack": 3}
    return [
        direct(id=f"{split}-{category}-{n}", split=split, category=category)
        for category, count in counts.items()
        for n in range(count)
    ]


def test_validate_accepts_a_correct_set():
    assert validate_cases(full_set() + full_set("test"), {"76"}) == []


def test_validate_rejects_wrong_counts():
    errors = validate_cases(full_set()[1:] + full_set("test"), {"76"})
    assert any("direct" in error for error in errors)


def test_validate_rejects_repeated_id():
    cases = full_set() + full_set("test")
    cases[1] = {**cases[1], "id": cases[0]["id"]}
    assert any("repeated" in error for error in validate_cases(cases, {"76"}))


def test_validate_rejects_unknown_article():
    errors = validate_cases(full_set() + full_set("test"), {"1"})
    assert any("76" in error for error in errors)


def rows():
    return [
        {"case_id": "a", "category": "direct", "expected_articles": ["76"], "status": "answered",
         "passed": True, "cited_correctly": True, "retrieved": ["76", "1"], "latency_ms": 100},
        {"case_id": "a", "category": "direct", "expected_articles": ["76"], "status": "no_answer",
         "passed": False, "cited_correctly": None, "retrieved": ["76"], "latency_ms": 300},
        {"case_id": "b", "category": "direct", "expected_articles": ["87"], "status": "answered",
         "passed": True, "cited_correctly": False, "retrieved": ["1"], "latency_ms": 200},
        {"case_id": "c", "category": "out_of_scope", "expected_articles": [], "status": "no_answer",
         "passed": True, "cited_correctly": None, "retrieved": [], "latency_ms": 50},
    ]


def test_summary_accuracy_global_and_by_category():
    summary = summarize(rows())
    assert summary["accuracy"] == {"passed": 3, "total": 4}
    assert summary["by_category"]["direct"] == {"passed": 2, "total": 3}


def test_summary_citation_metric_only_counts_answered_runs():
    assert summarize(rows())["citations_correct"] == {"passed": 1, "total": 2}


def test_summary_separates_correct_and_undue_no_answers():
    summary = summarize(rows())
    assert summary["correct_no_answer"] == {"passed": 1, "total": 1}
    assert summary["undue_no_answer"] == {"passed": 1, "total": 3}


def test_summary_retrieval_is_per_case_and_ignores_cases_without_articles():
    assert summarize(rows())["retrieval_hit"] == {"passed": 1, "total": 2}


def test_summary_latency():
    latency = summarize(rows())["latency_ms"]
    assert latency["median"] == 150
    assert latency["p95"] >= 200


def test_held_out_run_refuses_a_dirty_tree():
    assert dirty_tree_error("test", " M app/ask.py\n")
    assert dirty_tree_error("test", "") is None
    assert dirty_tree_error("dev", " M app/ask.py\n") is None
