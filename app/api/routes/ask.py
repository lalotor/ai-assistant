import asyncio
import structlog
from fastapi import APIRouter, HTTPException, Request, status

from app.api.models.requests import AskRequest
from app.api.models.responses import AskResponse

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["ask"])


@router.post(
    "/ask",
    response_model=AskResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask the AI assistant a question",
    description=(
        "Runs the question through the full multi-agent graph "
        "(Planner → Worker → Reviewer) and returns the final answer "
        "together with an execution trace."
    ),
)
async def ask(body: AskRequest, request: Request) -> AskResponse:
    """Send a question to the AI assistant and get a structured answer.

    The endpoint offloads the synchronous LangGraph invocation to a thread
    pool via ``asyncio.to_thread`` so the event loop stays free for other
    concurrent requests.

    Args:
        body: Validated request payload (question + optional trace_id).
        request: FastAPI request object used to access ``app.state.runtime``.

    Returns:
        AskResponse with the final answer and full execution trace.

    Raises:
        HTTPException 500: If the agent graph raises an unexpected error.
    """
    runtime = request.app.state.runtime

    logger.info(
        "ask_request_received",
        question_length=len(body.question),
        trace_id=body.trace_id,
    )

    try:
        # run_question is synchronous (LangGraph invoke); run it in a thread
        # pool so we don't block the async event loop.
        response = await asyncio.to_thread(
            runtime.run_question,
            body.question,
            body.trace_id,
        )
    except Exception as exc:
        logger.error(
            "ask_request_failed",
            error=str(exc),
            error_type=type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The agent encountered an error processing your question.",
        ) from exc

    trace = response.execution_trace
    trace_id = trace.trace_id if trace else (body.trace_id or "unknown")

    logger.info("ask_request_completed", trace_id=trace_id)

    return AskResponse(
        trace_id=trace_id,
        answer=response.final_answer,
        sources=response.retrieved_sources,
    )
