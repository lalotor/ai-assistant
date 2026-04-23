from typing import Literal
from pydantic import BaseModel, Field

class ToolDecision(BaseModel):
    """Structured output model for LLM tool selection decision."""
    
    tool: Literal["code_explainer", "doc_retriever", "architecture_advisor", "none"] = Field(
        description="The tool to use based on the user's question. Use 'none' for direct answers."
    )
    reason: str = Field(
        description="Brief explanation of why this tool was selected"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "tool": "code_explainer",
                "reason": "User provided a code snippet that needs explanation"
            }
        }
