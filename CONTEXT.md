# AI Assistant

A multi-agent conversational assistant that routes user questions to specialized tools (code explanation, documentation retrieval, architecture advice) through a fixed Planner → Worker → Reviewer pipeline, with an optional single revision step after review, using Retrieval-Augmented Generation (RAG) for documentation-grounded answers.

## Language

### Pipeline Stages

**Planner**:
The first pipeline stage. Decides which Tool (if any) should handle the user's question and produces a Tool Decision.
_Avoid_: Router, Dispatcher

**Worker**:
The second pipeline stage. Invokes the Tool selected by the Planner and produces the Draft Answer.
_Avoid_: Executor, Runner

**Reviewer**:
The third pipeline stage. Reviews the Draft Answer against the selected Tool's output, returns a structured Review Decision, and produces the Final Answer plus Review Feedback. For Doc Retriever results, it also assesses whether the retrieved excerpts sufficiently support the answer; an insufficient-evidence decision produces an abstention. When revision is enabled, a second reviewer pass evaluates the revised answer against the original Worker tool output and source list but cannot request another revision.
_Avoid_: Critic, Validator

**Plan**:
The Planner's one-line natural-language rationale for its Tool Decision. Not a multi-step execution plan, despite the name.
_Avoid_: Strategy, Task Plan

**Draft Answer**:
The unreviewed answer produced by the Worker, built from the selected Tool's output. Awaits review before being shown to the user.
_Avoid_: Raw Answer, Tool Output (Tool Output is a separate, narrower field feeding into the Draft Answer)

**Final Answer**:
The reviewed, user-facing answer produced by the Reviewer from the Draft Answer, or from the revised draft after the final review.
_Avoid_: Response, Output

**Review Feedback**:
The Reviewer's critique of the Draft Answer, explaining what changed or why the Final Answer differs from it. For a revision request, it must name a specific correction supported by the available evidence.
_Avoid_: Review Notes, Critique

**Review Decision**:
The Reviewer's structured choice: `approve` (the draft is acceptable), `revise` (one actionable, evidence-grounded correction is needed), or `abstain` (the answer cannot be responsibly produced). The value is validated by the review contract before the graph routes on it.
_Avoid_: Verdict, Score

**Revision**:
One rewrite of the Draft Answer by a dedicated revision step, using the original question, current draft, Review Feedback, existing Tool Output, and Retrieved Sources. It never re-runs the selected Tool or re-retrieves documents.
_Avoid_: Refinement Loop, Retry

**Revision Budget**:
The maximum number of Revision attempts for one question: one. The budget is enforced in graph routing and in the Reviewer's second pass, not only in prompt text.
_Avoid_: Retry Count, Iteration Limit

**Review Outcome**:
The terminal review state for one question: `approved`, `revised`, `abstained`, `budget_exhausted` (a revision was attempted but the final Reviewer still requested changes), or `revision_skipped` (single-pass mode used the Reviewer's inline answer when it asked for revision).
_Avoid_: Status, Result

### Tools

**Tool Decision**:
The Planner's structured output: which Tool to use, why (the Plan), and what input to pass it.
_Avoid_: Routing Decision, Selection

**Code Explainer**:
The Tool used when the user provides code snippets needing explanation or analysis.

**Doc Retriever**:
The Tool used when the user asks about internal technical documentation. Performs Hybrid Retrieval.

**Architecture Advisor**:
The Tool used when the user asks about software architecture, design patterns, or system design.

### Retrieval

**Hybrid Retrieval**:
The retrieval strategy combining vector search and keyword search, merging their results, then reranking to produce the final context. Used by the Doc Retriever.
_Avoid_: RAG Pipeline (RAG is the broader system capability; Hybrid Retrieval is the specific merge+rerank strategy inside it)

**Retrieved Sources**:
The list of source document identifiers returned alongside an answer, letting the user trace which documents grounded the response.
_Avoid_: Citations, References

### Tracing & Observability

**Execution Trace**:
The complete record of a single completed question's run across the Planner, Worker, Reviewer, and optional Revision stages, keyed by Trace ID. Includes an outcome (`success`, `recovered`, `degraded`, or `failed`), a Review Trace, one Reviewer event for a single pass or two when revision occurred, revision events when applicable, and a nested Retrieval Trace when the Doc Retriever was used. Terminal failures are logged at the workflow boundary with `outcome=failed`. The provider SDK's bounded retries remain enabled, but the current LangChain/OpenAI client integration exposes no stable retry-attempt callback to the runtime; `recovered` is therefore reserved and not emitted.
_Avoid_: Run Log, Execution Record

**Review Trace**:
The decision history within an Execution Trace: initial decision and feedback, whether revision was attempted, revision count, final decision and feedback, and the Review Outcome. Per-pass timing and token usage remain on the corresponding Reviewer and Revision Stage Events.
_Avoid_: Review Log

**Retrieval Trace**:
A nested trace of one Hybrid Retrieval invocation: vector and keyword result counts and completion statuses, merged count, reranked count, final sources, whether fallback was used, and an overall duration broken down by sub-stage into vector search, keyword search, merge, and rerank timings (each `None`, not `0`, when that sub-stage was never measured). Failed strategy and reranker error types are recorded without raw exception details. Always contained within an Execution Trace, never standalone.
_Avoid_: Retrieval Log

**Evidence Abstention**:
The Reviewer’s deterministic response when Doc Retriever returns no sources. It does not invoke the Reviewer LLM and does not treat a successful empty search as a retrieval failure.
_Avoid_: Retrieval Failure

**Trace ID**:
The identifier generated per question that ties together all logs, state, and the Execution Trace for that question. Used as the correlation ID in structured logs and as the LangGraph thread ID.
_Avoid_: Correlation ID, Request ID (Trace ID is the canonical term; the others are used in logging output but mean the same thing)

**Stage Timings**:
The per-stage started_at/ended_at timestamps recorded on the agent state as the Planner, Worker, Reviewer, optional Revision, and final Reviewer run. A single-pass execution has only the `reviewer` key; a revised execution has `reviewer`, `revision`, and `reviewer_final`.
_Avoid_: Timing Data, Performance Metrics

**LLM Call Count**:
The number of LLM invocations made while running one pipeline stage, recorded on that stage's StageEvent as llm_calls. Not always 1: the Worker's llm_calls is 2, not 1, when the selected Tool is Doc Retriever, since Hybrid Retrieval's reranking step makes its own, otherwise-invisible LLM call. A revision-enabled execution can add one Revision call and one final Reviewer call.
_Avoid_: Number of Requests, API Calls

**Token Usage**:
The input/output token counts and model name for the LLM call(s) made during one pipeline stage, recorded on that stage's StageEvent as token_usage. None when the provider returned no usage metadata, distinct from a stage that genuinely made zero LLM calls - the two are never conflated.
_Avoid_: Cost, Token Count (Token Usage is the stage-level structured record; the others are looser terms used only in prose)
