---
name: "add-langgraph-agent-node"
description: "Scaffold a new node in the ai-assistant's LangGraph pipeline (planner/worker/reviewer), following the repo's contracts, structlog, and stage-timing conventions."
version: 1
created: "2026-09-23"
updated: "2026-09-23"
---
## When to Use
Use when adding a new stage/node to the ai-assistant's LangGraph workflow (app/agents/graph.py), e.g. extending the fixed Planner -> Worker -> Reviewer sequence with a new stage (per CONTEXT.md terminology). Not for adding a new Tool (a callable the Worker invokes) - use add-rag-tool for that instead. Read CONTEXT.md first so the new node's naming matches existing domain vocabulary (Plan, Draft Answer, Final Answer, etc.), and check with the user via the grilling skill before introducing a new domain term not yet in CONTEXT.md.

## Procedure
1. Read CONTEXT.md first. If the new node introduces a concept not already in the glossary (e.g. a new stage output), call the domain-modeling skill to name and record it before writing code, rather than inventing ad hoc terminology.
2. Read app/agents/planner.py, worker.py, and reviewer.py as reference for the established node shape: a `<name>_node(state: AgentState) -> AgentState` function, structlog `logger.info("node_started", node="<name>_node", ...)` at entry, a `started = datetime.now()` timestamp, the node's core logic, then `state.stage_timings["<name>"] = {"started_at": started, "ended_at": datetime.now()}` before returning state.
3. Add any new fields the node reads or writes to AgentState in app/contracts/agent.py as Optional[...] fields with sensible defaults, matching the existing style (plan, selected_tool, draft_answer, etc.). Do not add required (non-Optional) fields without a default unless every existing caller of AgentState(...) already supplies them.
4. If the node needs an LLM call with structured output, follow the planner.py/reviewer.py pattern: define a Pydantic response model in app/contracts/ (or reuse ToolDecision/ReviewResult if applicable), call `llm.with_structured_output(YourModel)`, and load prompts via `app.prompts.format_prompt("<name>.txt", **kwargs)` with a new prompt template file in app/prompts/.
5. Wire the node into app/agents/graph.py: `workflow.add_node("<name>", <name>_node)` and add the appropriate `workflow.add_edge(...)` calls. This repo's graph is currently a fixed linear sequence (no conditional routing) - preserve that shape unless the user has explicitly asked for branching logic.
6. Update app/tracing.py's build_execution_trace() to add a `_build_stage_event(...)` call for the new stage if it should appear in the ExecutionTrace, and add the corresponding `<name>_events: list[StageEvent]` field to ExecutionTrace in app/contracts/trace.py.
7. Use the tdd skill to write seam-only tests for the new node: test `<name>_node(state) -> AgentState` through its public signature, mocking the LLM (app.utils.llm.get_llm) and any other system boundaries, following the pattern in tests/test_tracing.py or tests/tools/test_doc_retriever.py.
8. Run `uv run pytest` to confirm the full suite still passes, then clean up coverage artifacts (`rm -rf htmlcov coverage.xml .coverage`).
9. Consider running the code-review skill (Standards + Spec axes) on the new node before considering the work done, especially if AgentState or the graph's edge structure changed.

## Pitfalls
- This repo's graph (app/agents/graph.py) has no conditional/branching edges today - it's a fixed linear sequence. Don't introduce conditional routing without confirming with the user first; it's a meaningful architectural change, not just a new node.
- AgentState fields must stay Optional with defaults unless you audit every place AgentState(...) is constructed (currently only app/runtime/assistant_runtime.py's run_question). A new required field will break that call site.
- Per CONTEXT.md, 'Plan' is the Planner's one-line tool-selection rationale, not a multi-step plan - don't reuse that field for a new node's different concept; give it its own name and glossary entry instead.
- stage_timings is a plain dict on AgentState (Dict[str, Any]), not a structured type - follow the existing started_at/ended_at shape exactly so app/tracing.py's _build_stage_event() can consume it without changes to its lookup logic.
- If the new node calls an LLM, mock app.utils.llm.get_llm at the test seam - never let tests hit real OpenAI (matches the established convention from doc_retriever/planner/reviewer tests).

## Verification
1. The new node function has the same `<name>_node(state: AgentState) -> AgentState` shape as planner_node/worker_node/reviewer_node.
2. `uv run pytest` passes with the new node's seam tests included, and the full suite has no new failures.
3. app/agents/graph.py compiles (`python -c "from app.agents.graph import get_graph; get_graph()"`) without errors.
4. If AgentState or ExecutionTrace changed, CONTEXT.md is updated if a new domain term was introduced.
5. code-review (Standards + Spec) run against the diff before considering the work complete, per this repo's established review discipline.