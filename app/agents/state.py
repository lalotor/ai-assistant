from typing import TypedDict, Literal

class AssistantState(TypedDict):
    input: str
    decision: Literal["direct_answer", "call_tool"]
    tool_result: str | None
    output: str | None
