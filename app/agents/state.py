from typing import TypedDict, Literal

class AssistantState(TypedDict):
    input: str
    decision: Literal["direct_answer", "call_tool"]
    selected_tool: str | None  # The tool selected by LLM (code_explainer, doc_retriever, architecture_advisor, none)
    tool_reason: str | None  # Reason for tool selection
    tool_result: str | None
    output: str | None
