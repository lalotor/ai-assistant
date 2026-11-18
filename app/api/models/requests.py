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
    revision_enabled: bool = Field(
        default=False,
        description=(
            "Enable the bounded review-and-revision loop. When true, a "
            "reviewer's revise decision may trigger at most one revision "
            "before the final review."
        ),
    )
