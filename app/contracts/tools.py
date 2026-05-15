from typing import Literal, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class ToolDecision(BaseModel):
    """Structured output model for LLM tool selection decision."""

    tool: Literal["code_explainer", "doc_retriever", "architecture_advisor", "none"] = (
        Field(
            description="The tool to use based on the user's question. Use 'none' for direct answers."
        )
    )
    reason: str = Field(description="Brief explanation of why this tool was selected")
    tool_input: Dict[str, Any] = Field(
        default_factory=dict,
        description="""Input parameters for the selected tool. Expected keys:
        - code_explainer: {'code': str}
        - doc_retriever: {'query': str}
        - architecture_advisor: {'question': str}
        - none: {}
        """,
        json_schema_extra={
            "additionalProperties": False,
            "properties": {
                "code": {"type": "string"},
                "query": {"type": "string"},
                "question": {"type": "string"}
            },
            "examples": [
                {"code": "def add(a, b): return a + b"},
                {"query": "How to use FastAPI?"},
                {"question": "Should I use microservices?"},
            ]
        }
    )

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "tool": "code_explainer",
                    "reason": "User provided a code snippet that needs explanation",
                    "tool_input": {"code": "def add(a, b): return a + b"},
                },
                {
                    "tool": "doc_retriever",
                    "reason": "User is asking about documentation",
                    "tool_input": {"query": "How to use FastAPI?"},
                },
                {
                    "tool": "architecture_advisor",
                    "reason": "User needs architecture guidance",
                    "tool_input": {"question": "Should I use microservices?"},
                },
            ]
        }
    )

class ArchInput(BaseModel):
    question: str

class ArchOutput(BaseModel):
    advice: str

class CodeInput(BaseModel):
    code: str

class CodeOutput(BaseModel):
    explanation: str

class DocInput(BaseModel):
    query: str

class DocOutput(BaseModel):
    context: str
