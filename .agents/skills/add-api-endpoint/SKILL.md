---
name: "add-api-endpoint"
description: "Scaffold a new FastAPI endpoint or extend the AssistantRuntime for the ai-assistant's runtime/API layer, following the thin-route, runtime-owns-orchestration conventions in app/api/ and app/runtime/."
version: 1
created: "2026-09-24"
updated: "2026-09-24"
---
## When to Use
Use when adding a new HTTP endpoint (e.g. alongside /ask and /health) or extending AssistantRuntime's public interface (app/runtime/assistant_runtime.py), the shared entry point consumed by both main.py (CLI) and app/api/main.py (FastAPI). Not for adding a new Tool (use add-rag-tool) or a new LangGraph pipeline stage (use add-langgraph-agent-node) - this skill is for the runtime-agnostic entry point and the HTTP surface wrapping it. Read CONTEXT.md first; if the endpoint introduces a new domain concept, use domain-modeling to name it before writing code.

## Procedure
1. Read app/api/routes/ask.py and app/api/routes/health.py as reference: routes are thin - they extract app.state.runtime (set once in app/api/main.py's lifespan), call one runtime method, translate the result/exception into a response model, and do no orchestration logic of their own.
2. If the endpoint needs new runtime behavior, add a public method to AssistantRuntime (app/runtime/assistant_runtime.py) rather than reimplementing logic in the route - the runtime is the reusable, interface-agnostic entry point shared by main.py (CLI) and the API, so orchestration belongs there, not in app/api/.
3. Define request/response Pydantic models in app/api/models/requests.py and app/api/models/responses.py, following the existing AskRequest/AskResponse/HealthResponse naming and validation style (Field(..., min_length=..., description=...) for inputs).
4. Create app/api/routes/<name>.py with an APIRouter (tags=["<name>"]) and an async def handler that: (1) pulls runtime = request.app.state.runtime, (2) awaits asyncio.to_thread(runtime.<method>, ...) if the runtime call is synchronous/blocking (matches ask.py's pattern - LangGraph invoke is sync, so it must not block the event loop), (3) wraps the call in try/except and raises HTTPException(500, detail="<generic message>") on unexpected errors without leaking the raw exception string to the client (log the real error via structlog, return a generic detail).
5. Register the new router in app/api/main.py: app.include_router(<name>.router), following the existing health/ask registration order.
6. Update CONTEXT.md if the endpoint introduces a new domain-level concept (not just a new HTTP path) - most new endpoints won't need this, since they typically expose existing AssistantRuntime/AgentState concepts, not new ones.
7. Use the tdd skill to write seam-only tests at two levels: (1) the route itself, using fastapi.testclient.TestClient against a minimal FastAPI app with app.state.runtime replaced by a mock (see tests/api/test_ask_route.py) - never boot the real lifespan/vector store in a route test; (2) any new AssistantRuntime method, mocking its internal dependencies at their defining modules the way tests/runtime/test_assistant_runtime.py mocks app.config.env_validator.validate_environment, app.rag.vector_store.initialize_vector_store, and app.agents.graph.get_graph individually (AssistantRuntime.setup() imports these inside the function body specifically to keep them mockable and side-effect-free at import time - preserve that pattern for any new runtime method with heavy dependencies).
8. Run `uv run pytest` for the full suite, then clean up coverage artifacts (`rm -rf htmlcov coverage.xml .coverage`).

## Pitfalls
- Never call a synchronous/blocking method (like AssistantRuntime.run_question, which invokes LangGraph) directly from an async route handler - it blocks the whole event loop for every concurrent request. Always route through asyncio.to_thread(...), matching app/api/routes/ask.py.
- Don't let an unexpected exception's raw str(exc) reach the HTTP response body - it can leak internal paths, prompts, or stack details to callers. Log the full error via structlog (error=str(exc), error_type=type(exc).__name__) but return a generic HTTPException detail string, exactly as ask.py does.
- Don't test a new route by booting the real app.api.main app or its lifespan (which calls AssistantRuntime.setup() and tries to initialize a real vector store/LLM client) - build a minimal FastAPI app with just the router under test and a mocked app.state.runtime, per tests/api/test_ask_route.py and tests/api/test_health_route.py.
- AssistantRuntime.setup() imports its dependencies (env_validator, logging_config, vector_store, graph) inside the function body, not at module level, specifically so tests can mock each one at its defining module without triggering real side effects (API key validation, vector store loads) at import time. Don't hoist these imports to module level when extending setup() - it reintroduces the same import-time-crash class of bug already fixed in app/agents/planner.py, reviewer.py, and graph.py's old module-level `llm = get_llm()` pattern.
- AssistantRuntime is the single source of truth for orchestration - if you find yourself writing multi-step logic inside a route handler (not just extract-call-translate), that logic belongs on AssistantRuntime instead, so main.py (CLI) and the API don't diverge in behavior.

## Verification
1. The new route function follows the extract-runtime / await-to-thread-if-sync / try-except-translate shape of ask.py, with no orchestration logic inlined in the route.
2. New route tests use TestClient against a minimal app with a mocked app.state.runtime - they do not hit a real LLM, vector store, or LangGraph invocation.
3. Any new AssistantRuntime method has tests that mock its internal dependencies at their defining modules, following tests/runtime/test_assistant_runtime.py's fixture pattern.
4. `uv run pytest` passes with the new seam tests included, and coverage for the new route/runtime method is not 0% (check the coverage report by module, not just the pass/fail count).
5. code-review (Standards + Spec) run against the diff before considering the work complete, per this repo's established review discipline.