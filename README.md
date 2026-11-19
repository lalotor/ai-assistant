# Local Setup

Requires Python 3.13.5 or newer and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.sample .env
# Set OPENAI_API_KEY in .env
```

The first run initializes the local vector store and may take 1-2 minutes.

## FastAPI

Run the development server bound to loopback:

```bash
uv run fastapi dev app/api/main.py --host 127.0.0.1
```

The API has no authentication and is intended for trusted local/internal use
only. Do not bind it to a public or untrusted network: trace lookup returns
full request content and evaluation results can contain sensitive data.

### `POST /ask`

```bash
curl -sS http://127.0.0.1:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"What does the architecture_advisor tool do?"}'
```

The response contains `trace_id`, `answer`, `sources`, and review metadata.
Use the returned ID to retrieve the full trace. If supplying your own
`trace_id`, keep it unique: reusing an ID replaces the previously stored trace.

```bash
curl -sS http://127.0.0.1:8000/trace/<trace_id>
```

`GET /trace/{trace_id}` returns the full execution trace or `404` if it is
unknown or expired. Traces are stored in
`data/traces/execution_traces.sqlite3` and retained for seven days.

### `POST /evaluate`

Evaluation runs synchronously from the caller's perspective; the route uses a
worker thread so the API event loop remains responsive. Only built-in datasets
are accepted (`smoke`, `full`, or `revision`), and the default is `smoke`:

```bash
curl -sS http://127.0.0.1:8000/evaluate \
  -H 'Content-Type: application/json' \
  -d '{"dataset":"smoke","revision_enabled":false}'
```

The response includes aggregate metrics, per-question results, outcome counts,
and the local raw-results path under `evaluation/results/`. The endpoint does
not accept arbitrary dataset paths.

# Running the Agent
## Interactive mode
```bash
uv run python main.py
```

## Non-interactive mode, default output
```bash
uv run python main.py --question "Considering only your internal documentation, how many ingestion file source types do we have?"
```

## Non-interactive mode, JSON output
```bash
uv run python main.py --question "Considering only your internal documentation, how many ingestion file source types do we have?" --json
```

## Non-interactive mode with bounded revision
```bash
uv run python main.py --question "Considering only your internal documentation, how many ingestion file source types do we have?" --json --revision
```

Revision is opt-in. The graph allows at most one revision when the Reviewer
returns `revise` with actionable feedback, then performs one final review. The
API exposes the same switch with `"revision_enabled": true` on `POST /ask` and
`POST /evaluate`.

## Run the evaluation suite
```bash
# Single-pass mode
uv run python -m evaluation.runner --dataset evaluation/datasets/retrieval_eval_full.json

# Revision-enabled mode (same dataset/model/scoring)
uv run python -m evaluation.runner --dataset evaluation/datasets/retrieval_eval_full.json --revision

# Compare repeated runs per mode
uv run python -m evaluation.compare \
  --baseline "evaluation/results/eval_single_pass_*.json" \
  --revision "evaluation/results/eval_revision_*.json"
```

## Run evaluation report
```bash
uv run python -m evaluation.build_report --results evaluation/results/eval_<ts>.json --title "Baseline run" --name baseline
uv run python -m evaluation.build_report --title "Baseline run" --name baseline   # uses the most recent results file
```

# Running unit tests suite
## Standard
```bash
uv run pytest
```

## Run one file
```bash
uv run pytest tests/rag/test_chunking.py
```

# AI Engineering Assistant Roadmap (12 Weeks)

A production-minded AI Engineering project focused on:
- agent orchestration
- retrieval systems (RAG)
- evaluation & observability
- deterministic workflows
- production-oriented architecture

Core stack:
- Python
- LangGraph
- LangChain
- FAISS
- OpenAI API
- FastAPI (local REST API)

---

## Week 1 — Minimal Agent

Build a basic LangGraph agent with:
- CLI interface
- simple orchestration
- tool execution
- state transitions
- logging

Focus:
- orchestration fundamentals
- stateful workflows
- deterministic execution

---

## Week 2 — Tools + Contracts

Introduce:
- reusable tools
- typed contracts
- tool registry

Example tools:
- code explainer
- doc retriever
- architecture advisor

Focus:
- separation of concerns
- typed input/output
- orchestration boundaries

---

## Week 3 — Multi-Agent System

Build a deterministic multi-agent workflow:
- planner
- worker
- reviewer

Flow:

```text
START → planner → worker → reviewer → END
```

Focus:
- structured orchestration
- controlled execution
- explicit transitions

---

## Week 4 — RAG v1

Implement initial retrieval system:
- ingestion pipeline
- chunking
- embeddings
- vector retrieval
- RAG integration

Focus:
- chunking quality
- semantic retrieval
- retrieval-aware agents

---

## Week 5 — Hybrid Retrieval + Reranking

Upgrade retrieval with:
- semantic search
- keyword search
- reranking
- retrieval observability

Pipeline:

```text
query
 ↓
vector retrieval
 +
keyword retrieval
 ↓
merge
 ↓
rerank
 ↓
final context
```

Focus:
- production-style retrieval
- retrieval quality
- exact identifier lookup

---

## Week 6 — Evaluation System

Build evaluation infrastructure:
- curated evaluation dataset
- evaluation runner
- scoring pipeline
- trace capture
- failure categorization

Focus:
- measurable AI quality
- regression detection
- reproducibility

---

## Week 7 — Failure Analysis + Observability

Add:
- execution tracing
- structured telemetry
- failure categorization
- stage diagnostics

Focus:
- debugging AI systems
- observability-first design
- replayability

---

## Week 8 — API Layer + Runtime Boundaries

Expose the system via FastAPI:
- `POST /ask`
- `POST /evaluate`
- `GET /trace/{id}`

Focus:
- runtime separation
- thin API layer
- orchestration isolation

---

## Week 9 — Performance + Cost Engineering

Introduce:
- caching
- latency tracking
- token usage analysis
- model comparison

Focus:
- measurable optimization
- cost/quality tradeoffs
- production efficiency

---

## Week 10 — Reliability Engineering

Introduce:
- bounded, selective retries
- operation timeouts and execution budgets
- retrieval fallbacks and graceful degradation
- explicit terminal failure and abstention behavior
- failure-injection tests and recovery telemetry

**Focus:**
- predictable failure handling
- resilience without silent quality degradation
- latency, cost, and correctness trade-offs

## Week 11 — Controlled Reflection + Revision

Introduce:
- structured reviewer decisions
- explicit answer-quality criteria
- bounded critique-and-revision
- revision budgets and stopping conditions
- evaluation of single-pass vs. revised answers

**Focus:**
- evidence-grounded refinement
- controlled iterative orchestration
- measurable quality improvements

**Implementation:**
- `ReviewResult.decision` is a validated `approve` / `revise` / `abstain`.
- The graph routes to at most one dedicated revision node, then a final review.
- Revision reuses existing tool output and retrieved sources; it does not
  re-retrieve or discard provenance.
- `reviewer` / `revision` / `reviewer_final` stage timings and usage, plus a
  Review Trace, are included in the execution trace.
- The single-pass vs revision comparison is in
  [evaluation/reports/revision_comparison.md](evaluation/reports/revision_comparison.md).
  Revision remains opt-in: the measured benefit was limited to one Doc
  Retriever failure mode, and the keyword proxy overstated one revised answer.

## Week 12 — Final Integration + Production Readiness

Integrate and validate:
- multi-agent orchestration
- hybrid RAG and source attribution
- evaluation and regression testing
- execution tracing and telemetry
- API runtime and failure handling
- performance and token-cost analysis
- architecture and operational documentation

**Final goal:**

A production-minded AI orchestration system resembling an internal engineering copilot, with measurable quality, observable execution, bounded recovery behavior, and a reproducible demonstration.

**Stretch goal, only if justified:** persistent checkpoints and resumable long-running workflows for tasks that genuinely need to survive process restarts or wait for external events.

---

# Architectural Principles

- Deterministic orchestration
- Separation of concerns
- Observability-first design
- Production-minded simplicity
- Evaluation-driven improvement

Avoid:
- uncontrolled autonomous agents
- premature infrastructure complexity
- hidden orchestration logic
- opaque AI workflows
