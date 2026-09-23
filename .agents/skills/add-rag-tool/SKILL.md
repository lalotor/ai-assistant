---
name: "add-rag-tool"
description: "Scaffold a new Tool for the ai-assistant's Worker to invoke, following the registry, contracts, and prompt-template conventions in app/tools/."
version: 1
created: "2026-09-23"
updated: "2026-09-23"
---
## When to Use
Use when adding a new Tool (per CONTEXT.md: a callable capability the Worker invokes, chosen by the Planner's Tool Decision) to the ai-assistant, e.g. a new capability alongside Code Explainer, Doc Retriever, and Architecture Advisor. Not for adding a new pipeline stage/node - use add-langgraph-agent-node for that. Read CONTEXT.md first for the Tool/Tool Decision vocabulary.

## Procedure
1. Read CONTEXT.md's Tools section, then read app/tools/code_explainer.py and app/tools/architecture_advisor.py as the two simplest reference examples (a single public function calling an LLM with a prompt template) before looking at the more complex app/tools/doc_retriever.py if the new tool needs multi-step retrieval logic.
2. Define the tool's Input/Output Pydantic models in app/contracts/tools.py, following the existing `<Name>Input`/`<Name>Output` naming (ArchInput/ArchOutput, CodeInput/CodeOutput, DocInput/DocOutput).
3. Create app/tools/<name>.py with a single public function `<name>(input: <Name>Input) -> <Name>Output`, following the established shape: get_llm() (only if the tool needs an LLM, called inside the function, never at module level - a module-level `llm = get_llm()` is a known anti-pattern this repo already removed once, since it was dead code that also crashed test collection when OPENAI_API_KEY wasn't loaded), format_prompt("<name>.txt", **kwargs) to build the prompt, structlog logging at entry, and return the Output model. If the tool has multiple internal steps, keep them as private `_`-prefixed helpers behind this one public function (see app/tools/doc_retriever.py's collapsed-seam pattern) rather than exposing several public functions.
4. Add the prompt template file app/prompts/<name>.txt if the tool calls an LLM, following the plain-instruction style of the existing templates (see app/prompts/architecture_advisor.txt or code_explainer.txt for the simplest examples).
5. Register the tool in app/tools/registry.py: add a `"<name>": {"function": <name>, "description": "...", "invoke": _invoke_<name>}` entry, plus a private `_invoke_<name>(tool_input: dict, user_input: str) -> dict` adapter following the pattern of `_invoke_code_explainer`/`_invoke_doc_retriever`/`_invoke_architecture_advisor`: extract the right tool_input key (falling back to user_input), call the tool function, and return a uniform `{"result": str, "sources": list|None, "retrieval_trace": ...|None}` dict. worker_node() dispatches through this invoke() adapter generically (Candidate 4 from the improve-codebase-architecture scan was resolved this way) and needs no per-tool changes - adding a tool now only touches registry.py, not worker.py. The description is read directly into the Planner's tool-selection prompt, so write it as a clear, distinguishing trigger condition (see existing descriptions for the pattern: 'Use when...').
6. Add the new tool name to the Literal[...] type in ToolDecision.tool (app/contracts/tools.py) so the Planner's structured LLM output can select it, and add an example tool_input entry to ToolDecision's model_config examples.
7. Update CONTEXT.md's Tools section with the new tool's one-line definition, matching the existing entries' style (what it's used for, in terms of the user's question).
8. Use the tdd skill to write seam-only tests for the new tool's public function (mocking get_llm/format_prompt or other system boundaries), AND for its registry invoke() adapter (mocking the tool function itself, following tests/tools/test_registry.py's pattern) - these are two distinct seams, test both.
9. Run `uv run pytest` for the full suite, then clean up coverage artifacts (`rm -rf htmlcov coverage.xml .coverage`).

## Pitfalls
- Forgetting to add the new tool name to ToolDecision.tool's Literal[...] type means the Planner's structured LLM output can never select it, even if the registry and worker dispatch are wired correctly - the failure mode is silent (planner just never picks it), not an error.
- The registry's "description" field is not just documentation - it is read verbatim into the Planner's tool-selection prompt (app/prompts/planner.txt's {tool_options}). A vague or overlapping description will cause misrouting between tools.
- worker.py's tool dispatch was refactored (Candidate 4 in the architecture scan) into a generic invoke()-adapter pattern - adding a tool now only requires registry.py's invoke() adapter, not touching worker.py. If this ever regresses back to an if/elif chain, that assumption breaks.
- If the tool does multi-step work internally, don't expose each step as a separate public function (the doc_retriever.py anti-pattern this repo already fixed once) - keep one public entry point and `_`-prefix the internals.
- Every LLM call in tools must go through app.utils.llm.get_llm() and app.prompts.format_prompt() for consistency with logging/tracing conventions - don't construct a LangChain client or format a prompt string directly in a new tool.

## Verification
1. The new tool has exactly one public function with the `<name>(input: <Name>Input) -> <Name>Output` signature.
2. ToolDecision.tool's Literal[...] includes the new tool name, and the registry description is distinguishing enough that the Planner selects it correctly (verify manually via `python main.py --question "..." --json` with a question targeting the new tool, or via a planner-focused test).
3. `uv run pytest` passes with new seam tests for the tool included.
4. CONTEXT.md's Tools section documents the new tool.
5. code-review (Standards + Spec) run against the diff before considering the work complete.