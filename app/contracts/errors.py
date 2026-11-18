from typing import Any


class WorkflowStageError(RuntimeError):
    """A graph-stage failure with safe metadata for failure tracing."""

    def __init__(
        self,
        *,
        stage: str,
        failure_category: str,
        failure_type: str,
        stage_timings: dict[str, dict[str, Any]],
        review_state: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(f"{stage} stage failed ({failure_category}).")
        self.stage = stage
        self.failure_category = failure_category
        self.failure_type = failure_type
        self.stage_timings = stage_timings
        self.review_state = review_state
