"""Unit tests for evaluation.compare's repeated-run comparison report."""
import json

import pytest

from evaluation.compare import (
    compare_results,
    format_comparison_markdown,
    load_results_files,
    write_comparison_report,
)


def make_result(
    question,
    *,
    score=1.0,
    score_sources=1.0,
    duration_ms=1000.0,
    llm_calls=3,
    tokens=300,
    revision_count=0,
    review_outcome=None,
) -> dict:
    """A complete result row matching evaluation.runner's focused shape."""
    return {
        "question": question,
        "score": score,
        "score_sources": score_sources,
        "timing_metrics": {
            "trace": {"duration_ms": duration_ms},
        },
        "llm_usage": {
            "planner": {
                "llm_calls": 1,
                "token_usage": {"input_tokens": tokens, "output_tokens": 0},
            },
            "worker": {"llm_calls": 1, "token_usage": None},
            "reviewer": {"llm_calls": 1, "token_usage": None},
            "total_llm_calls": llm_calls,
        },
        "revision_count": revision_count,
        "review_outcome": review_outcome,
    }


@pytest.mark.unit
class TestCompareResults:
    def test_averages_repeated_runs_per_question_and_reports_regressions(self):
        baseline = [
            make_result("q1", score=1.0, duration_ms=1000.0, review_outcome="approved"),
            make_result("q1", score=0.0, duration_ms=3000.0, review_outcome="approved"),
            make_result("q2", score=1.0, duration_ms=1000.0, review_outcome="approved"),
            make_result("q2", score=1.0, duration_ms=1000.0, review_outcome="approved"),
        ]
        revision = [
            make_result(
                "q1",
                score=1.0,
                duration_ms=2000.0,
                llm_calls=4,
                tokens=400,
                revision_count=1,
                review_outcome="revised",
            ),
            make_result(
                "q1",
                score=1.0,
                duration_ms=4000.0,
                llm_calls=4,
                tokens=400,
                revision_count=1,
                review_outcome="revised",
            ),
            make_result(
                "q2",
                score=0.0,
                duration_ms=2000.0,
                llm_calls=4,
                tokens=400,
                revision_count=1,
                review_outcome="budget_exhausted",
            ),
            make_result(
                "q2",
                score=0.0,
                duration_ms=2000.0,
                llm_calls=4,
                tokens=400,
                revision_count=1,
                review_outcome="budget_exhausted",
            ),
        ]

        comparison = compare_results(baseline, revision)

        assert comparison["questions"] == 2
        assert comparison["runs"] == {"baseline": 4, "revision": 4}
        assert comparison["answer_score"]["baseline"] == 0.75
        assert comparison["answer_score"]["revision"] == 0.5
        assert comparison["answer_score"]["delta"] == -0.25
        assert comparison["answer_score"]["improved"] == 1
        assert comparison["answer_score"]["unchanged"] == 0
        assert comparison["answer_score"]["degraded"] == 1

        assert comparison["latency_ms"]["baseline"]["avg"] == 1500.0
        assert comparison["latency_ms"]["revision"]["avg"] == 2500.0
        assert comparison["latency_ms"]["delta_avg_ms"] == 1000.0

        assert comparison["llm_calls"]["baseline"]["total"] == 12
        assert comparison["llm_calls"]["revision"]["total"] == 16
        assert comparison["llm_calls"]["delta_avg_per_question"] == 1.0

        assert comparison["tokens"]["baseline"]["total"] == 1200
        assert comparison["tokens"]["revision"]["total"] == 1600
        assert comparison["tokens"]["delta_avg_per_question"] == 100.0

        by_question = {row["question"]: row for row in comparison["per_question"]}
        assert by_question["q1"]["score_delta"] == 0.5
        assert by_question["q1"]["score_status"] == "improved"
        assert by_question["q1"]["revision"]["revision_attempted_runs"] == 2
        assert by_question["q1"]["revision"]["review_outcomes"] == {"revised": 2}
        assert by_question["q2"]["score_delta"] == -1.0
        assert by_question["q2"]["score_status"] == "degraded"
        assert by_question["q2"]["revision"]["review_outcomes"] == {
            "budget_exhausted": 2
        }

        assert comparison["review"]["revision"] == {
            "revisions_attempted": 4,
            "revision_count_total": 4,
            "answers_changed": 0,
            "questions_with_revision": 2,
            "outcomes": {"budget_exhausted": 2, "revised": 2},
        }

    def test_marks_a_question_missing_when_one_mode_lacks_it(self):
        comparison = compare_results(
            [make_result("baseline-only", score=1.0)],
            [make_result("revision-only", score=0.0)],
        )

        baseline_only = comparison["per_question"][0]
        revision_only = comparison["per_question"][1]
        assert baseline_only["score_status"] == "missing"
        assert baseline_only["revision"] is None
        assert revision_only["score_status"] == "missing"
        assert revision_only["baseline"] is None
        assert comparison["answer_score"]["missing"] == 2

    def test_no_revision_attempts_is_reported_explicitly(self):
        comparison = compare_results(
            [make_result("q", review_outcome="approved")],
            [make_result("q", review_outcome="approved")],
        )

        assert comparison["review"]["revision"]["revisions_attempted"] == 0
        assert comparison["review"]["revision"]["revision_count_total"] == 0
        assert comparison["review"]["revision"]["outcomes"] == {"approved": 1}


@pytest.mark.unit
class TestComparisonReport:
    def test_renders_summary_per_question_table_and_outcomes(self):
        comparison = compare_results(
            [make_result("q1", score=0.0, review_outcome="approved")],
            [
                make_result(
                    "q1",
                    score=1.0,
                    revision_count=1,
                    review_outcome="revised",
                )
            ],
        )

        report = format_comparison_markdown(comparison, title="Week 11 comparison")

        assert report.startswith("# Week 11 comparison")
        assert "Answer score:" in report
        assert "improved 1, unchanged 0, degraded 0" in report
        assert "Latency P50:" in report
        assert "Review outcomes:" in report
        assert "| q1 |" in report
        assert "revised=1" in report
        assert "Quality signal: 1 improved" in report

    def test_loads_one_or_more_result_files(self, tmp_path):
        first = tmp_path / "first.json"
        second = tmp_path / "second.json"
        first.write_text(
            json.dumps({"results": [make_result("q1")]}),
            encoding="utf-8",
        )
        second.write_text(
            json.dumps({"results": [make_result("q2")]}),
            encoding="utf-8",
        )

        results = load_results_files([str(first), str(tmp_path / "*.json")])

        assert [result["question"] for result in results] == ["q1", "q1", "q2"]

    def test_rejects_a_run_file_with_the_wrong_declared_mode(self, tmp_path):
        path = tmp_path / "revision.json"
        path.write_text(
            json.dumps(
                {
                    "summary": {"mode": "revision"},
                    "results": [make_result("q1")],
                }
            ),
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="Expected a single_pass"):
            load_results_files([str(path)], expected_mode="single_pass")

    def test_writes_json_and_markdown_reports(self, tmp_path):
        comparison = compare_results(
            [make_result("q1", review_outcome="approved")],
            [make_result("q1", review_outcome="approved")],
        )

        json_path, markdown_path = write_comparison_report(
            comparison,
            output_dir=str(tmp_path),
            name="comparison",
            title="Comparison title",
        )

        payload = json.loads((tmp_path / "comparison.json").read_text())
        assert payload["questions"] == 1
        assert payload["runs"] == {"baseline": 1, "revision": 1}
        assert (tmp_path / "comparison.md").read_text().startswith(
            "# Comparison title"
        )
        assert json_path.endswith("comparison.json")
        assert markdown_path.endswith("comparison.md")
