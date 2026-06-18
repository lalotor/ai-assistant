"""Evaluation runner for retrieval assessment.

Invokes the AI assistant via its CLI interface (`python main.py --question ... --json`)
so that all initialisation logic (env validation, vector store, logging) is handled
by main.py and never duplicated here.
"""
import json
import os
import subprocess
import sys
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# Project root (one level up from evaluation/)
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_SCRIPT = os.path.join(ROOT_DIR, "main.py")


def ask_assistant(question: str) -> dict[str, Any]:
    """Send a question to the AI assistant via the CLI and return the JSON result.

    Args:
        question: The user question to evaluate.

    Returns:
        Parsed JSON dict with keys: user_input, plan, final_answer, review_feedback.

    Raises:
        RuntimeError: If the subprocess exits with a non-zero code.
        json.JSONDecodeError: If the output is not valid JSON.
    """
    result = subprocess.run(
        [sys.executable, MAIN_SCRIPT, "--question", question, "--json"],
        capture_output=True,
        text=True,
        cwd=ROOT_DIR,
        check=False
    )

    if result.returncode != 0:
        logger.error(
            "assistant_cli_failed",
            returncode=result.returncode,
            stderr=result.stderr.strip(),
        )
        raise RuntimeError(
            f"main.py exited with code {result.returncode}: {result.stderr.strip()}"
        )

    # The JSON output is the last line printed by main.py (--json flag)
    stdout_lines = result.stdout.strip().splitlines()
    json_line = stdout_lines[-1] if stdout_lines else ""
    return json.loads(json_line)


def run_evaluation(dataset_path: str | None = None) -> list[dict[str, Any]]:
    """Run the evaluation suite against the retrieval pipeline.

    Args:
        dataset_path: Path to the evaluation JSON file.
                      Defaults to evaluation/datasets/retrieval_eval.json.

    Returns:
        List of result dicts, one per evaluation item.
    """
    if dataset_path is None:
        dataset_path = os.path.join(
            ROOT_DIR, "evaluation", "datasets", "retrieval_eval.json"
        )

    with open(dataset_path, encoding="utf-8") as f:
        eval_set = json.load(f)

    results: list[dict[str, Any]] = []

    print(f"\n{'='*60}")
    print(f"🧪 Running evaluation  —  {len(eval_set)} question(s)")
    print(f"{'='*60}\n")

    for idx, item in enumerate(eval_set, start=1):
        question = item["question"]
        print(f"[{idx}/{len(eval_set)}] Q: {question[:70]}...")

        try:
            response = ask_assistant(question)
            answer = response["final_answer"].lower()

            # Keyword matching
            expected = item.get("expected_keywords", [])
            hits = [kw for kw in expected if kw.lower() in answer]
            score = len(hits) / len(expected) if expected else 1.0

            result = {
                "question": question,
                "answer": response["final_answer"],
                "plan": response.get("plan"),
                "expected_keywords": expected,
                "matched_keywords": hits,
                "score": score,
                "status": "pass" if score >= 0.5 else "fail",
            }
            print(f"   Keywords: {len(hits)}/{len(expected)} matched  (score: {score:.0%})")

        except Exception as exc:
            result = {
                "question": question,
                "answer": None,
                "error": str(exc),
                "score": 0.0,
                "status": "error",
            }
            print(f"   ❌ Error: {exc}")

        results.append(result)
        print()

    # Summary
    total = len(results)
    passed = sum(1 for r in results if r["status"] == "pass")
    failed = sum(1 for r in results if r["status"] == "fail")
    errors = sum(1 for r in results if r["status"] == "error")
    avg_score = sum(r["score"] for r in results) / total if total else 0.0

    print("="*60)
    print(f"📊 Results: {passed} passed, {failed} failed, {errors} errors  —  avg score: {avg_score:.0%}")
    print("="*60 + "\n")

    return results

if __name__ == "__main__":
    run_evaluation()
