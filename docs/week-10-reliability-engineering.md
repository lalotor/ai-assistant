# Week 10 — Reliability Engineering for AI Workflows

**Project:** AI Engineering Assistant  
**Duration:** 4 hours  
**Core stack:** Python, LangGraph, LangChain, FAISS, OpenAI API, FastAPI

## 1. Mission

Week 9 improved observability: execution traces, stage-level latency, retrieval timings, token usage, and evaluation scores.

This week, make the assistant handle failures deliberately. It should recover when a safe alternative exists, terminate predictably when recovery is impossible, and avoid returning unsupported answers.

### Deliverables

- Bounded retries for transient failures.
- Timeouts at appropriate integration boundaries.
- A retrieval fallback when one retrieval strategy fails.
- Explicit behavior for unrecoverable failures and insufficient evidence.
- Deterministic failure-injection tests.
- Execution traces that distinguish normal success, recovered success, degraded success, and failure.

**Scope:** Persistent/resumable workflows are not required this week. Consider them later only if the assistant needs to survive process restarts or wait for long-running external events.

## 2. Engineering principles

1. **Retry only transient failures.** Do not repeatedly retry invalid requests, authentication errors, or configuration errors.
2. **Bound retries and time.** Every retry policy must have a maximum attempt count and must respect the applicable time budget.
3. **Prefer local recovery.** Retry the failed operation where possible instead of restarting the entire graph and repeating successful work.
4. **Preserve correctness.** A fallback must not silently turn an evidence-grounded answer into an unsupported guess.
5. **Distinguish failure from empty results.** A retrieval strategy that errors is not the same as one that succeeds but returns no useful evidence.
6. **Make outcomes observable.** Record the recovery path, final outcome, and relevant timing/attempt information in the existing trace system.
7. **Avoid unnecessary infrastructure.** Reuse existing client and framework capabilities before adding libraries or abstractions.

## 3. Failure scenarios and expected behavior

| Scenario | Expected behavior |
|---|---|
| LLM provider temporarily returns an error | Retry within a bounded policy |
| LLM request exceeds its timeout | Stop waiting within the configured time budget |
| Vector search fails but keyword search succeeds | Continue using available retrieval evidence |
| Both retrieval strategies fail | Return a clear failure or abstention, not invented evidence |
| Planner returns an invalid tool selection | Reject it safely; do not invoke an arbitrary tool |
| Reviewer fails after the worker generates a draft | Apply an explicit review-failure policy |
| Retries are exhausted | Terminate predictably and record why |

Use these as initial policies. Inspect the current repository and adapt them to its actual interfaces and behavior before changing code.

## 4. Concepts to apply

### 4.1 Retries

Retries are useful when a failure may disappear on another attempt.

| Failure type | Initial policy |
|---|---|
| Temporary network error or provider 5xx | Retry a bounded number of times |
| HTTP 429 / rate limit | Honor `Retry-After` when available; otherwise use backoff |
| Invalid request or malformed schema | Do not retry unchanged input |
| Authentication/configuration error | Fail fast |
| Empty retrieval results | Consider an alternative strategy; do not blindly repeat the same search |

Use exponential backoff with jitter where appropriate. Check whether the current provider client already retries before adding another retry layer. Avoid nested retry loops that multiply attempts and latency.

### 4.2 Timeouts and budgets

Distinguish individual operation timeouts from the overall workflow deadline.

- Set appropriate timeouts for external calls where supported.
- Ensure retries cannot run indefinitely.
- Understand whether cancellation actually stops the underlying operation.
- Avoid starting a retry when insufficient time remains for it to be useful.
- Choose initial values using Week 9 measurements and document assumptions; do not pick arbitrary aggressive limits.

### 4.3 Retrieval fallback

The current hybrid retrieval pipeline has vector and keyword retrieval. This is a suitable place for the first fallback.

- Handle failures from each retrieval strategy independently where the architecture allows.
- Preserve source metadata and provenance for available results.
- Distinguish a strategy error from a successful search with zero useful results.
- Verify the merge/reranker behavior with partial and empty result sets.
- If neither strategy yields sufficient evidence, abstain or return an explicit limitation.

### 4.4 Execution outcomes

Use a small outcome vocabulary, adapting it to existing contracts:

- `success`: normal execution completed.
- `recovered`: a failure occurred, but a retry or fallback recovered.
- `degraded`: execution completed with a documented limitation.
- `failed`: the workflow could not safely complete.

These are proposed labels, not assumptions about existing repository code. Keep the chosen outcome consistent across API responses, evaluation output, and traces where appropriate.

### 4.5 Side effects and idempotency

Do not blindly retry operations that may have side effects. Read-only retrieval is generally safe to repeat, but future tools that create or modify external resources need an explicit duplicate-execution policy, such as idempotency keys or operation-status checks. Do not add unnecessary idempotency infrastructure for read-only operations.

## 5. Four-hour work plan

### Session 1 — Failure policies (45 minutes)

**Goal:** Decide how each critical boundary should behave before implementing recovery.

1. Inspect the planner, worker, reviewer, retrieval implementation, and external client calls.
2. List likely failures at each boundary.
3. For each failure, choose retry, fallback, degrade, or fail fast.
4. Define what the caller and trace should receive.

**Deliverable:** `docs/reliability.md` with a failure-policy table.

### Session 2 — Bounded retries and timeouts (45 minutes)

**Goal:** Prevent transient failures and slow calls from creating unbounded work.

1. Identify the correct integration boundaries for retries.
2. Implement or configure bounded retries for known transient failures.
3. Set appropriate operation timeouts.
4. Ensure permanent errors are not retried and attempt counts are observable.

**Deliverable:** Unit tests for retry success, retry exhaustion, permanent errors, and timeout behavior.

### Session 3 — Retrieval fallback (75 minutes)

**Goal:** Recover when one retrieval strategy fails without compromising evidence quality.

1. Inspect how vector and keyword retrieval are currently invoked.
2. Handle each strategy's failure independently where the architecture permits.
3. Preserve source metadata for results that remain available.
4. Distinguish partial retrieval from total retrieval failure.
5. Define the outcome when no sufficient evidence is available.

**Deliverable:** An end-to-end test where one retrieval strategy fails and the other successfully supplies evidence.

### Session 4 — Failure injection and regression (75 minutes)

**Goal:** Prove that recovery policies work under controlled failures.

1. Simulate transient and permanent provider errors.
2. Simulate timeouts and retry exhaustion.
3. Simulate vector failure, keyword failure, and both failing.
4. Verify final outcomes, traces, and source attribution.
5. Run the existing evaluation suite and compare results with the saved Week 9 baseline.

**Deliverable:** A repeatable resilience test suite and a short before/after report.

## 6. Implementation guidance

### 6.1 Start with a failure-policy table

Create `docs/reliability.md` (or update an existing equivalent). Begin with a table such as:

| Boundary | Failure | Action | Expected outcome |
|---|---|---|---|
| LLM client | Transient provider error | Bounded retry | Success if a later attempt works |
| LLM client | Invalid request | Fail fast | Failed |
| Vector retrieval | Search failure | Continue with keyword results if available | Recovered or degraded |
| Keyword retrieval | Search failure | Continue with vector results if available | Recovered or degraded |
| Retrieval | Insufficient evidence | Abstain or return qualified limitation | Degraded or failed, per contract |
| Reviewer | Timeout/provider error | Apply explicit review-failure policy | Never silently claim review succeeded |

Adapt the table to actual code boundaries and existing contracts.

### 6.2 Keep retries at the right boundary

- Prefer retrying the specific failed operation rather than the entire graph.
- Record attempt count and final failure category.
- Do not retry permanent failures.
- Avoid nested retry loops.
- Respect overall request deadlines where available.
- Do not retry side-effecting operations without a duplicate-execution policy.

### 6.3 Make retrieval resilient

Desired behavior:

1. Run vector and keyword retrieval using the current pipeline.
2. Determine which results are available.
3. If both succeed, preserve the normal merge/rerank path.
4. If one fails, continue with the available strategy if the existing architecture supports it.
5. Check whether evidence is sufficient for the question.
6. If evidence is insufficient, abstain or explain the limitation.

Do not assume the reranker supports empty or partial result sets. Inspect its contract and test the cases that will be supported. Preserve the distinction between retrieval errors and empty results.

### 6.4 Extend existing traces

Build on the existing `ExecutionTrace` and telemetry. Do not create a separate logging system.

Capture, where applicable:

- Stage/dependency that failed.
- Structured failure category and retryability.
- Number of attempts.
- Whether a fallback was activated.
- Which retrieval strategies returned usable results.
- Final execution outcome.
- Duration and available token usage.

Avoid storing sensitive prompts or document contents in routine telemetry without a specific, justified need. Prefer structured error categories over raw exception text that could expose secrets.

## 7. Required automated tests

Use mocks or controlled fakes to make failures deterministic. Do not rely on actual provider outages or unpredictable network behavior.

| Test | Expected assertion |
|---|---|
| First LLM attempt fails, second succeeds | Workflow succeeds; attempt count is correct |
| Every LLM attempt fails | Retries stop at configured limit |
| Permanent request error | No retry loop |
| Operation times out | Execution terminates or recovers within the intended budget |
| Vector retrieval fails, keyword succeeds | Available evidence continues through the pipeline with provenance |
| Keyword retrieval fails, vector succeeds | Available results continue through the supported pipeline |
| Both retrieval strategies fail | No fabricated evidence; explicit failure or abstention |
| Reviewer fails | Documented review-failure policy is enforced |
| Normal request succeeds | Existing behavior and evaluation remain stable |

A timeout test should verify behavior at the actual client/execution boundary, not merely that a mocked function raises a timeout exception.

## 8. Evaluation and measurements

Use the Week 9 baseline to assess the effect of reliability changes. Do not judge success only by the number of recovered failures.

Track:

- **Quality:** answer and retrieval evaluation scores.
- **Latency:** average, p50, and p95 where sample size supports useful interpretation.
- **Cost:** LLM calls and token usage per question.
- **Reliability:** recovery rate, terminal failure rate, retry exhaustion, and timeout frequency.
- **Evidence:** whether final answers remain grounded in retrieved sources.

Week 9 runs contained 32–33 evaluated questions, with average latency around 8.5–9.2 seconds. Treat these as initial reference points, not definitive benchmarks: the run sizes differed, and one sample trace showed substantially higher vector-search latency than the baseline average. Avoid attributing changes to Week 10 without controlling for those differences.

Preserve the Week 9 baseline files. Document any quality regression, unexpected latency increase, or change in token usage.

## 9. Definition of done

- [x] Failure policies documented for critical stages and external dependencies.
  - **Note:** `docs/reliability.md` records the policies. Unexpected tool
    failures now propagate as `ToolExecutionError`, and invalid tool selections
    fail as `InvalidToolSelectionError`; neither becomes draft text.
- [x] Retries are selective, bounded, and distinguish transient from permanent failures.
  - **Note:** The OpenAI client is configured for two retries and a 30-second
    request timeout; deterministic tests cover retry success, exhaustion, and
    permanent errors. Retry attempts are not exposed in runtime telemetry.
- [x] Operation timeouts are enforced at appropriate boundaries.
  - **Note:** Provider request timeouts are set at the client boundary and
    tested against a local HTTP server that delays its response.
- [x] At least one retrieval fallback works end to end.
  - **Note:** `tests/runtime/test_retrieval_fallback_flow.py` runs the actual
    graph through `AssistantRuntime.run_question()` with vector failure and
    controlled keyword evidence, including mixed-case exact identifiers. It
    verifies that the evidence and source reach the Reviewer, the answer is
    returned with provenance, and the execution/retrieval traces identify the
    degraded fallback. Keyword matching compares query and content
    case-insensitively and includes a non-matching adjacent code chunk from
    the same source when it continues a matching chunk. The regression
    fixture verifies that all DiffService call arguments reach the Reviewer.
    The final live evaluation and remaining quality gaps are summarized in
    the [Evaluation snapshot](reliability.md#evaluation-snapshot).
- [x] Insufficient evidence and unrecoverable failures have explicit outcomes.
  - **Note:** No-source Doc Retriever results cause deterministic abstention;
    when sources exist, the Reviewer must report `evidence_sufficient`, and a
    false result is replaced with a standard abstention. Total retrieval and
    other terminal failures propagate to the existing generic API 500 path.
    Evidence sufficiency with sources is LLM-judged, not a deterministic
    semantic proof.
- [x] Automated tests cover recovery, retry exhaustion, permanent errors, and retrieval failure combinations.
  - **Note:** Retry success/exhaustion/permanent errors, actual client timeout,
    vector/keyword failure combinations, end-to-end fallback/provenance,
    Reviewer abstention for irrelevant or partial evidence, and Reviewer
    timeout behavior through the API failure path are covered.
- [ ] Traces distinguish normal success, recovered success, degraded success, and failure.
  - **Partial:** Successful Execution Traces distinguish `success` and
    `degraded`; failed graph stages emit safe structured failed Execution
    Traces with stage and partial timing. Provider retry recovery is not
    observable, so `recovered` is not emitted.
- [x] Existing evaluations run; any quality regression is investigated.
  - **Result:** Three full runs of the revised 11-question dataset (33
    evaluations) passed 28 questions, with no errors or timeouts. The
    aggregate is recorded in
    [reliability_eng_refined.md](../evaluation/reports/reliability_eng_refined.md)
    and [reliability_eng_refined.json](../evaluation/reports/reliability_eng_refined.json).
    The observed averages were 0.7364 answer score, 0.5354 retrieval/source
    score, 5,788.5 ms latency, and 3,906 tokens per question.
  - **Remaining findings:** Two DiffService runs abstained despite retrieving
    the controller call site; one ingestion run abstained with the source
    file retrieved. The retry-policy and queue-versus-REST answers described
    the expected behavior but missed literal expected-keyword checks (for
    example, `max_retries` versus “up to 3 times,” and `dead-letter queue`
    versus “dead letter queue”). Review these rubric mismatches before the
    next evaluation; the 28/33 result is not a complete measure of semantic
    answer quality. The revised rubric and 2026-10-19 results also differ
    from Week 9, so the score change is not a controlled comparison. No
    additional live evaluation was run after these mismatches were identified.
- [x] Week 9 baseline is preserved for comparison.
  - **Note:** The existing Week 9 baseline and optimized reports were not
    modified; the latest Week 10 results are in the separate
    `reliability_eng_refined` reports. The earlier
    `reliability_eng` reports remain historical.

## 10. Targeted references

Use these as targeted references, not additional courses:

- [Tenacity](https://tenacity.readthedocs.io/) — retry policies and backoff.
- [Python asyncio timeouts](https://docs.python.org/3/library/asyncio-task.html#timeouts) — if integration boundaries use async operations.
- [LangGraph documentation](https://docs.langchain.com/oss/python/langgraph/overview) — relevant workflow and state-management patterns.

Before adding a library or abstraction, inspect what the current provider client and graph implementation already support.

## 11. Final engineering challenge

Demonstrate and test this scenario:

> A user asks a question about internal documentation. Vector retrieval fails. Keyword retrieval succeeds. The assistant answers from available evidence, records the degraded retrieval path, and produces a trace that explains what happened. If keyword retrieval also fails, the assistant returns an explicit limitation instead of inventing an answer.

Also demonstrate:
1. A transient LLM failure that recovers within the retry policy.
2. A permanent failure that terminates without retrying indefinitely.

Week 10 is complete when these scenarios are reproducible through automated tests and you can explain their effects on quality, latency, cost, and observability.

**Core principle:** Reliability is not the absence of failures. It is the ability to handle failures within defined limits while preserving correctness and making the outcome observable.

## 12. Instructions for the AI coding companion

Work incrementally and inspect the repository before making changes.

1. **Inspect first.** Review the current graph, retrieval code, LLM client configuration, `ExecutionTrace`, tests, and evaluation runner. Identify the actual implementation boundaries and existing retry/timeout behavior.
2. **Report before editing.** Summarize the relevant architecture, likely files to change, existing capabilities to reuse, and any assumptions.
3. **Propose the failure policy.** Map each important failure to retry, fallback, degrade, or fail fast. Call out cases where the existing contracts do not define behavior.
4. **Implement in small steps.** Start with the policy documentation and tests, then implement bounded retries/timeouts, then retrieval fallback, then trace enhancements.
5. **Preserve existing architecture.** Avoid unnecessary new dependencies, duplicate retry layers, broad graph rewrites, and unrelated refactoring.
6. **Test deterministically.** Use mocks or controlled fakes for provider errors, timeouts, and retrieval failures. Do not depend on real outages.
7. **Run regression evaluation.** Execute relevant unit/integration tests and the existing evaluation suite. Compare against the saved Week 9 baseline when possible.
8. **Report honestly.** Summarize files changed, behavior added, tests run and their actual results, evaluation differences, known limitations, and any unfinished work. Do not claim a test passed unless it was executed successfully.
9. **Do not silently change contracts.** If API/state/trace schemas need to change, explain the change and update tests and documentation consistently.
10. **Stop at the Week 10 scope.** Do not implement persistent/resumable workflows or a general-purpose reliability framework unless inspection reveals an existing, concrete requirement.

Begin by inspecting the repository and reporting a concise implementation plan. Do not start with a large code change.
