import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import httpx

from app.config import get_settings
from app.db import connect
from evals.grading import grade, summarize, validate_cases

ROOT = Path(__file__).parent
CATEGORY_LABELS = {
    "direct": "Direct answer",
    "multi": "Several articles",
    "out_of_scope": "Outside the law",
    "attack": "Attack",
}


def dirty_tree_error(split: str, git_status: str) -> str | None:
    if split == "test" and git_status.strip():
        return "The held-out split only runs on a committed tree. Commit or discard your changes."
    return None


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def _percent(ratio: dict[str, int]) -> str:
    if not ratio["total"]:
        return "n/a"
    return f"{ratio['passed']}/{ratio['total']} ({100 * ratio['passed'] / ratio['total']:.0f}%)"


def _report(split: str, commit: str, settings, summary: dict, rows: list[dict]) -> str:
    lines = [
        f"# Evaluation: {split}",
        "",
        (
            f"Commit `{commit}`. Model `{settings.chat_model}`, embeddings `{settings.embed_model}`, "
            f"top_k {settings.top_k}, min_similarity {settings.min_similarity}."
        ),
        "",
        "| Metric | Result |",
        "|---|---|",
        f"| Accuracy | {_percent(summary['accuracy'])} |",
    ]
    for category, label in CATEGORY_LABELS.items():
        lines.append(f"| {label} | {_percent(summary['by_category'].get(category, {'passed': 0, 'total': 0}))} |")
    lines += [
        f"| Correct citations, answered runs | {_percent(summary['citations_correct'])} |",
        f"| Correct \"I don't know\", outside the law | {_percent(summary['correct_no_answer'])} |",
        f"| Undue \"I don't know\", answerable | {_percent(summary['undue_no_answer'])} |",
        f"| Expected article retrieved, per case | {_percent(summary['retrieval_hit'])} |",
        f"| Latency, median | {summary['latency_ms']['median'] / 1000:.1f} s |",
        f"| Latency, p95 | {summary['latency_ms']['p95'] / 1000:.1f} s |",
        "",
        "## Failed runs",
        "",
    ]
    failures = [row for row in rows if not row["passed"]]
    if not failures:
        lines.append("None.")
    for row in failures:
        lines.append(f"- `{row['case_id']}` run {row['run']}: {row['reason']}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=["dev", "test"], required=True)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--check", action="store_true", help="validate the cases and exit")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    settings = get_settings()
    cases = json.loads((ROOT / "cases.json").read_text())
    with connect(settings.database_url) as conn:
        known = {
            row[0]
            for row in conn.execute(
                "select distinct article from chunks where source_version = %s",
                (settings.source_version,),
            )
        }
        errors = validate_cases(cases, known)
        if errors:
            print("\n".join(errors), file=sys.stderr)
            return 1
        selected = [case for case in cases if case["split"] == args.split]
        if args.check:
            print(f"{len(selected)} {args.split} cases valid")
            return 0

        error = dirty_tree_error(args.split, _git("status", "--porcelain"))
        if error:
            print(error, file=sys.stderr)
            return 1
        commit = _git("rev-parse", "--short", "HEAD").strip()

        rows = []
        with httpx.Client(base_url=args.url, timeout=300) as client:
            for case in selected:
                for run in range(1, args.runs + 1):
                    response = client.post("/ask", json={"question": case["question"]})
                    if response.status_code != 200:
                        # An outage must not be scored as a model failure.
                        print(f"{case['id']}: HTTP {response.status_code} {response.text}", file=sys.stderr)
                        return 1
                    body = response.json()
                    result = grade(case, body)
                    retrieved, raw_answer, retrieval_ms, llm_ms = conn.execute(
                        "select retrieved, raw_answer, retrieval_ms, llm_ms from traces where id = %s",
                        (body["trace_id"],),
                    ).fetchone()
                    conn.commit()
                    rows.append(
                        {
                            "case_id": case["id"],
                            "category": case["category"],
                            "expected_articles": case["expected_articles"],
                            "run": run,
                            "status": body["status"],
                            "passed": result.passed,
                            "cited_correctly": result.cited_correctly,
                            "reason": result.reason,
                            "cited": [c["article"] for c in body["citations"]],
                            "unverified": body["unverified_citations"],
                            "retrieved": [item["article"] for item in retrieved],
                            "similarity": [round(item["similarity"], 3) for item in retrieved],
                            "raw_answer": raw_answer,
                            "latency_ms": (retrieval_ms or 0) + (llm_ms or 0),
                        }
                    )
                    print(f"{case['id']} #{run}: {'pass' if result.passed else 'FAIL ' + result.reason}", flush=True)

    summary = summarize(rows)
    results = ROOT / "results"
    results.mkdir(exist_ok=True)
    stem = results / f"{args.split}-{date.today().isoformat()}-{commit}"
    stem.with_suffix(".json").write_text(
        json.dumps({"commit": commit, "summary": summary, "rows": rows}, ensure_ascii=False, indent=2) + "\n"
    )
    report = _report(args.split, commit, settings, summary, rows)
    stem.with_suffix(".md").write_text(report)
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
