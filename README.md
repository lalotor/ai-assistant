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
   uv add langchain_core langchain-openai langgraph langchain-text-splitters langchain_community ipython python-dotenv structlog pytest pytest-cov pytest-mock faiss-cpu
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

## Run the evaluation suite
```bash
python evaluation/runner.py
python -m evaluation.runner
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

## Week 10 — Long-Running Workflows

Add support for:
- persistent execution state
- resumable workflows
- multi-step task execution

Focus:
- workflow durability
- state management
- replayable execution

---

## Week 11 — Reflection + Self-Improvement

Implement controlled reflection:
- critique stage
- bounded revisions
- deterministic refinement

Focus:
- structured self-evaluation
- safe iterative improvement
- orchestration discipline

---

## Week 12 — Final System Integration

Integrate:
- multi-agent orchestration
- advanced RAG
- evaluation
- observability
- API runtime
- execution tracing

Final goal:

> A production-minded AI orchestration system resembling internal engineering copilots and enterprise AI assistants.

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
