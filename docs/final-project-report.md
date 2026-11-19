# Week 12: Final integration report

## 1. System summary

The project is a local, single-turn AI assistant with a Planner → Worker →
Reviewer LangGraph workflow, optional bounded revision, hybrid documentation
retrieval, evaluation tooling, and structured execution traces. OpenAI remains
the default model and embedding provider; Gemini can be selected independently
for either role. Groq is also available for chat, paired with local Hugging Face
embeddings when no remote embedding API is available.

The FastAPI application initializes one `AssistantRuntime` at startup and
exposes:

- `GET /health` for service/runtime status.
- `POST /ask` for an answer, source paths, review metadata, and a trace ID.
- `POST /evaluate` for a selected built-in evaluation dataset (`smoke`, `full`,
  or `revision`).
- `GET /trace/{trace_id}` for persisted success and workflow-stage-failure
  traces.

Graph and evaluation calls are synchronous operations offloaded to worker
threads; callers still wait for completion. Trace records are full-content
SQLite records under `data/traces/`, retained for seven days. The local API has
no authentication, and is not production-ready or safe to expose to an
untrusted network.

Design decisions are recorded in [ADR 0003](./adr/0003-local-persistent-execution-traces.md).
The runnable local demonstration is in the [demo walkthrough](./demo-walkthrough.md).

## 2. Validation results

| Validation | Result |
|---|---|
| `uv run pytest -q` | **264 passed, 1 skipped** (265 collected). |
| Overall coverage | 94% reported by the configured pytest coverage run. |
| FastAPI startup command help | Confirmed `fastapi dev` accepts `--host` and defaults to `127.0.0.1`. |
| Mocked API/runtime integration | Verified a grounded retrieval-fallback answer through `/ask` and `/trace/{trace_id}`; verified a reviewer-timeout error returns `X-Trace-ID` and leaves a retrievable failed-stage trace. |
| Gemini integration construction | Constructed Gemini chat and embedding integrations, and both Planner/Reviewer structured-output runnables, with placeholder keys and no network call. |
| Live API startup / live provider evaluation | Not run. This report does not claim that external model calls or a real service startup passed. |

Pytest emitted four warnings, including the existing coverage warning that
`main` was not imported. The targeted API/runtime/trace suite passed 48 tests
before the final full-suite run. No lint or type-check command is configured in
the project manifest. The editor problem check reports the existing
`lifespan(app)` parameter shadowing the module-level `app` name in
`app/api/main.py`; it was not changed as part of this work.

## 3. Quality, performance, and cost

No new Week 12 live evaluation or performance run was made, so there is no
Week 12 quality, latency, or token-cost measurement to compare against prior
weeks.

Gemini remains an optional provider for chat and embeddings, and Groq is
available for chat; OpenAI remains the default. Local Hugging Face embeddings
allow RAG to run without an OpenAI or Gemini embedding key. Automated tests
verify provider selection, conditional key validation, provider-neutral model
usage metadata, and FAISS rebuild behavior when the embedding model changes.
Live Groq requests and local model downloads have not been verified with user
credentials or external model services.

The latest existing comparison is the [Week 11 revision report](../../evaluation/reports/revision_comparison.md):
three full runs per mode over 11 questions (33 baseline and 33 revision
evaluations). The keyword-based answer score was 0.73 → 0.86 and retrieval
score 0.53 → 0.56; mean latency increased by about 579 ms, with 0.24 more
LLM calls and 397 more tokens per question on average. Only two questions
triggered revision, and manual inspection found that the keyword score
overstated one result. These results support keeping revision optional; they
are not a Week 12 measurement or proof of a general quality gain.

Earlier Week 9 performance measurements are preserved in
[baseline](../../evaluation/reports/baseline.md) and
[optimized](../../evaluation/reports/optimized.md). They use different
evaluation snapshots and are historical context, not a directly comparable
Week 12 result.

## 4. Reliability and integration

The full suite covers the agent graph, bounded revision and failure paths,
retrieval/tool behavior, evaluation runner and report generation, API response
contracts, runtime delegation, and trace persistence/retention.

The added integration path verifies:

- Vector retrieval failure with keyword fallback can still produce a
  source-attributed answer, marked degraded, and persist its trace.
- A reviewer timeout fails explicitly, does not expose provider details or the
  question in the failed trace, returns `X-Trace-ID`, and can be retrieved
  through the trace route.
- Unknown/expired traces return `404`; evaluation accepts only the built-in
  dataset names and returns bounded response fields.

Evaluation is synchronous from the HTTP caller's perspective, although it
runs off the event loop in a worker thread. It is not a queued/background job.
Evaluation results and full traces are local files, not a shared production
storage service.

## 5. Reflection and revision

Bounded revision remains implemented and opt-in (`revision_enabled=false` by
default). The Week 11 evidence is mixed and narrowly concentrated in two
documentation questions; one apparent gain was a scoring artifact. Keeping
revision opt-in preserves the existing low-cost default while allowing
controlled experiments.

## 6. Known limitations and prioritized next steps

1. **Access control and data governance:** Add authentication/authorization,
   deployment network controls, and a policy for sensitive questions,
   retrieved content, trace deletion, and evaluation artifacts before any
   shared or public deployment. Current full-content traces have no encryption
   or per-user access control.
2. **Trace ID collisions:** Caller-supplied trace IDs are expected to be
   unique, but this is not enforced; reusing one replaces its stored trace.
   Consider rejecting collisions if clients cannot guarantee uniqueness.
3. **Evaluation operations:** Run the smoke/full datasets against the intended
   provider configuration, preserve raw outputs, inspect representative
   failures, and compare only against equivalent dataset/model settings. Add a
   queued job interface if evaluations become too long for request/response
   use.
4. **Deployment readiness:** Add load/concurrency testing, operational
   monitoring and alerting, explicit capacity limits, managed storage, secrets
   management, and an owner for retention and incident handling.
5. **Evaluation quality:** Replace or supplement substring keyword scoring
   with stronger semantic/manual checks and expand cases that can trigger
   bounded revision.

The present result is a tested local integration milestone, not a claim of
production readiness.
