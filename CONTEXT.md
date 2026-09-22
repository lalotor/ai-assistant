# AI Assistant

A multi-agent conversational assistant that routes user questions to specialized tools (code explanation, documentation retrieval, architecture advice) through a fixed three-stage pipeline, using Retrieval-Augmented Generation (RAG) for documentation-grounded answers.

## Language

### Pipeline Stages

**Planner**:
The first pipeline stage. Decides which Tool (if any) should handle the user's question and produces a Tool Decision.
_Avoid_: Router, Dispatcher

**Worker**:
The second pipeline stage. Invokes the Tool selected by the Planner and produces the Draft Answer.
_Avoid_: Executor, Runner

**Reviewer**:
The third and final pipeline stage. Reviews the Draft Answer and produces the Final Answer plus Review Feedback.
_Avoid_: Critic, Validator

**Plan**:
The Planner's one-line natural-language rationale for its Tool Decision. Not a multi-step execution plan, despite the name.
_Avoid_: Strategy, Task Plan

**Draft Answer**:
The unreviewed answer produced by the Worker, built from the selected Tool's output. Awaits review before being shown to the user.
_Avoid_: Raw Answer, Tool Output (Tool Output is a separate, narrower field feeding into the Draft Answer)

**Final Answer**:
The reviewed, user-facing answer produced by the Reviewer from the Draft Answer.
_Avoid_: Response, Output

**Review Feedback**:
The Reviewer's critique of the Draft Answer, explaining what changed or why the Final Answer differs from it.
_Avoid_: Review Notes, Critique

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
The complete record of a single question's run across the Planner, Worker, and Reviewer stages, keyed by Trace ID. Contains a nested Retrieval Trace when the Doc Retriever was used.
_Avoid_: Run Log, Execution Record

**Retrieval Trace**:
A nested trace of one Hybrid Retrieval invocation: vector result count, keyword result count, merged count, reranked count, and final sources. Always contained within an Execution Trace, never standalone.
_Avoid_: Retrieval Log

**Trace ID**:
The identifier generated per question that ties together all logs, state, and the Execution Trace for that question. Used as the correlation ID in structured logs and as the LangGraph thread ID.
_Avoid_: Correlation ID, Request ID (Trace ID is the canonical term; the others are used in logging output but mean the same thing)

**Stage Timings**:
The per-stage started_at/ended_at timestamps recorded on the agent state as the Planner, Worker, and Reviewer each run.
_Avoid_: Timing Data, Performance Metrics
