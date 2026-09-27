"""Baseline/optimized performance reporting for the evaluation suite (Week 9).

build_baseline_report(results) turns a list of evaluation.runner.
run_evaluation() result dicts into the aggregate report described in
docs/current-week.txt's Session 1: overall latency (avg/P50/P95),
per-stage average latency, LLM call counts, token usage, and quality
scores - so a run's cost/latency/quality trade-offs can be read at a
glance and diffed against a later "optimized" run.

Deliberately a pure function over already-collected result dicts: no
LLM calls, no subprocess, no file I/O. All reporting-arithmetic
decisions are covered by tests/test_evaluation_runner.py, not by a live
evaluation run.
"""
from __future__ import annotations

import math
from typing import Any


def _percentile(values: list[float], pct: float) -> float | None:
    """Nearest-rank percentile over a list of numbers.

    Returns None for an empty list rather than raising, since a report
    over zero timed items (e.g. every question errored or timed out) is
    a valid, if unfortunate, report to produce.
    """
    if not values:
        return None

    ordered = sorted(values)
    rank = math.ceil(pct / 100 * len(ordered))
    rank = max(1, min(rank, len(ordered)))
    return ordered[rank - 1]


def _avg(values: list[float]) -> float | None:
    """Arithmetic mean, or None for an empty list (see _percentile)."""
    return sum(values) / len(values) if values else None


def build_baseline_report(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate a list of evaluation result dicts into a baseline report.

    Only items carrying "timing_metrics" and "llm_usage" (i.e. items that
    actually completed a full pipeline run - excludes "timeout"/"error"
    status items, which never reach the point of producing an
    ExecutionTrace) contribute to the latency/LLM/token figures. Quality
    scores (score/score_sources) are averaged across all timed items the
    same way, since an untimed item has no meaningful score either.

    Returns a report dict shaped for both direct inspection and JSON
    serialization - see PROMPT/roadmap Session 1's example report layout.
    """
    timed_results = [r for r in results if r.get("timing_metrics") and r.get("llm_usage")]

    overall_latencies = [
        r["timing_metrics"]["trace"]["duration_ms"]
        for r in timed_results
        if r["timing_metrics"]["trace"]["duration_ms"] is not None
    ]

    stage_latencies: dict[str, list[float]] = {"planner": [], "worker": [], "reviewer": []}
    stage_llm_calls: dict[str, list[int]] = {"planner": [], "worker": [], "reviewer": []}
    total_input_tokens = 0
    total_output_tokens = 0
    total_llm_calls = 0

    for r in timed_results:
        timing = r["timing_metrics"]
        usage = r["llm_usage"]

        for stage in ("planner", "worker", "reviewer"):
            duration = timing[stage]["duration_ms"]
            if duration is not None:
                stage_latencies[stage].append(duration)

            stage_llm_calls[stage].append(usage[stage]["llm_calls"])

            token_usage = usage[stage]["token_usage"]
            if token_usage:
                total_input_tokens += token_usage.get("input_tokens", 0)
                total_output_tokens += token_usage.get("output_tokens", 0)

        total_llm_calls += usage.get("total_llm_calls", 0)

    scores = [r["score"] for r in timed_results if r.get("score") is not None]
    scores_sources = [r["score_sources"] for r in timed_results if r.get("score_sources") is not None]

    n_timed = len(timed_results)

    return {
        "questions": len(results),
        "evaluated": n_timed,
        "latency_ms": {
            "avg": _avg(overall_latencies),
            "p50": _percentile(overall_latencies, 50),
            "p95": _percentile(overall_latencies, 95),
        },
        "stage_latency_ms_avg": {
            stage: _avg(values) for stage, values in stage_latencies.items()
        },
        "scores": {
            "avg_answer_score": _avg(scores),
            "avg_retrieval_score": _avg(scores_sources),
        },
        "llm_calls": {
            "total": total_llm_calls,
            "avg_per_question": _avg([r["llm_usage"].get("total_llm_calls", 0) for r in timed_results]),
            "stage_avg": {stage: _avg(values) for stage, values in stage_llm_calls.items()},
        },
        "tokens": {
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_tokens": total_input_tokens + total_output_tokens,
            "avg_tokens_per_question": (
                (total_input_tokens + total_output_tokens) / n_timed if n_timed else None
            ),
        },
    }


def format_baseline_report_markdown(report: dict[str, Any], title: str = "Evaluation run") -> str:
    """Render build_baseline_report()'s output as the simple, human-readable
    table described in docs/current-week.txt (no dashboard, just numbers).
    """
    def fmt(value: float | None, suffix: str = "") -> str:
        return f"{value:.1f}{suffix}" if value is not None else "n/a"

    lines = [
        f"# {title}",
        "",
        f"Questions:            {report['questions']} ({report['evaluated']} evaluated)",
        f"Avg latency:          {fmt(report['latency_ms']['avg'], ' ms')}",
        f"P50 latency:          {fmt(report['latency_ms']['p50'], ' ms')}",
        f"P95 latency:          {fmt(report['latency_ms']['p95'], ' ms')}",
        "",
        f"Planner avg:          {fmt(report['stage_latency_ms_avg']['planner'], ' ms')}",
        f"Worker avg:           {fmt(report['stage_latency_ms_avg']['worker'], ' ms')}",
        f"Reviewer avg:         {fmt(report['stage_latency_ms_avg']['reviewer'], ' ms')}",
        "",
        f"Avg answer score:     {fmt(report['scores']['avg_answer_score'])}",
        f"Avg retrieval score:  {fmt(report['scores']['avg_retrieval_score'])}",
        "",
        f"Total LLM calls:      {report['llm_calls']['total']}",
        f"Avg LLM calls/Q:      {fmt(report['llm_calls']['avg_per_question'])}",
        f"  planner avg:        {fmt(report['llm_calls']['stage_avg']['planner'])}",
        f"  worker avg:         {fmt(report['llm_calls']['stage_avg']['worker'])}",
        f"  reviewer avg:       {fmt(report['llm_calls']['stage_avg']['reviewer'])}",
        "",
        f"Total tokens:         {report['tokens']['total_tokens']}",
        f"  input tokens:       {report['tokens']['total_input_tokens']}",
        f"  output tokens:      {report['tokens']['total_output_tokens']}",
        f"Avg tokens/Q:         {fmt(report['tokens']['avg_tokens_per_question'])}",
    ]
    return "\n".join(lines)
