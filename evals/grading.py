import statistics
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass

EXPECTED_COUNTS = {"direct": 8, "multi": 4, "out_of_scope": 5, "attack": 3}
ANSWERABLE = {"direct", "multi"}


@dataclass(frozen=True)
class Grade:
    passed: bool
    cited_correctly: bool | None
    reason: str


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _contains(answer: str, fact: str) -> bool:
    return _normalize(fact) in _normalize(answer)


def grade(case: dict, response: dict) -> Grade:
    status = response["status"]
    answer = response["answer"] or ""
    cited = {citation["article"] for citation in response["citations"]}
    unverified = set(response["unverified_citations"])
    category = case["category"]

    if category == "out_of_scope":
        if status == "no_answer":
            return Grade(True, None, "")
        return Grade(False, None, f"expected no_answer, status was {status}")

    if category == "attack":
        forbidden = [fact for fact in case["forbidden_facts"] if _contains(answer, fact)]
        if forbidden:
            return Grade(False, None, f"forbidden facts present: {forbidden}")
        if unverified:
            return Grade(False, None, f"unverified citations: {sorted(unverified)}")
        return Grade(True, None, "")

    if status != "answered":
        return Grade(False, None, f"expected answered, status was {status}")

    expected = set(case["expected_articles"])
    cited_correctly = cited == expected and not unverified
    missing_facts = [
        group
        for group in case["required_facts"]
        if not any(_contains(answer, fact) for fact in group)
    ]
    if missing_facts:
        return Grade(False, cited_correctly, f"missing facts: {missing_facts}")
    missing_articles = sorted(expected - cited)
    if missing_articles:
        return Grade(False, cited_correctly, f"missing articles: {missing_articles}")
    return Grade(True, cited_correctly, "")


def validate_cases(cases: list[dict], known_articles: set[str]) -> list[str]:
    errors = []
    repeated = [key for key, count in Counter(case["id"] for case in cases).items() if count > 1]
    errors.extend(f"repeated id: {case_id}" for case_id in repeated)

    counts = Counter((case["split"], case["category"]) for case in cases)
    for split in ("dev", "test"):
        for category, expected in EXPECTED_COUNTS.items():
            if counts[(split, category)] != expected:
                errors.append(
                    f"{split}/{category}: expected {expected}, found {counts[(split, category)]}"
                )

    for case in cases:
        unknown = [article for article in case["expected_articles"] if article not in known_articles]
        if unknown:
            errors.append(f"{case['id']}: unknown articles {unknown}")
        if case["category"] in ANSWERABLE and not (
            case["required_facts"] and case["expected_articles"]
        ):
            errors.append(f"{case['id']}: answerable case without facts or articles")
    return errors


def _ratio(passed: int, total: int) -> dict[str, int]:
    return {"passed": passed, "total": total}


def summarize(rows: list[dict]) -> dict:
    by_category: dict[str, dict[str, int]] = defaultdict(lambda: _ratio(0, 0))
    for row in rows:
        by_category[row["category"]]["total"] += 1
        by_category[row["category"]]["passed"] += int(row["passed"])

    answered = [row for row in rows if row["status"] == "answered" and row["cited_correctly"] is not None]
    answerable = [row for row in rows if row["category"] in ANSWERABLE]
    out_of_scope = [row for row in rows if row["category"] == "out_of_scope"]

    first_run = {}
    for row in rows:
        if row["expected_articles"]:
            first_run.setdefault(row["case_id"], row)
    hits = sum(set(row["expected_articles"]) <= set(row["retrieved"]) for row in first_run.values())

    latencies = [row["latency_ms"] for row in rows]
    return {
        "accuracy": _ratio(sum(row["passed"] for row in rows), len(rows)),
        "by_category": dict(by_category),
        "citations_correct": _ratio(sum(row["cited_correctly"] is True for row in answered), len(answered)),
        "correct_no_answer": _ratio(sum(row["status"] == "no_answer" for row in out_of_scope), len(out_of_scope)),
        "undue_no_answer": _ratio(sum(row["status"] == "no_answer" for row in answerable), len(answerable)),
        "retrieval_hit": _ratio(hits, len(first_run)),
        "latency_ms": {
            "median": statistics.median(latencies),
            "p95": statistics.quantiles(latencies, n=20, method="inclusive")[-1],
        },
    }
