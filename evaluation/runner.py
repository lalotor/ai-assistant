"""Evaluation runner for retrieval assessment.

Invokes the AI assistant via its CLI interface (`python main.py --question ... --json`)
so that all initialisation logic (env validation, vector store, logging) is handled
by main.py and never duplicated here.

Results are saved progressively after each question is evaluated, so partial
results are preserved even if the runner is interrupted or a later question fails.
A configurable per-question timeout prevents any single question from blocking
the entire evaluation run.
"""
from dataclasses import asdict
from datetime import datetime
import argparse
import json
import os
import subprocess
import sys
from typing import Any
import structlog
from dotenv import load_dotenv

from app.contracts.response import QueryResponse

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

slow_execution_threshold = int(validated_env.get("SLOW_EXECUTION_THRESHOLD", 10000))

# Per-question timeout in seconds. If a question takes longer, it is marked as
# a timeout error and the runner moves on to the next question.
question_timeout = int(validated_env.get("QUESTION_TIMEOUT", 60))

def ask_assistant(
    question: str,
    timeout: int | None = None,
    revision_enabled: bool = False,
) -> QueryResponse:
    """Send a question to the AI assistant via the CLI and return the JSON result.

    Args:
        question: The user question to evaluate.
        timeout:  Maximum seconds to wait for the subprocess. Defaults to the
                  QUESTION_TIMEOUT env var (120s). Pass 0 or None to disable.
        revision_enabled: Pass --revision to the CLI so the bounded revision
                  path is available for this run.

    Returns:
        Parsed QueryResponse with all pipeline fields.

    Raises:
        TimeoutError: If the subprocess exceeds the timeout.
        RuntimeError: If the subprocess exits with a non-zero code.
        json.JSONDecodeError: If the output is not valid JSON.
    """
    effective_timeout = timeout if timeout is not None else question_timeout
    command = [sys.executable, MAIN_SCRIPT, "--question", question, "--json"]
    if revision_enabled:
        command.append("--revision")

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            cwd=ROOT_DIR,
            check=False,
            timeout=effective_timeout if effective_timeout > 0 else None,
        )
    except subprocess.TimeoutExpired as exc:
        logger.error(
            "assistant_timeout",
            question_length=len(question),
            timeout_seconds=effective_timeout,
        )
        raise TimeoutError(
            f"Question processing timed out after {effective_timeout}s."
        ) from exc

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
    return QueryResponse.from_dict(json.loads(json_line))


def score_keywords(
    answer: str,
    expected_keywords: list[str] | None = None,
    expected_keyword_groups: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """Score literal keywords or concepts with explicitly accepted phrasings."""
    normalized_answer = answer.casefold()
    expected = expected_keywords or []
    hits = [keyword for keyword in expected if keyword.casefold() in normalized_answer]

    if expected_keyword_groups:
        matched_groups = [
            label
            for label, alternatives in expected_keyword_groups.items()
            if any(alternative.casefold() in normalized_answer for alternative in alternatives)
        ]
        score = len(matched_groups) / len(expected_keyword_groups)
    else:
        matched_groups = []
        score = len(hits) / len(expected) if expected else 1.0

    return {
        "expected_keywords": expected,
        "matched_keywords": hits,
        "expected_keyword_groups": expected_keyword_groups or {},
        "matched_keyword_groups": matched_groups,
        "score": score,
    }


def run_evaluation(
    dataset_path: str | None = None,
    revision_enabled: bool = False,
) -> list[dict[str, Any]]:
    """Run the evaluation suite against the retrieval pipeline.

    Results are saved progressively after each question so that partial
    results survive interruptions.  A per-question timeout prevents any
    single question from blocking the entire run.

    Args:
        dataset_path: Path to the evaluation JSON file.
                      Defaults to evaluation/datasets/retrieval_eval_smoke.json.
        revision_enabled: Run the same dataset through the graph with the
                      bounded revision path enabled.

    Returns:
        List of result dicts, one per evaluation item.
    """
    if dataset_path is None:
        dataset_path = os.path.join(
            ROOT_DIR, "evaluation", "datasets", "retrieval_eval_smoke.json"
        )

    with open(dataset_path, encoding="utf-8") as f:
        eval_set = json.load(f)

    results: list[dict[str, Any]] = []

    # Create the results file path once, reused for every progressive save
    results_dir = os.path.join(ROOT_DIR, "evaluation", "results")
    os.makedirs(results_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    mode = "revision" if revision_enabled else "single_pass"
    results_file = os.path.join(results_dir, f"eval_{mode}_{timestamp}.json")

    logger.info(
        "run_evaluation_started",
        questions=len(eval_set),
        timeout_per_question=question_timeout,
        revision_enabled=revision_enabled,
        results_file=results_file,
    )
    
    for idx, item in enumerate(eval_set, start=1):
        question = item["question"]
        logger.info(
            "evaluating_question",
            progression=f"[{idx}/{len(eval_set)}]",
            question_length=len(question),
        )

        try:
            response = ask_assistant(question, revision_enabled=revision_enabled)
            retrieved_sources = response.retrieved_sources

            # Keyword matching
            expected = item.get("expected_keywords", [])
            keyword_score = score_keywords(
                response.final_answer,
                expected_keywords=expected,
                expected_keyword_groups=item.get("expected_keyword_groups"),
            )
            hits = keyword_score["matched_keywords"]
            score = keyword_score["score"]

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

            # Execution trace
            trace = response.execution_trace
            planner_event = trace.planner_events[0]
            worker_event = trace.worker_events[0]
            reviewer_event = trace.reviewer_events[0]
            final_reviewer_event = (
                trace.reviewer_events[1] if len(trace.reviewer_events) > 1 else None
            )
            revision_event = trace.revision_events[0] if trace.revision_events else None

            timing_metrics = {
                "trace": {
                    "trace_id": trace.trace_id,
                    "started_at": trace.started_at,
                    "ended_at": trace.ended_at,
                    "duration_ms": trace.duration_ms
                },
                "planner": {
                    "started_at": planner_event.started_at,
                    "ended_at": planner_event.ended_at,
                    "duration_ms": planner_event.duration_ms
                },
                "worker": {
                    "started_at": worker_event.started_at,
                    "ended_at": worker_event.ended_at,
                    "duration_ms": worker_event.duration_ms
                },
                "reviewer": {
                    "started_at": reviewer_event.started_at,
                    "ended_at": reviewer_event.ended_at,
                    "duration_ms": reviewer_event.duration_ms
                }
            }
            llm_usage = {
                "planner": {
                    "llm_calls": planner_event.llm_calls,
                    "token_usage": planner_event.token_usage
                },
                "worker": {
                    "llm_calls": worker_event.llm_calls,
                    "token_usage": worker_event.token_usage
                },
                "reviewer": {
                    "llm_calls": reviewer_event.llm_calls,
                    "token_usage": reviewer_event.token_usage
                },
            }
            total_llm_calls = (
                planner_event.llm_calls
                + worker_event.llm_calls
                + reviewer_event.llm_calls
            )

            if final_reviewer_event is not None:
                timing_metrics["reviewer_final"] = {
                    "started_at": final_reviewer_event.started_at,
                    "ended_at": final_reviewer_event.ended_at,
                    "duration_ms": final_reviewer_event.duration_ms,
                }
                llm_usage["reviewer_final"] = {
                    "llm_calls": final_reviewer_event.llm_calls,
                    "token_usage": final_reviewer_event.token_usage,
                }
                total_llm_calls += final_reviewer_event.llm_calls

            if revision_event is not None:
                timing_metrics["revision"] = {
                    "started_at": revision_event.started_at,
                    "ended_at": revision_event.ended_at,
                    "duration_ms": revision_event.duration_ms,
                }
                llm_usage["revision"] = {
                    "llm_calls": revision_event.llm_calls,
                    "token_usage": revision_event.token_usage,
                }
                total_llm_calls += revision_event.llm_calls

            llm_usage["total_llm_calls"] = total_llm_calls

            result = {
                "question": question,
                "answer": response.final_answer,
                "plan": response.plan,
                "selected_tool": response.selected_tool,
                "tool_input": response.tool_input,
                "tool_output": response.tool_output,
                "draft_answer": response.draft_answer,
                "initial_draft_answer": response.initial_draft_answer,
                "answer_changed": (
                    response.initial_draft_answer is not None
                    and response.final_answer != response.initial_draft_answer
                ),
                "review_feedback": response.review_feedback,
                "initial_review_decision": (
                    trace.review_trace.initial_decision if trace.review_trace else None
                ),
                "review_decision": response.review_decision,
                "revision_count": response.revision_count,
                "review_outcome": response.review_outcome,
                "retrieved_sources": retrieved_sources_list,
                "expected_keywords": expected,
                "matched_keywords": hits,
                "expected_keyword_groups": keyword_score["expected_keyword_groups"],
                "matched_keyword_groups": keyword_score["matched_keyword_groups"],
                "expected_sources": expected_sources,
                "matched_sources": hits_sources,
                "score": score,
                "score_sources": score_sources,
                "status": "pass" if score >= 0.5 else "fail",
                "failure_type": classify_failure(item, response, score, score_sources),
                "timing_metrics": timing_metrics,
                "llm_usage": llm_usage,
                "retrieval_trace": (
                    asdict(trace.retrieval_trace)
                    if trace.retrieval_trace is not None
                    else None
                ),
            }
            matched_criteria = (
                keyword_score["matched_keyword_groups"]
                if keyword_score["expected_keyword_groups"]
                else hits
            )
            expected_criteria_count = (
                len(keyword_score["expected_keyword_groups"])
                if keyword_score["expected_keyword_groups"]
                else len(expected)
            )
            logger.info(
                "evaluation_result",
                score=f"{len(matched_criteria)}/{expected_criteria_count} matched (score: {score:.0%})",
                score_sources=f"{len(hits_sources)}/{len(expected_sources)} matched (score: {score_sources:.0%})",
                failure_type=result["failure_type"]
            )

        except TimeoutError as exc:
            result = {
                "question": question,
                "answer": None,
                "error": str(exc),
                "score": 0.0,
                "score_sources": 0.0,
                "status": "timeout",
                "failure_type": "timeout",
            }
            logger.error(
                "evaluation_timeout",
                question_length=len(question),
                timeout_seconds=question_timeout,
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
                error_type=type(exc).__name__,
            )

        results.append(result)

        # Progressive save — write after every question so partial results survive
        _save_progress(results, results_file, len(eval_set), mode=mode)

    logger.info(
        "run_evaluation_completed",
        total=len(results),
        revision_enabled=revision_enabled,
        results_file=results_file,
    )

    return results

def classify_failure(item: dict, response: QueryResponse, score: float, score_sources: float) -> str | None:
    """Classify the failure type for a failed evaluation item.

    Only ever assigns a failure type to items that actually failed
    (score < 0.5). A passing item is never classified, even if it was
    slow, since "slow but correct" is not a failure.
    """
    if score >= 0.5:
        return None  # Not a failure

    duration_ms = response.execution_trace.duration_ms
    if duration_ms is not None and duration_ms > slow_execution_threshold:
        return "slow_execution"

    category = item.get("category", "")
    selected_tool = response.selected_tool
    tool_output = response.final_answer
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

def _save_progress(
    results: list[dict[str, Any]],
    results_file: str,
    total_questions: int,
    mode: str = "single_pass",
) -> None:
    """Persist current results to disk after each question.

    Called after every evaluated question so that partial results are
    available even if the runner is interrupted mid-run.

    Args:
        results:          Accumulated result dicts so far.
        results_file:     Absolute path to the output JSON file.
        total_questions:  Total number of questions in the dataset.
        mode:             "single_pass" or "revision"; stored in the summary
                          so comparison reports can label the source run.
    """
    evaluated = len(results)
    passed = sum(1 for r in results if r["status"] == "pass")
    failed = sum(1 for r in results if r["status"] == "fail")
    errors = sum(1 for r in results if r["status"] == "error")
    timeouts = sum(1 for r in results if r["status"] == "timeout")
    avg_score = sum(r["score"] for r in results) / evaluated if evaluated else 0.0
    avg_score_sources = sum(r["score_sources"] for r in results) / evaluated if evaluated else 0.0
    revisions_attempted = sum(1 for r in results if r.get("revision_count", 0) > 0)
    abstained = sum(1 for r in results if r.get("review_outcome") == "abstained")
    budget_exhausted = sum(
        1 for r in results if r.get("review_outcome") == "budget_exhausted"
    )
    answers_changed = sum(1 for r in results if r.get("answer_changed"))

    summary = {
        "timestamp": datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),
        "mode": mode,
        "total_questions": total_questions,
        "evaluated": evaluated,
        "remaining": total_questions - evaluated,
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "timeouts": timeouts,
        "avg_score": round(avg_score, 4),
        "avg_score_sources": round(avg_score_sources, 4),
        "revisions_attempted": revisions_attempted,
        "abstained": abstained,
        "budget_exhausted": budget_exhausted,
        "answers_changed": answers_changed,
    }

    with open(results_file, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "results": results}, f, indent=2)

    logger.info(
        "progress_saved",
        progression=f"[{evaluated}/{total_questions}]",
        file=results_file,
    )

def main() -> None:
    parser = argparse.ArgumentParser(description="Run the assistant evaluation suite.")
    parser.add_argument(
        "--dataset",
        default=None,
        help="Evaluation dataset JSON path (defaults to the smoke dataset).",
    )
    parser.add_argument(
        "--revision",
        action="store_true",
        default=False,
        help="Enable the bounded review-and-revision loop for this run.",
    )
    args = parser.parse_args()
    run_evaluation(args.dataset, revision_enabled=args.revision)


if __name__ == "__main__":
    main()
