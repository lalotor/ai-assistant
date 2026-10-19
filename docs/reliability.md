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
| Reviewer | Retrieved sources exist but may not sufficiently support an answer | Do not treat source presence alone as proof that evidence is sufficient. | The Reviewer assesses the evidence and must return an explicit limitation or abstention rather than an unsupported answer. | Record retrieval outcomes and available sources; a minimum evidence-sufficiency threshold remains to be defined. |
| Reranker | Reranking call fails after candidate retrieval | Apply the LLM retry policy. If it is still unavailable but candidates exist, retain candidates in their existing deterministic merge order without claiming they were reranked; use them only if evidence is sufficient. | Return a qualified answer with available sources and mark execution degraded; otherwise abstain. | Record reranker failure, fallback use, and final sources. |
| Worker tool | Unexpected tool failure not handled by a safe local fallback | Stop the workflow; do not turn exception text into draft content for the Reviewer. | Fail explicitly; the Reviewer must not convert an error message into an answer. | Record the Worker failure category and that no reviewed answer was produced. |
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
- When Doc Retriever returns no sources, the Reviewer abstains deterministically
  without invoking the LLM. The answer states that no relevant documentation
  was found to support a response.

## Trace and response consistency

Execution outcomes are `success`, `recovered`, `degraded`, or `failed`, as
defined above. Traces should identify the failing stage or dependency, a
structured failure category, retry count, fallback use, and final outcome when
known. Retrieval traces should distinguish a strategy error from a successful
search with zero results and preserve provenance for every returned source.

Do not put raw prompts, document contents, credentials, or unfiltered provider
exception text into routine telemetry. Successful and degraded answers retain
the existing response shape unless a schema change is separately designed;
terminal failures use the existing API/CLI failure path and must not be
represented as successful answers.

## Decisions to confirm during implementation

- Define the exact structured failure categories and how a failed run is
  represented in traces, since the current trace is assembled only after a
  successful graph invocation.
- Define and test the minimum evidence-sufficiency rule for returning a
  qualified answer versus abstaining. Currently, deterministic abstention
  covers the no-source case; source presence alone is not a sufficiency rule.
