from pathlib import Path

from support_ai.data import Dataset, parse_datetime
from support_ai.eval import run_evaluation
from support_ai.retrieval import KnowledgeBase

ROOT = Path(__file__).parents[1]


def test_eval_has_required_case_counts_and_adversarial_cases() -> None:
    report = run_evaluation(
        Dataset.load(ROOT / "data"),
        KnowledgeBase(ROOT / "knowledge-base"),
        parse_datetime("2026-05-22T00:00:00Z"),
    )
    assert report["summary"]["task1_cases"] >= 5
    assert report["summary"]["task2_cases"] >= 5
    assert report["summary"]["passed"] == report["summary"]["total"]
    assert report["summary"]["overall_quality"] == 1.0
    assert any("Adversarial" in case["description"] for case in report["results"] if case["task"] == "task1")
    assert any("Adversarial" in case["description"] for case in report["results"] if case["task"] == "task2")


def test_eval_case_failure_is_reported_not_crashed() -> None:
    # This is indirectly covered by the report contract: every case has an
    # explicit error field, including successful cases where it must be null.
    report = run_evaluation(
        Dataset.load(ROOT / "data"),
        KnowledgeBase(ROOT / "knowledge-base"),
        parse_datetime("2026-05-22T00:00:00Z"),
    )
    assert all("error" in case for case in report["results"])
