"""CLI to turn an evaluation results file into a tracked baseline/optimized
performance report (Week 9, Session 1).

Unlike evaluation/results/*.json (gitignored raw run output, one file per
run), reports written here are tracked, since Session 2 needs a stable
baseline to diff future "optimized" runs against - an untracked baseline
would not survive a fresh clone or branch switch.

Usage:
    python -m evaluation.build_report --results evaluation/results/eval_<ts>.json --title "Baseline run" --name baseline
    python -m evaluation.build_report --title "Baseline run" --name baseline   # uses the most recent results file
"""
from __future__ import annotations

import argparse
import glob
import json
import os

from evaluation.report import build_baseline_report, format_baseline_report_markdown

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(ROOT_DIR, "evaluation", "results")
REPORTS_DIR = os.path.join(ROOT_DIR, "evaluation", "reports")


def _latest_results_file() -> str:
    """The most recently created file in evaluation/results/, matching the
    eval_<timestamp>.json naming evaluation.runner.run_evaluation() writes."""
    candidates = sorted(glob.glob(os.path.join(RESULTS_DIR, "eval_*.json")))
    if not candidates:
        raise FileNotFoundError(
            f"No results files found in {RESULTS_DIR}. Run the evaluation suite first "
            "(see the run-and-triage-evaluation skill), then re-run this command."
        )
    return candidates[-1]


def _load_results(results_path: str) -> list[dict]:
    with open(results_path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("results", data)  # tolerate a bare results list too


def build_report_from_results_file(results_path: str, name: str, title: str) -> tuple[str, str]:
    """Build a baseline report from a single results file and write it as
    both JSON and Markdown under evaluation/reports/<name>.{json,md}.

    Returns (json_path, md_path).
    """
    return build_report_from_results_files([results_path], name=name, title=title)


def build_report_from_results_files(results_paths: list[str], name: str, title: str) -> tuple[str, str]:
    """Build one baseline report from one or more results files, merging
    every result across all of them before aggregating.

    Merging (rather than averaging per-run reports) is deliberate: the
    roadmap calls for running the suite "several times" to get a stable
    baseline, and merging every individual question's result before
    computing P50/P95 gives an honest percentile over the combined sample,
    which averaging three separate P95s would not.

    Returns (json_path, md_path).
    """
    results: list[dict] = []
    for path in results_paths:
        results.extend(_load_results(path))

    report = build_baseline_report(results)
    report["source_results_files"] = [os.path.relpath(p, ROOT_DIR) for p in results_paths]

    os.makedirs(REPORTS_DIR, exist_ok=True)
    json_path = os.path.join(REPORTS_DIR, f"{name}.json")
    md_path = os.path.join(REPORTS_DIR, f"{name}.md")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(format_baseline_report_markdown(report, title=title))
        f.write("\n")

    return json_path, md_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", nargs="+", help="One or more evaluation/results/eval_*.json files to merge. Defaults to the most recent one.")
    parser.add_argument("--name", default="baseline", help="Base filename (without extension) for the report. Default: baseline")
    parser.add_argument("--title", default="Evaluation run", help="Human-readable title for the Markdown report.")
    args = parser.parse_args()

    results_paths = args.results or [_latest_results_file()]
    json_path, md_path = build_report_from_results_files(results_paths, name=args.name, title=args.title)

    print(f"Report written to:\n  {json_path}\n  {md_path}")


if __name__ == "__main__":
    main()
