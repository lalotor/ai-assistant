"""Evaluation runner for retrieval assessment.

Invokes the AI assistant via its CLI interface (`python main.py --question ... --json`)
so that all initialisation logic (env validation, vector store, logging) is handled
by main.py and never duplicated here.
"""
from datetime import datetime
import json
import os
import subprocess
import sys
from typing import Any
import structlog
from dotenv import load_dotenv

# Load environment variables FIRST before any validation
# This ensures .env file values (like OPENAI_API_KEY) are available
load_dotenv()

from app.config.logging_config import configure_logging
from app.config.env_validator import validate_environment

validated_env = validate_environment(verbose=True)

configure_logging(
    log_level=validated_env.get("LOG_LEVEL", "INFO"),
    json_logs=validated_env.get("JSON_LOGS", "false").lower() == "true",
    enable_file_logging=validated_env.get("ENABLE_FILE_LOGGING", "false").lower() == "true",
    log_file_path=validated_env.get("LOG_FILE_PATH", "logs/app.log")
)

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

    logger.info(
        "run_evaluation_started",
        questions=len(eval_set)
    )
    
    for idx, item in enumerate(eval_set, start=1):
        question = item["question"]
        logger.info(
            "evaluating_question",
            progression=f"[{idx}/{len(eval_set)}]",
            Q=question[:100]
        )

        try:
            response = ask_assistant(question)
            answer = response["final_answer"].lower()
            retrieved_sources = response.get("retrieved_sources", [])

            # Extract trace fields from the JSON output
            selected_tool = response.get("selected_tool")
            tool_input = response.get("tool_input")
            tool_output = response.get("tool_output")
            draft_answer = response.get("draft_answer")
            review_feedback = response.get("review_feedback")

            # Keyword matching
            expected = item.get("expected_keywords", [])
            hits = [kw for kw in expected if kw.lower() in answer]
            score = len(hits) / len(expected) if expected else 1.0

            # Files matching
            expected_sources = item.get("expected_sources", [])
            hits_sources = []
            score_sources = 0.0
            retrieved_sources_list = []
            if retrieved_sources:
                retrieved_set = {s.lower() for s in retrieved_sources}
                hits_sources = [src for src in expected_sources if src.lower() in retrieved_set]
                score_sources = len(hits_sources) / len(expected_sources) if expected_sources else 1.0
                retrieved_sources_list = list(retrieved_sources)

            result = {
                "question": question,
                "answer": response["final_answer"],
                "plan": response.get("plan"),
                "selected_tool": selected_tool,
                "tool_input": tool_input,
                "tool_output": tool_output,
                "draft_answer": draft_answer,
                "review_feedback": review_feedback,
                "retrieved_sources": retrieved_sources_list,
                "expected_keywords": expected,
                "matched_keywords": hits,
                "expected_sources": expected_sources,
                "matched_sources": hits_sources,
                "score": score,
                "score_sources": score_sources,
                "status": "pass" if score >= 0.5 else "fail",
                "failure_type": classify_failure(item, response, score, score_sources)
            }
            logger.info(
                "evaluation_result",
                score=f"{len(hits)}/{len(expected)} matched (score: {score:.0%})",
                score_sources=f"{len(hits_sources)}/{len(expected_sources)} matched (score: {score_sources:.0%})",
                failure_type=result["failure_type"]
            )

        except Exception as exc:
            result = {
                "question": question,
                "answer": None,
                "error": str(exc),
                "score": 0.0,
                "score_sources": 0.0,
                "status": "error",
            }
            logger.error(
                "evaluation_error",
                error=str(exc),
                error_type=type(exc).__name__,
                exc_info=True
            )

        results.append(result)

    save_evaluation_results(results)

    return results

def classify_failure(item: dict, response: dict, score: float, score_sources: float) -> str | None:
    """Classify the failure type for a failed evaluation item."""
    if score >= 0.5:
        return None  # Not a failure

    category = item.get("category", "")
    selected_tool = response.get("selected_tool", "")
    tool_output = response.get("final_answer", "")
    expected_sources = item.get("expected_sources", [])

    # 1. Tool crashed
    if "Error executing" in tool_output or "Error:" in tool_output:
        return "tool_failure"

    # 2. Wrong tool selected
    if category and selected_tool and category != selected_tool:
        return "planner_failure"

    # 3. Expected docs don't exist in corpus
    if expected_sources and not all(os.path.exists(s) for s in expected_sources):
        return "missing_context"

    # 4. Right docs exist but weren't retrieved
    if expected_sources and score_sources < 0.5:
        return "retrieval_failure"

    # 5. Right docs retrieved but answer doesn't use them
    if score_sources >= 0.5 and score < 0.3:
        return "hallucination"

    # 6. Everything else — reasoning was weak
    return "weak_reasoning"

def save_evaluation_results(results: list[dict[str, Any]]):
    """Save the evaluation results to a timestamped JSON file in evaluation/results/"""
    results_dir = os.path.join(ROOT_DIR, "evaluation", "results")
    os.makedirs(results_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    results_file = os.path.join(results_dir, f"eval_{timestamp}.json")

    # Summary
    total = len(results)
    passed = sum(1 for r in results if r["status"] == "pass")
    failed = sum(1 for r in results if r["status"] == "fail")
    errors = sum(1 for r in results if r["status"] == "error")
    avg_score = sum(r["score"] for r in results) / total if total else 0.0
    avg_score_sources = sum(r["score_sources"] for r in results) / total if total else 0.0

    summary = {
        "timestamp": timestamp,
        "total": total,
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "avg_score": round(avg_score, 4),
        "avg_score_sources": round(avg_score_sources, 4),
    }

    with open(results_file, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "results": results}, f, indent=2)

    logger.info(
        "evaluation_results_saved", 
        file=results_file,
        summary=summary
    )

if __name__ == "__main__":
    run_evaluation()
