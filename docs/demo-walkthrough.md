# Local API demo walkthrough

This walkthrough exercises a grounded answer, persisted trace lookup, and the
built-in evaluation endpoint. It uses the live model provider and may incur API
usage costs.

## 1. Start the local service

From the repository root, install dependencies and configure the provider key:

```bash
uv sync
cp .env.sample .env
# Set OPENAI_API_KEY in .env, or choose Gemini for both providers:
# LLM_PROVIDER=gemini
# EMBEDDING_PROVIDER=gemini
# GEMINI_API_KEY=your-key
```

Start the API on loopback only:

```bash
uv run fastapi dev app/api/main.py --host 127.0.0.1
```

In another terminal, confirm startup:

```bash
curl -sS http://127.0.0.1:8000/health
```

The health response should report `"status":"ok"` and an initialized runtime.

## 2. Ask a documentation-grounded question

```bash
curl -sS http://127.0.0.1:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"Considering only your internal documentation, what inputs does DiffService take?"}'
```

The response includes the final answer, retrieved source paths, review outcome,
and `trace_id`. Record that ID for the next step. Add
`"revision_enabled":true` to the request body to test the bounded, optional
revision path.

## 3. Inspect the complete execution trace

Replace `<trace_id>` with the value returned by `/ask`:

```bash
curl -sS http://127.0.0.1:8000/trace/<trace_id>
```

The trace includes stage and retrieval details and may contain the question,
answer, and retrieved content. Unknown and expired IDs return `404`.

## 4. Run the smoke evaluation

```bash
curl -sS http://127.0.0.1:8000/evaluate \
  -H 'Content-Type: application/json' \
  -d '{"dataset":"smoke","revision_enabled":false}'
```

The request waits for the selected dataset to finish. The response includes
aggregate metrics, status counts, per-question results, and a raw-results path
under `evaluation/results/`. Only the server-owned `smoke`, `full`, and
`revision` datasets are accepted.

## Safety and test coverage

The API has no authentication. Keep the development server bound to loopback;
do not expose it to a public or untrusted network. Full trace records and
evaluation artifacts are stored locally.

For deterministic failure-path evidence without relying on a live provider,
run:

```bash
uv run pytest tests/runtime/test_retrieval_fallback_flow.py
```

This test module covers successful retrieval fallback through `/ask` and
`/trace/{trace_id}`, plus a reviewer timeout that returns an error response
with a trace ID and persists a retrievable failed-stage trace.
