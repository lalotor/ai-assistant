import asyncio

import structlog
from fastapi import APIRouter, HTTPException, Request, status

from app.api.models.responses import TraceResponse

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["trace"])


@router.get(
    "/trace/{trace_id}",
    response_model=TraceResponse,
    summary="Retrieve an execution trace",
)
async def get_trace(trace_id: str, request: Request) -> TraceResponse:
    """Return a persisted trace, or 404 when it is unknown or expired."""
    runtime = request.app.state.runtime
    try:
        execution_trace = await asyncio.to_thread(runtime.get_trace, trace_id)
    except Exception as exc:
        logger.error(
            "trace_lookup_failed",
            trace_id=trace_id,
            error_type=type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The execution trace could not be retrieved.",
        ) from exc

    if execution_trace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution trace not found.",
        )

    return TraceResponse(trace_id=trace_id, execution_trace=execution_trace)
