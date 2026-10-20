# Reliability policy

This document defines the initial failure policy for the Planner → Worker →
Reviewer workflow and its retrieval dependencies. It guides implementation;
it does not claim that the current runtime already enforces these behaviors.

## Execution outcomes

| Outcome | Meaning |
|---|---|
| `success` | The workflow completed normally and the Reviewer produced the Final Answer. |
| `recovered` | A transient failure occurred, but a bounded retry restored the normal path without a known loss of capability. |
| `degraded` | The workflow can safely return a qualified limitation or use partial capabilities, but a known strategy or evidence source was unavailable. |
| `failed` | The workflow could not safely produce a reviewed, evidence-supported answer. |

A retry or fallback must never be reported as normal success when it leaves a
known limitation. A degraded answer must state that limitation and preserve any
available source attribution. A failed workflow must not present a draft as a
Final Answer.

## Failure policies

| Boundary | Failure | Action | Caller behavior | Trace behavior |
|---|---|---|---|---|
| Planner, Worker, Reviewer, or reranker LLM call | Temporary network/provider error or rate limit | Retry only errors classified as transient, with a finite attempt limit and backoff. Honor `Retry-After` when available. Use one retry layer; verify and configure the provider client's existing behavior before adding another. | If a retry succeeds and no capability was lost, continue normally. If retries are exhausted, fail explicitly. | Record operation, attempt count, whether recovery occurred, and terminal failure category. |
| Any LLM call | Invalid request/output schema, authentication, or configuration error | Fail fast; do not retry unchanged input or credentials. | Return the existing generic API error or CLI failure; do not expose provider details. | Record a non-retryable failure category without prompts, credentials, or raw sensitive exception text. |
| Any external operation | Operation timeout | Enforce a timeout at the integration boundary where cancellation is real. Retry only if the timeout is classified as transient and budget remains; otherwise terminate. Do not rely on an outer timeout that leaves the synchronous request running in a background thread. | Return a recovered result only if a bounded retry succeeds; otherwise fail explicitly. | Record timeout, attempts, and elapsed time. |
| Planner | Invalid or unrecognized tool selection | Reject before dispatch. Do not substitute an arbitrary tool or silently treat an invalid selection as `none`. | Fail explicitly; do not invoke a tool or ask the Reviewer to turn the error into an answer. | Record a planner validation failure. |
| Vector retrieval | Search errors while keyword retrieval succeeds | Continue with keyword results. If usable evidence remains, return a qualified answer and mark execution degraded because one retrieval strategy was unavailable. | Return the answer with available sources and a clear limitation; if evidence is insufficient, abstain. | Record vector failure, keyword availability, fallback use, and available sources. |
| Keyword retrieval | Search/cache errors while vector retrieval succeeds | Continue with vector results. If usable evidence remains, return a qualified answer and mark execution degraded because one retrieval strategy was unavailable. | Return the answer with available sources and a clear limitation; if evidence is insufficient, abstain. | Record keyword failure, vector availability, fallback use, and available sources. |
| Vector and keyword retrieval | Both strategies fail | Do not rerun the entire graph or invent evidence. | Fail explicitly; no documentation-grounded answer is returned. | Record retrieval failure and both strategy outcomes. |
| Retrieval | Both strategies complete but return no sources | Treat this as an evidence limitation, not a retrieval exception. Do not retry the same empty search blindly. | The Reviewer returns a deterministic abstention without an LLM call. | Retrieval status distinguishes successful empty results from strategy failures; record the abstention outcome. |
| Reviewer | Retrieved sources exist but are irrelevant or only partially support an answer | Do not treat source presence alone as proof that evidence is sufficient. The structured Reviewer result must set `evidence_sufficient` false unless the retrieved excerpts directly support the requested answer. | When the Reviewer reports insufficient evidence for Doc Retriever, the runtime replaces the proposed answer with a standard deterministic abstention. | Record retrieval outcomes and available sources; the sufficiency assessment itself is LLM-judged, not a deterministic semantic proof. |
| Reranker | Reranking call fails after candidate retrieval | Apply the LLM retry policy. If it is still unavailable but candidates exist, retain candidates in their existing deterministic merge order without claiming they were reranked; use them only if evidence is sufficient. | Return a qualified answer with available sources and mark execution degraded; otherwise abstain. | Record reranker failure, fallback use, and final sources. |
| Worker tool | Unexpected tool failure not handled by a safe local fallback | Stop the workflow; raise `ToolExecutionError` without embedding the underlying error text in a draft. | Fail explicitly; the Reviewer must not convert an error message into an answer. | Record the `tool_execution_error` category and exception type; no reviewed answer is produced. |
| Planner/Worker boundary | Selected tool is not registered | Raise `InvalidToolSelectionError`; do not invoke a substitute or pass an error draft to the Reviewer. | Fail explicitly. | Record `invalid_tool_selection` without treating the invalid selection as a tool result. |
| Reviewer | Provider error, invalid output, or timeout after a draft exists | Apply the LLM retry policy, then fail if review cannot complete. Never treat the unreviewed draft as the Final Answer. | Fail explicitly; do not return the draft as a successful or degraded answer. | Record Reviewer failure and that no Final Answer was produced. |

## Retry and timeout bounds

- Retry only failures positively classified as transient. Authentication,
  configuration, invalid-request, and malformed-output failures are not
  transient.
- LLM calls use the OpenAI client's transient-error retry policy, configured
  for two retries (three total attempts). The client honors `Retry-After` and
  otherwise uses exponential backoff with jitter for retryable failures.
- Each LLM provider request has a 30-second timeout. This replaces the
  provider SDK's 600-second default; it is an initial per-operation limit, not
  an end-to-end workflow deadline.
- Avoid nested retries. Configure the existing LLM client rather than wrapping
  each call in a second retry policy.
- Set external-call timeouts at the client/integration boundary. Verify whether
  timeout or cancellation actually stops the underlying operation.
- Use the Week 9 p95 latency (about 22.4 seconds across 33 evaluated questions)
  as context, not as an operation timeout. The per-call limits must be based on
  provider behavior and measured stage timings rather than copied from the
  end-to-end number.
- Retrieval operations are read-only and may be retried only when the specific
  failure is transient and the request budget allows it. Do not repeat a
  successful empty search as though it were an error.
- Keyword retrieval compares normalized lowercase terms and content, gives
  mixed-case, uppercase, and numeric identifiers extra weight, and prefers
  matching implementation code over tests. If a matching code chunk has an
  immediate same-source successor with no independent query-term match, the
  successor is included as context so split calls and their arguments remain
  available together; relevance and sufficiency still require review.
- When Doc Retriever returns no sources, the Reviewer abstains deterministically
  without invoking the LLM. The answer states that no relevant documentation
  was found to support a response.
- When sources exist, the Reviewer must explicitly assess whether their content
  supports the requested answer. A false `evidence_sufficient` decision causes
  the runtime to return a standard abstention instead of the generated answer.
- When a question requests exact names, identifiers, inputs, counts, or
  configuration values, preserve the supported forms from the retrieved
  excerpts rather than replacing them with generic paraphrases.

## Trace and response consistency

Execution outcomes are `success`, `recovered`, `degraded`, or `failed`, as
defined above. Record a structured failure category, retry count, and failing
stage when those facts are observable; record fallback use and final outcome
for completed workflows. Retrieval traces distinguish a strategy error from a
successful search with zero results and preserve provenance for every
returned source.

Successful Execution Traces classify normal completion as `success` and
retrieval fallback or evidence abstention as `degraded`. A graph-stage failure
retains the existing exception/API failure path but also emits a safe failed
Execution Trace in structured logs. It identifies the failing stage, category,
exception type, and available stage timings; snapshots and retrieval details
are omitted so the failed trace does not contain user input, document content,
or retrieval queries. The configured provider SDK retries internally but does
not currently expose retry attempts to the runtime, so a `recovered` outcome
is not emitted until recovery can be observed reliably.

Do not put raw prompts, document contents, credentials, or unfiltered provider
exception text into routine telemetry. Successful and degraded answers retain
the existing response shape unless a schema change is separately designed;
terminal failures use the existing API/CLI failure path and must not be
represented as successful answers.

## Evaluation snapshot

Three full runs of the revised 11-question dataset were completed on
2026-10-19 (33 evaluations total). The latest aggregate is in
[reliability_eng_refined.md](../evaluation/reports/reliability_eng_refined.md)
and [reliability_eng_refined.json](../evaluation/reports/reliability_eng_refined.json);
raw runs remain under the ignored `evaluation/results/` directory. The
earlier [reliability_eng.md](../evaluation/reports/reliability_eng.md) is
preserved as a historical Week 10 report, and the Week 9 optimized report is
unchanged.

| Metric | Week 9 optimized (33 evals) | Week 10 refined (33 evals) |
|---|---:|---:|
| Average answer score | 0.6734 | 0.7364 |
| Average retrieval/source score | 0.4740 | 0.5354 |
| Average latency | 8,478.5 ms | 5,788.5 ms |
| P95 latency | 20,130.2 ms | 10,586.8 ms |
| Average tokens per question | 3,811.2 | 3,906.0 |
| Total LLM calls | 96 | 99 |

The refined run passed 28 of 33 evaluations, with no errors or timeouts. The
five misses were two DiffService abstentions despite retrieving the controller
call site, one ingestion-source abstention, one retry-policy answer, and one
queue-versus-REST answer. The last two answers included the documented
behavior/tradeoffs but were penalized by exact keyword checks: for example,
the retry answer said “up to 3 times” and “dead letter queue,” while the
rubric required `retry_count`, `max_retries`, and `dead-letter queue`; the
architecture answer described scalability and decoupling without using those
literal terms. Treat the 28/33 count as a strict benchmark result, not a
complete measure of semantic answer quality.

The revised dataset also corrected stale expectations (including the
DiffService identifier/source, the MongoDB no-context case, and a question
about a service absent from the corpus). These results are therefore not an
apples-to-apples comparison with Week 9, despite equal sample sizes.
Furthermore, these are separate live LLM runs, not deterministic paired
measurements; differences cannot be attributed solely to the reliability
changes. The prior Week 10 report remains available for historical reference.
The rubric mismatches above should be reviewed before a future evaluation;
no further live evaluation was run after identifying them.

## Decisions to confirm during implementation

- Expose provider retry attempts if the SDK offers a stable hook, then emit
  `recovered` only when at least one retry actually occurred and succeeded.
- Validate how reliably the Reviewer identifies irrelevant and partial
  evidence. The current sufficiency signal is LLM-judged; no deterministic
  semantic proof exists for source relevance.
