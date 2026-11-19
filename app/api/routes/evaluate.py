import asyncio

import structlog
from fastapi import APIRouter, HTTPException, Request, status

from app.api.models.requests import EvaluationRequest
from app.api.models.responses import EvaluationResponse

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["evaluation"])


@router.post(
    "/evaluate",
    response_model=EvaluationResponse,
    summary="Run an evaluation dataset",
    description=(
        "Runs the selected built-in dataset synchronously and returns its "
        "aggregate metrics and per-question results. Execution is moved to a "
        "worker thread so the API event loop remains responsive."
    ),
)
async def evaluate(
    body: EvaluationRequest,
    request: Request,
) -> EvaluationResponse:
    """Run a bounded, server-selected evaluation dataset."""
    runtime = request.app.state.runtime
    try:
        result = await asyncio.to_thread(
            runtime.run_evaluation,
            body.dataset,
            revision_enabled=body.revision_enabled,
        )
    except Exception as exc:
        logger.error(
            "evaluation_request_failed",
            dataset=body.dataset,
            error_type=type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The evaluation could not be completed.",
        ) from exc

    return EvaluationResponse(**result)
