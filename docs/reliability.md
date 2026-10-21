# Reliability policy

This document defines the failure policy for the Planner → Worker → Reviewer
workflow, its optional one-revision path, and its retrieval dependencies. It
guides implementation; it does not claim that every behavior below is
exercised by every question.

## Execution outcomes

| Outcome | Meaning |
|---|---|
| `success` | The workflow completed normally and the Reviewer produced the Final Answer. This includes the explicit single-pass policy where a reviewer requests revision but no revision path is enabled (`revision_skipped`). |
| `recovered` | A transient failure occurred, but a bounded retry restored the normal path without a known loss of capability. Emit only when the retry is observable; the current provider-client integration does not expose a stable retry-attempt signal, so this outcome is reserved and not emitted. |
| `degraded` | The workflow can safely return a qualified limitation or use partial capabilities, but a known strategy or evidence source was unavailable. Evidence abstention (`abstained`) and a revision whose final review still requests changes (`budget_exhausted`) are degraded outcomes. |
| `failed` | The workflow could not safely produce a reviewed, evidence-supported answer. Reviewer, final-reviewer, or revision failures are terminal and never return the draft as the answer. |

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
| Reviewer (initial pass) | Provider error, invalid output, missing/invalid decision, or timeout after a draft exists | Apply the LLM retry policy, then fail if review cannot complete. The structured decision is required; malformed output is not retried unchanged. Never treat the unreviewed draft as the Final Answer. | Fail explicitly; do not return the draft as a successful or degraded answer. | Record Reviewer failure and that no Final Answer was produced. |
| Revision | Provider error, invalid output, empty revision, or timeout after the reviewer requested changes | Apply the LLM retry policy, then fail. Do not restart the graph, retry the tool, or return the pre-revision draft as if it were approved. | Fail explicitly; no revised answer is returned. | Record the `revision` stage failure and available timings. |
| Reviewer (final pass after revision) | Provider error, invalid output, missing/invalid decision, or timeout | Apply the LLM retry policy, then fail. The revised draft is not reviewer-approved and must not be presented as approved. | Fail explicitly; do not silently return the revised draft. | Record the `reviewer_final` stage failure; the trace outcome is `failed`. |
| Reviewer / graph | Revision budget already used and the final Reviewer still requests revision | Do not route to another revision. End the graph, keep the revised answer, append an explicit provisional-answer limitation, and mark the outcome `budget_exhausted`. | Return the revised answer with its limitation; trace outcome is `degraded`. | Record both review decisions, one revision, and the exhausted budget. |
| Reviewer / graph | Revision is disabled and the Reviewer requests revision | Do not call the revision step. Use the Reviewer's inline `final_answer` and mark `review_outcome=revision_skipped`. | Return the single-pass reviewed answer; trace outcome remains `success`. | Record the reviewer decision and that no revision was attempted. |

## Review and revision policy

- The Reviewer returns a validated decision: `approve`, `revise`, or
  `abstain`. A `revise` decision is actionable only when `feedback` is
  non-empty; otherwise the graph does not start a revision.
- Revision is opt-in and bounded to one attempt. The graph checks
  `revision_enabled`, the decision, the feedback, and `revision_count < 1`
  before routing to the `revision` node. The final Reviewer pass cannot
  request another revision, even if its prompt output says `revise`.
- A revision receives the original question, current draft, reviewer
  feedback, the existing tool output, and the existing retrieved-source
  list. It does not re-run the selected tool or re-retrieve documents.
  `retrieved_sources` and `retrieval_trace` are retained unchanged.
- The final Reviewer reuses the same structured contract and evidence gate
  as the initial Reviewer. For Doc Retriever answers, a final
  `evidence_sufficient=false` produces a deterministic abstention; it never
  authorizes inventing evidence during revision.
- If the final Reviewer still requests changes after one revision, the graph
  ends with the revised answer plus an explicit provisional limitation and
  `review_outcome=budget_exhausted`. This is a degraded result, not a second
  revision and not a normal approval.
- If revision is disabled and the Reviewer requests changes, the single-pass
  behavior is preserved: the Reviewer's inline `final_answer` is returned
  and `review_outcome=revision_skipped`. No extra LLM call is made.

## Retry and timeout bounds

- Retry only failures positively classified as transient. Authentication,
  configuration, invalid-request, and malformed-output failures are not
  transient.
- LLM calls use the OpenAI client's transient-error retry policy, configured
  for two retries (three total attempts). The client honors `Retry-After` and
  otherwise uses exponential backoff with jitter for retryable failures.
- Each LLM provider request, including a revision or final-review request, has
  a 30-second timeout. This replaces the provider SDK's 600-second default; it
  is an initial per-operation limit, not an end-to-end workflow deadline.
- A reviewer request for revision does not add a retry layer around the
  revision call. The revision and its final review use the same provider retry
  policy as the initial review; an exhausted retry budget fails the graph.
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
retrieval fallback, evidence abstention, or review-budget exhaustion as
`degraded`. A graph-stage failure retains the existing exception/API failure
path but also emits a safe failed Execution Trace in structured logs. It
identifies the failing stage (`revision` or `reviewer_final` when applicable),
category, exception type, and available stage timings; snapshots and retrieval
details are omitted so the failed trace does not contain user input, document
content, or retrieval queries. Routine application logs record lengths/counts
and structured categories rather than user questions, code, retrieved excerpts,
drafts, or final answers. The configured provider SDK retries internally but
does not expose a stable retry-attempt callback to the runtime, so a
`recovered` outcome is intentionally not emitted.

Revision-enabled traces contain two Reviewer events (`reviewer` and
`reviewer_final`), one Revision event, and a Review Trace with the initial and
final decisions, feedback, revision count, and outcome. Single-pass traces
contain one Reviewer event and no Revision event. The response exposes the
final `review_decision`, `revision_count`, and `review_outcome`; source
provenance remains the same list returned by the Worker.

Do not put raw prompts, document contents, credentials, or unfiltered provider
exception text into routine telemetry. Successful and degraded answers retain
the existing response shape unless a schema change is separately designed;
terminal failures use the existing API/CLI failure path and must not be
represented as successful answers.

## Evaluation snapshot

Three full runs of the revised 11-question dataset were completed on
2026-10-19 (33 evaluations total), using curated alternative phrasings for
the retry-policy and queue-versus-REST concepts. The aggregate is in
[reliability_eng_phrase_groups.md](../evaluation/reports/reliability_eng_phrase_groups.md)
and [reliability_eng_phrase_groups.json](../evaluation/reports/reliability_eng_phrase_groups.json);
raw runs remain under the ignored `evaluation/results/` directory. Earlier
Week 10 reports are preserved, and the Week 9 optimized report is unchanged.

| Metric | Week 9 optimized (33 evals) | Week 10 phrase groups (33 evals) |
|---|---:|---:|
| Average answer score | 0.6734 | 0.8553 |
| Average retrieval/source score | 0.4740 | 0.5152 |
| Average latency | 8,478.5 ms | 5,913.3 ms |
| P95 latency | 20,130.2 ms | 12,486.5 ms |
| Average tokens per question | 3,811.2 | 4,025.5 |
| Total LLM calls | 96 | 99 |

The three runs passed 32 of 33 evaluations, with no errors or timeouts. The
single full-suite miss was a DiffService abstention despite retrieving the
controller call site and its four arguments. A subsequent two-question smoke
run still abstained on DiffService after the Reviewer prompt was clarified to
state that a visible call expression is sufficient evidence; the retrieval
was correct, but the model's evidence judgment remains intermittent. The
ingestion question passed in the smoke run.

The revised keyword scoring accepts curated phrase alternatives for each
required concept and retains the original literal keywords for diagnostics.
This avoids treating “retry up to 3 times” as wrong solely because it omits
an internal field name, or requiring a hyphen in “dead letter queue.” The
reported score is still keyword-based, not a semantic judge. These rubric
changes and separate live LLM runs mean this is not an apples-to-apples
comparison with Week 9.

The revised dataset also corrected stale expectations (including the
DiffService identifier/source, the MongoDB no-context case, and a question
about a service absent from the corpus). These are separate live LLM runs,
not deterministic paired measurements; differences cannot be attributed
solely to the reliability changes. The prompt clarification was smoke-tested
but not included in the three-run aggregate. Manual user verification on
2026-10-20 confirmed the latest changes behaved as expected. The intermittent
DiffService abstention remains a documented model-judgment limitation, not a
claim of deterministic resolution or a blocker to closing the Week 10 scope.

## Accepted observability limitation

- Keep provider-client retries bounded and enabled. The installed
  LangChain/OpenAI integration delegates requests to the OpenAI SDK without a
  stable application-level retry callback. Do not infer recovery from latency
  or add a second retry layer; leave `recovered` reserved until a stable
  signal is available.
- Validate how reliably the Reviewer identifies irrelevant and partial
  evidence. The current sufficiency signal is LLM-judged; no deterministic
  semantic proof exists for source relevance.
- Revision quality is not guaranteed by the existence of a revision step. The
  Week 11 comparison must be read as keyword-proxy evidence, with manual
  inspection of changed, unchanged, and regressed answers; revision must not
  be enabled by default unless that comparison supports it.
