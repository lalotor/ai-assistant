"""Compare single-pass and revision-enabled evaluation runs.

The comparison is a pure function over already-collected result dicts,
plus a small CLI that loads one or more results files per mode and writes
a tracked Markdown/JSON report. This keeps the evaluation runner and
reporting layer separate from the experiment's analysis.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import argparse
import glob
import json
import os
from typing import Any

from evaluation.report import _avg, build_baseline_report, result_token_totals

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(ROOT_DIR, "evaluation", "reports")


def load_results_files(
    paths: list[str],
    *,
    expected_mode: str | None = None,
) -> list[dict[str, Any]]:
    """Load result dicts from one or more run files.

    A path containing ``*`` is expanded as a glob; this lets a caller
    compare a set of repeated runs without listing every filename. When
    ``expected_mode`` is supplied, a file whose summary declares a different
    mode is rejected so a single-pass run cannot be mislabeled as revision
    (or vice versa). Older files without a mode remain readable.
    """
    results: list[dict[str, Any]] = []
    for path in paths:
        matches = (
            sorted(glob.glob(path))
            if any(ch in path for ch in "*?[")
            else [path]
        )
        if not matches:
            raise FileNotFoundError(f"No evaluation results matched: {path}")
        for match in matches:
            with open(match, encoding="utf-8") as f:
                data = json.load(f)
            mode = (data.get("summary") or {}).get("mode")
            if expected_mode is not None and mode is not None and mode != expected_mode:
                raise ValueError(
                    f"Expected a {expected_mode} result file, but {match} "
                    f"declares mode={mode!r}."
                )
            results.extend(data.get("results", []))
    return results


def compare_results(
    baseline_results: list[dict[str, Any]],
    revision_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a per-question and aggregate comparison of two evaluation modes."""
    baseline_by_question = _group_by_question(baseline_results)
    revision_by_question = _group_by_question(revision_results)
    questions = list(baseline_by_question)
    questions.extend(q for q in revision_by_question if q not in baseline_by_question)

    per_question = [
        _compare_question(
            question,
            baseline_by_question.get(question, []),
            revision_by_question.get(question, []),
        )
        for question in questions
    ]

    baseline_report = build_baseline_report(baseline_results)
    revision_report = build_baseline_report(revision_results)

    answer_score = _score_summary(
        baseline_results, revision_results, "score", per_question, "score_status"
    )
    retrieval_score = _score_summary(
        baseline_results,
        revision_results,
        "score_sources",
        per_question,
        "retrieval_status",
    )

    return {
        "questions": len(questions),
        "runs": {
            "baseline": len(baseline_results),
            "revision": len(revision_results),
        },
        "answer_score": answer_score,
        "retrieval_score": retrieval_score,
        "latency_ms": {
            "baseline": baseline_report["latency_ms"],
            "revision": revision_report["latency_ms"],
            "delta_avg_ms": _delta(
                revision_report["latency_ms"]["avg"],
                baseline_report["latency_ms"]["avg"],
            ),
        },
        "llm_calls": {
            "baseline": {
                "total": baseline_report["llm_calls"]["total"],
                "avg_per_question": baseline_report["llm_calls"]["avg_per_question"],
                "avg_per_run": _per_run(
                    baseline_report["llm_calls"]["total"], baseline_results
                ),
            },
            "revision": {
                "total": revision_report["llm_calls"]["total"],
                "avg_per_question": revision_report["llm_calls"]["avg_per_question"],
                "avg_per_run": _per_run(
                    revision_report["llm_calls"]["total"], revision_results
                ),
            },
            "delta_avg_per_question": _delta(
                revision_report["llm_calls"]["avg_per_question"],
                baseline_report["llm_calls"]["avg_per_question"],
            ),
        },
        "tokens": {
            "baseline": {
                "total": baseline_report["tokens"]["total_tokens"],
                "avg_per_question": baseline_report["tokens"]["avg_tokens_per_question"],
                "avg_per_run": _per_run(
                    baseline_report["tokens"]["total_tokens"], baseline_results
                ),
            },
            "revision": {
                "total": revision_report["tokens"]["total_tokens"],
                "avg_per_question": revision_report["tokens"]["avg_tokens_per_question"],
                "avg_per_run": _per_run(
                    revision_report["tokens"]["total_tokens"], revision_results
                ),
            },
            "delta_avg_per_question": _delta(
                revision_report["tokens"]["avg_tokens_per_question"],
                baseline_report["tokens"]["avg_tokens_per_question"],
            ),
        },
        "review": {
            "baseline": baseline_report["review"],
            "revision": {
                **revision_report["review"],
                "questions_with_revision": sum(
                    1
                    for row in per_question
                    if (row["revision"] or {}).get("revision_attempted_runs", 0) > 0
                ),
            },
        },
        "per_question": per_question,
    }


def format_comparison_markdown(
    comparison: dict[str, Any],
    title: str = "Single-pass vs revision-enabled evaluation",
) -> str:
    """Render the comparison as a concise, tracked Markdown report."""
    def fmt(value: float | None, suffix: str = "", digits: int = 2) -> str:
        return f"{value:.{digits}f}{suffix}" if value is not None else "n/a"

    def delta(value: float | None, suffix: str = "", digits: int = 2) -> str:
        return f"{value:+.{digits}f}{suffix}" if value is not None else "n/a"

    answer = comparison["answer_score"]
    retrieval = comparison["retrieval_score"]
    latency = comparison["latency_ms"]
    calls = comparison["llm_calls"]
    tokens = comparison["tokens"]
    review = comparison["review"]

    lines = [
        f"# {title}",
        "",
        (
            f"Questions: {comparison['questions']} unique; "
            f"runs: {comparison['runs']['baseline']} baseline, "
            f"{comparison['runs']['revision']} revision"
        ),
        "",
        "## Summary",
        "",
        (
            f"Answer score:      {fmt(answer['baseline'])} -> "
            f"{fmt(answer['revision'])} ({delta(answer['delta'])})  "
            f"[improved {answer['improved']}, unchanged {answer['unchanged']}, "
            f"degraded {answer['degraded']}]"
        ),
        (
            f"Retrieval score:   {fmt(retrieval['baseline'])} -> "
            f"{fmt(retrieval['revision'])} ({delta(retrieval['delta'])})  "
            f"[improved {retrieval['improved']}, unchanged {retrieval['unchanged']}, "
            f"degraded {retrieval['degraded']}]"
        ),
        (
            f"Latency avg:       {fmt(latency['baseline']['avg'], ' ms', 1)} -> "
            f"{fmt(latency['revision']['avg'], ' ms', 1)} "
            f"({delta(latency['delta_avg_ms'], ' ms', 1)})"
        ),
        (
            f"Latency P50:       {fmt(latency['baseline']['p50'], ' ms', 1)} -> "
            f"{fmt(latency['revision']['p50'], ' ms', 1)}"
        ),
        (
            f"Latency P95:       {fmt(latency['baseline']['p95'], ' ms', 1)} -> "
            f"{fmt(latency['revision']['p95'], ' ms', 1)}"
        ),
        (
            f"LLM calls:         {calls['baseline']['total']} -> "
            f"{calls['revision']['total']} total; "
            f"{fmt(calls['baseline']['avg_per_question'])} -> "
            f"{fmt(calls['revision']['avg_per_question'])} per question "
            f"({delta(calls['delta_avg_per_question'])})"
        ),
        (
            f"Tokens:            {tokens['baseline']['total']} -> "
            f"{tokens['revision']['total']} total; "
            f"{fmt(tokens['baseline']['avg_per_question'], '', 0)} -> "
            f"{fmt(tokens['revision']['avg_per_question'], '', 0)} per question "
            f"({delta(tokens['delta_avg_per_question'], '', 0)})"
        ),
        (
            "Review outcomes:   baseline: "
            f"{_format_outcomes(review['baseline']['outcomes'])}; revision: "
            f"{_format_outcomes(review['revision']['outcomes'])}"
        ),
        (
            "Revision attempts: "
            f"{review['revision']['revisions_attempted']} across revision runs "
            f"on {review['revision']['questions_with_revision']} of "
            f"{comparison['questions']} questions; final answers changed vs "
            f"draft: {review['revision'].get('answers_changed', 0)}"
        ),
        "",
        "## Per-question",
        "",
        (
            "| Question | Base score | Rev score | Δ score | Base retrieval | "
            "Rev retrieval | Δ retrieval | Δ latency ms | Δ calls | Δ tokens | "
            "Rev count | Changed | Outcome |"
        ),
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]

    for row in comparison["per_question"]:
        baseline = row["baseline"] or {}
        revision = row["revision"] or {}
        lines.append(
            "| {question} | {base_score} | {rev_score} | {d_score} | "
            "{base_retrieval} | {rev_retrieval} | {d_retrieval} | "
            "{d_latency} | {d_calls} | {d_tokens} | {rev_count} | "
            "{changed} | {outcome} |".format(
                question=_escape(row["question"]),
                base_score=fmt(baseline.get("score")),
                rev_score=fmt(revision.get("score")),
                d_score=delta(row.get("score_delta")),
                base_retrieval=fmt(baseline.get("score_sources")),
                rev_retrieval=fmt(revision.get("score_sources")),
                d_retrieval=delta(row.get("retrieval_delta")),
                d_latency=delta(row.get("latency_delta_ms"), "", 0),
                d_calls=delta(row.get("llm_calls_delta"), "", 2),
                d_tokens=delta(row.get("tokens_delta"), "", 0),
                rev_count=revision.get("revision_attempted_runs", 0)
                if revision
                else 0,
                changed=revision.get("answers_changed", 0) if revision else 0,
                outcome=_format_outcomes(revision.get("review_outcomes", {})),
            )
        )

    lines.extend([
        "",
        "## Reading",
        "",
        (
            f"Quality signal: {answer['improved']} improved, "
            f"{answer['unchanged']} unchanged, {answer['degraded']} degraded "
            "on keyword-based answer score."
        ),
        (
            "Cost signal: revision adds one revision call and one final-review "
            "call only on runs where the reviewer requests revision."
        ),
        (
            "Changed counts final answers that differ from the Worker draft; "
            "this includes single-pass reviewer edits as well as revisions."
        ),
        (
            "Caveat: keyword/source overlap is a proxy for answer quality; "
            "inspect the raw result files for representative answers before "
            "making a default-on decision."
        ),
    ])
    return "\n".join(lines)


def write_comparison_report(
    comparison: dict[str, Any],
    *,
    output_dir: str = REPORTS_DIR,
    name: str = "revision_comparison",
    title: str = "Single-pass vs revision-enabled evaluation",
) -> tuple[str, str]:
    """Write the JSON and Markdown comparison reports; return their paths."""
    os.makedirs(output_dir, exist_ok=True)
    json_path = os.path.join(output_dir, f"{name}.json")
    markdown_path = os.path.join(output_dir, f"{name}.md")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(comparison, f, indent=2)
    with open(markdown_path, "w", encoding="utf-8") as f:
        f.write(format_comparison_markdown(comparison, title=title))

    return json_path, markdown_path


def _group_by_question(results: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        question = result.get("question")
        if question:
            grouped[question].append(result)
    return dict(grouped)


def _compare_question(
    question: str,
    baseline_runs: list[dict[str, Any]],
    revision_runs: list[dict[str, Any]],
) -> dict[str, Any]:
    baseline = _per_question_metrics(baseline_runs)
    revision = _per_question_metrics(revision_runs)
    baseline_values = baseline or {}
    revision_values = revision or {}

    score_delta = _delta(
        revision_values.get("score"), baseline_values.get("score")
    )
    retrieval_delta = _delta(
        revision_values.get("score_sources"), baseline_values.get("score_sources")
    )
    latency_delta = _delta(
        revision_values.get("duration_ms"), baseline_values.get("duration_ms")
    )

    return {
        "question": question,
        "baseline": baseline,
        "revision": revision,
        "score_delta": score_delta,
        "score_status": _status(score_delta),
        "retrieval_delta": retrieval_delta,
        "retrieval_status": _status(retrieval_delta),
        "latency_delta_ms": latency_delta,
        "llm_calls_delta": _delta(
            revision_values.get("llm_calls"), baseline_values.get("llm_calls")
        ),
        "tokens_delta": _delta(
            revision_values.get("tokens"), baseline_values.get("tokens")
        ),
    }


def _per_question_metrics(runs: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not runs:
        return None

    timed = [
        r for r in runs
        if r.get("timing_metrics") and r.get("llm_usage")
    ]
    scores = [r["score"] for r in runs if r.get("score") is not None]
    retrieval_scores = [
        r["score_sources"] for r in runs if r.get("score_sources") is not None
    ]
    durations = [
        r["timing_metrics"]["trace"]["duration_ms"]
        for r in timed
        if r["timing_metrics"]["trace"].get("duration_ms") is not None
    ]
    calls = [r["llm_usage"].get("total_llm_calls", 0) for r in timed]
    tokens = [sum(result_token_totals(r)) for r in timed]
    outcomes = Counter(
        r.get("review_outcome") for r in runs if r.get("review_outcome")
    )
    revision_counts = [r.get("revision_count", 0) for r in runs]

    return {
        "runs": len(runs),
        "score": _avg(scores),
        "score_sources": _avg(retrieval_scores),
        "duration_ms": _avg(durations),
        "llm_calls": _avg(calls),
        "tokens": _avg(tokens),
        "revision_attempted_runs": sum(1 for count in revision_counts if count > 0),
        "revision_count_avg": _avg([float(count) for count in revision_counts]),
        "answers_changed": sum(1 for r in runs if r.get("answer_changed")),
        "review_outcomes": dict(sorted(outcomes.items())),
    }


def _score_summary(
    baseline_results: list[dict[str, Any]],
    revision_results: list[dict[str, Any]],
    field: str,
    per_question: list[dict[str, Any]],
    status_field: str,
) -> dict[str, Any]:
    baseline = _avg([
        r[field] for r in baseline_results if r.get(field) is not None
    ])
    revision = _avg([
        r[field] for r in revision_results if r.get(field) is not None
    ])
    statuses = Counter(row[status_field] for row in per_question)
    return {
        "baseline": baseline,
        "revision": revision,
        "delta": _delta(revision, baseline),
        "improved": statuses.get("improved", 0),
        "unchanged": statuses.get("unchanged", 0),
        "degraded": statuses.get("degraded", 0),
        "missing": statuses.get("missing", 0),
    }


def _per_run(total: int | None, results: list[dict[str, Any]]) -> float | None:
    return total / len(results) if results and total is not None else None


def _delta(new: float | int | None, old: float | int | None) -> float | None:
    if new is None or old is None:
        return None
    return float(new) - float(old)


def _status(delta: float | None) -> str:
    if delta is None:
        return "missing"
    if delta > 0:
        return "improved"
    if delta < 0:
        return "degraded"
    return "unchanged"


def _format_outcomes(outcomes: dict[str, int]) -> str:
    if not outcomes:
        return "n/a"
    return ", ".join(f"{name}={count}" for name, count in sorted(outcomes.items()))


def _escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare single-pass and revision-enabled evaluation runs."
    )
    parser.add_argument(
        "--baseline",
        nargs="+",
        required=True,
        help="One or more single-pass result files (globs allowed).",
    )
    parser.add_argument(
        "--revision",
        nargs="+",
        required=True,
        help="One or more revision-enabled result files (globs allowed).",
    )
    parser.add_argument(
        "--output-dir",
        default=REPORTS_DIR,
        help="Directory for the generated JSON/Markdown report.",
    )
    parser.add_argument(
        "--name",
        default="revision_comparison",
        help="Output filename stem (without extension).",
    )
    parser.add_argument(
        "--title",
        default="Single-pass vs revision-enabled evaluation",
        help="Markdown report title.",
    )
    args = parser.parse_args()

    comparison = compare_results(
        load_results_files(args.baseline, expected_mode="single_pass"),
        load_results_files(args.revision, expected_mode="revision"),
    )
    json_path, markdown_path = write_comparison_report(
        comparison,
        output_dir=args.output_dir,
        name=args.name,
        title=args.title,
    )
    print(f"Wrote {json_path} and {markdown_path}")


if __name__ == "__main__":
    main()
