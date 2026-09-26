---
name: "run-and-triage-evaluation"
description: "Run the ai-assistant's evaluation suite and interpret/triage failures using its built-in failure categories."
version: 1
created: "2026-09-23"
updated: "2026-09-23"
---
## When to Use
Use when the user wants to run the ai-assistant's evaluation suite (evaluation/runner.py) and understand what a failing/regressed result means, or wants to know whether an eval failure points to a retrieval bug, a planner routing bug, a prompt/reasoning problem, or a stale dataset. Not for writing new unit tests (use tdd) or for diagnosing a hard bug/exception (use diagnosing-bugs) - this skill is specifically for interpreting evaluation-suite results.

## Procedure
1. Confirm the required LLM provider credential is configured in .env (see .env.sample for the expected variable name) - evaluation runs invoke the real assistant end-to-end via subprocess, not mocks. This is a real-API-cost operation, not a free unit test run.
2. Run the smoke dataset first for a fast sanity check: `python evaluation/runner.py` uses evaluation/datasets/retrieval_eval_smoke.json by default per evaluation/runner.py's configuration; check the script's argument handling (or evaluation/datasets/ directory) to confirm which dataset a given invocation targets before assuming smoke vs full.
3. For a full run: `python -m evaluation.runner` (per README.md's documented invocation) against evaluation/datasets/retrieval_eval_full.json.
4. Results are saved progressively to evaluation/results/eval_<timestamp>.json after every question (so a partial run's results are still usable if interrupted). Read the most recent file in evaluation/results/ to see the run's summary: total_questions, evaluated, passed, failed, errors, timeouts, avg_score, avg_score_sources.
5. For each failed item, read its "failure_category" (or equivalent field set by classify_failure() in evaluation/runner.py) and map it to what to investigate: tool_failure (the tool itself crashed - check tool_output for the error, likely a code bug in app/tools/), planner_failure (category != selected_tool - check app/prompts/planner.txt and the tool registry descriptions in app/tools/registry.py for ambiguous routing), missing_context (expected_sources don't exist on disk - the dataset references files that were removed/moved from data/docs, fix the dataset not the code), retrieval_failure (expected docs exist but weren't retrieved - investigate app/tools/doc_retriever.py's Hybrid Retrieval: vector k, keyword_search's term-matching, or the LLM reranking step), hallucination (right docs retrieved but answer doesn't use them - investigate the reviewer/worker prompt or the LLM's grounding), weak_reasoning (everything else - a genuine reasoning-quality issue, often needs a human read of the transcript), slow_execution (duration_ms exceeded SLOW_EXECUTION_THRESHOLD - a performance issue, not correctness).
6. Cross-reference the failing question's category field in the dataset against the actual selected_tool in the result - a mismatch here is definitionally a planner_failure and should not be miscategorized as a retrieval issue.
7. If several failures share the same failure_category, look for a systemic cause (e.g. all retrieval_failure items reference the same doc type or the same query phrasing pattern) rather than fixing each one as an isolated case.
8. After making a code or dataset fix, re-run the same dataset (smoke for a fast check, full before considering it resolved) to confirm the specific failing question(s) now pass, and that no previously-passing question regressed.
9. Do not edit evaluation/results/*.json manually - these are generated artifacts; if a dataset's expected_keywords/expected_sources need correcting (e.g. after a real code change altered legitimate behavior), edit the dataset file in evaluation/datasets/ instead.

## Pitfalls
- Evaluation runs make real LLM API calls per question (via subprocess to main.py --json) - this costs money and takes real wall-clock time (QUESTION_TIMEOUT env var, default 60s per question). Don't run the full dataset repeatedly during iteration; use the smoke dataset while investigating, and confirm with the user before running the full suite if it hasn't been run recently.
- classify_failure()'s categories are checked in a fixed priority order (tool_failure, then planner_failure, then missing_context, then retrieval_failure, then hallucination, then weak_reasoning) - a question failing for multiple reasons will only ever surface its first-matching category, so fixing that one and re-running may reveal a second, previously-masked failure category on the same question.
- missing_context failures mean the dataset's expected_sources paths don't exist in data/docs on this machine/checkout - this is very often a stale-dataset problem (files were moved/renamed), not a retrieval bug, and should not be triaged as retrieval_failure.
- The runner shells out to `main.py --question ... --json`, so any bug in main.py's argument parsing or JSON output path will surface as evaluation failures unrelated to actual assistant quality - if many/all questions fail identically, check that the CLI itself still runs correctly before assuming a systemic quality regression.
- Results files in evaluation/results/ are gitignored (per .gitignore's evaluation/results/ entry) - don't expect to diff historical results via git; compare timestamps/contents of the JSON files directly instead.

## Verification
1. The evaluation run completes (or is interrupted) and produces a results file in evaluation/results/ with a summary section (evaluated/passed/failed/errors/timeouts counts).
2. Each failing item's failure_category has been mapped to a specific hypothesis about root cause (tool bug, prompt/routing issue, stale dataset, retrieval gap, or genuine reasoning weakness) before any fix is attempted.
3. After a fix, the same dataset is re-run and the previously-failing question(s) now pass, with no new failures among previously-passing questions.