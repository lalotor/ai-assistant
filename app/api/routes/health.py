from fastapi import APIRouter, Request

from app.api.models.responses import HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Returns service status and whether the runtime is fully initialised.",
)
async def health(request: Request) -> HealthResponse:
    """Lightweight liveness + readiness check.

    The ``runtime_initialized`` field lets orchestrators (e.g. Kubernetes
    readiness probes) distinguish between a process that is alive but still
    warming up vs one that is ready to serve traffic.
    """
    runtime = request.app.state.runtime
    return HealthResponse(
        status="ok",
        runtime_initialized=runtime._is_initialized,
    )
