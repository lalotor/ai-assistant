from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    """Request model for the /ask endpoint."""

    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The question to send to the AI assistant.",
        examples=["What does the architecture_advisor tool do?"],
    )
    trace_id: str | None = Field(
        default=None,
        description="Optional caller-supplied trace ID. A UUID is generated if omitted.",
    )
