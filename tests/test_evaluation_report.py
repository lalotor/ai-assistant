"""Unit tests for evaluation.report's build_baseline_report() and
format_baseline_report_markdown().

build_baseline_report(results) is a pure function over already-collected
evaluation.runner.run_evaluation() result dicts - no LLM calls, no
subprocess, no file I/O. These tests construct fixture result dicts
directly rather than running a live evaluation, per evaluation/report.py's
own module docstring.
"""
import pytest

from evaluation.report import build_baseline_report, format_baseline_report_markdown


def make_result(
    score=1.0,
    score_sources=1.0,
    trace_duration_ms=1000.0,
    planner_ms=200.0,
    worker_ms=600.0,
    reviewer_ms=200.0,
    planner_calls=1,
    worker_calls=1,
    reviewer_calls=1,
    planner_tokens=(100, 20),
    worker_tokens=(500, 80),
    reviewer_tokens=(150, 40),
) -> dict:
    """A complete, fully-timed evaluation result dict, matching the shape
    evaluation.runner.run_evaluation() actually produces."""

    def usage(calls, tokens):
        if tokens is None:
            return {"llm_calls": calls, "token_usage": None}
        input_tokens, output_tokens = tokens
        return {
            "llm_calls": calls,
            "token_usage": {"input_tokens": input_tokens, "output_tokens": output_tokens, "model": "gpt-5.4-mini"},
        }

    return {
        "score": score,
        "score_sources": score_sources,
        "status": "pass" if score >= 0.5 else "fail",
        "timing_metrics": {
            "trace": {"duration_ms": trace_duration_ms},
            "planner": {"duration_ms": planner_ms},
            "worker": {"duration_ms": worker_ms},
            "reviewer": {"duration_ms": reviewer_ms},
        },
        "llm_usage": {
            "planner": usage(planner_calls, planner_tokens),
            "worker": usage(worker_calls, worker_tokens),
            "reviewer": usage(reviewer_calls, reviewer_tokens),
            "total_llm_calls": planner_calls + worker_calls + reviewer_calls,
        },
    }


def make_timeout_result() -> dict:
    """A timeout/error item: no timing_metrics or llm_usage at all,
    matching what run_evaluation() actually produces for these statuses."""
    return {"status": "timeout", "score": 0.0, "score_sources": 0.0}


@pytest.mark.unit
class TestBuildBaselineReport:
    def test_computes_overall_avg_latency(self):
        results = [
            make_result(trace_duration_ms=1000.0),
            make_result(trace_duration_ms=3000.0),
        ]

        report = build_baseline_report(results)

        assert report["latency_ms"]["avg"] == 2000.0

    def test_computes_p50_and_p95_latency(self):
        results = [make_result(trace_duration_ms=ms) for ms in [100.0, 200.0, 300.0, 400.0, 500.0]]

        report = build_baseline_report(results)

        assert report["latency_ms"]["p50"] == 300.0
        assert report["latency_ms"]["p95"] == 500.0

    def test_computes_per_stage_average_latency(self):
        results = [
            make_result(planner_ms=100.0, worker_ms=500.0, reviewer_ms=100.0),
            make_result(planner_ms=300.0, worker_ms=700.0, reviewer_ms=300.0),
        ]

        report = build_baseline_report(results)

        assert report["stage_latency_ms_avg"]["planner"] == 200.0
        assert report["stage_latency_ms_avg"]["worker"] == 600.0
        assert report["stage_latency_ms_avg"]["reviewer"] == 200.0

    def test_computes_average_answer_and_retrieval_scores(self):
        results = [
            make_result(score=1.0, score_sources=0.5),
            make_result(score=0.5, score_sources=1.0),
        ]

        report = build_baseline_report(results)

        assert report["scores"]["avg_answer_score"] == 0.75
        assert report["scores"]["avg_retrieval_score"] == 0.75

    def test_counts_total_and_per_stage_average_llm_calls(self):
        results = [
            make_result(planner_calls=1, worker_calls=1, reviewer_calls=1),
            make_result(planner_calls=1, worker_calls=2, reviewer_calls=1),  # doc_retriever reranking call
        ]

        report = build_baseline_report(results)

        assert report["llm_calls"]["total"] == 3 + 4
        assert report["llm_calls"]["stage_avg"]["worker"] == 1.5
        assert report["llm_calls"]["avg_per_question"] == 3.5

    def test_sums_input_and_output_tokens_across_all_stages_and_questions(self):
        results = [
            make_result(planner_tokens=(100, 20), worker_tokens=(500, 80), reviewer_tokens=(150, 40)),
        ]

        report = build_baseline_report(results)

        assert report["tokens"]["total_input_tokens"] == 750
        assert report["tokens"]["total_output_tokens"] == 140
        assert report["tokens"]["total_tokens"] == 890
        assert report["tokens"]["avg_tokens_per_question"] == 890

    def test_excludes_missing_token_usage_from_totals_without_raising(self):
        result = make_result(planner_tokens=None)

        report = build_baseline_report([result])

        # planner contributed 0 tokens, worker+reviewer still counted
        assert report["tokens"]["total_input_tokens"] == 650
        assert report["tokens"]["total_output_tokens"] == 120

    def test_excludes_timeout_and_error_items_from_all_aggregates(self):
        """Timeout/error items never reach an ExecutionTrace, so they carry
        no timing_metrics/llm_usage at all - they must not raise a
        KeyError and must not skew the averages."""
        results = [
            make_result(trace_duration_ms=1000.0, score=1.0),
            make_timeout_result(),
        ]

        report = build_baseline_report(results)

        assert report["questions"] == 2
        assert report["evaluated"] == 1
        assert report["latency_ms"]["avg"] == 1000.0

    def test_empty_results_list_does_not_raise(self):
        report = build_baseline_report([])

        assert report["questions"] == 0
        assert report["evaluated"] == 0
        assert report["latency_ms"]["avg"] is None
        assert report["latency_ms"]["p50"] is None

    def test_all_timeout_results_produces_a_report_with_no_timed_data(self):
        report = build_baseline_report([make_timeout_result(), make_timeout_result()])

        assert report["questions"] == 2
        assert report["evaluated"] == 0
        assert report["latency_ms"]["avg"] is None
        assert report["tokens"]["total_tokens"] == 0


@pytest.mark.unit
class TestFormatBaselineReportMarkdown:
    def test_renders_a_human_readable_report_with_the_given_title(self):
        report = build_baseline_report([make_result()])

        text = format_baseline_report_markdown(report, title="Baseline run")

        assert "# Baseline run" in text
        assert "Avg latency:" in text
        assert "Total LLM calls:" in text

    def test_renders_na_for_missing_values_without_raising(self):
        report = build_baseline_report([])

        text = format_baseline_report_markdown(report, title="Empty run")

        assert "n/a" in text
