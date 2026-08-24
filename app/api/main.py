from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from app.api.routes import ask, health
from app.runtime.assistant_runtime import AssistantRuntime

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown of the AssistantRuntime.

    On startup: initialise the runtime once (loads env, vector store, graph).
    On shutdown: log teardown — add cleanup hooks here if needed in future.
    """
    logger.info("api_startup_begin")
    runtime = AssistantRuntime()
    runtime.setup()
    app.state.runtime = runtime
    logger.info("api_startup_complete")

    yield  # application runs here

    logger.info("api_shutdown")


app = FastAPI(
    title="AI Engineering Assistant",
    description=(
        "Multi-agent AI assistant exposing RAG, code analysis, "
        "and architecture reasoning via a REST API."
    ),
    version="0.8.0",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(ask.router)
