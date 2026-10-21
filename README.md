# Setting Up the Python Environment with uv
1. **Init project**:
   ```bash
   uv init --python 3.13.5 ai-assistant
   cd ai-assistant
   ```
2. **Venv**
   ```bash
   uv venv
   source .venv/bin/activate
   ```

3. **Dependencies**
   ```bash
   uv add langchain_core langchain-openai langgraph langchain-text-splitters langchain_community ipython python-dotenv structlog pytest pytest-cov pytest-mock faiss-cpu "fastapi[standard]"
   ```
# FastAPI
## Run the Development Server
```bash
uv run fastapi dev app/api/main.py
```

# Running the Agent
## Interactive mode
```bash
python main.py
```

## Non-interactive mode, default output
```bash
python main.py --question "Considering only your internal documentation, how many ingestion file source types do we have?"
```

## Non-interactive mode, JSON output
```bash
python main.py --question "Considering only your internal documentation, how many ingestion file source types do we have?"  --json
```

## Non-interactive mode with bounded revision
```bash
python main.py --question "Considering only your internal documentation, how many ingestion file source types do we have?" --json --revision
```

Revision is opt-in. The graph allows at most one revision when the Reviewer
returns `revise` with actionable feedback, then performs one final review. The
API exposes the same switch with `"revision_enabled": true` on `POST /ask`.

## Run the evaluation suite
```bash
# Single-pass mode
python -m evaluation.runner --dataset evaluation/datasets/retrieval_eval_full.json

# Revision-enabled mode (same dataset/model/scoring)
python -m evaluation.runner --dataset evaluation/datasets/retrieval_eval_full.json --revision

# Compare repeated runs per mode
python -m evaluation.compare \
  --baseline "evaluation/results/eval_single_pass_*.json" \
  --revision "evaluation/results/eval_revision_*.json"
```

## Run evaluation report
```bash
python -m evaluation.build_report --results evaluation/results/eval_<ts>.json --title "Baseline run" --name baseline
python -m evaluation.build_report --title "Baseline run" --name baseline   # uses the most recent results file
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
- FastAPI (later stages)

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
- Default-off comparison is documented in
  [evaluation/reports/revision_comparison.md](evaluation/reports/revision_comparison.md)
  once the live comparison runs are complete.

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
