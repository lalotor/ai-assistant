"""Shared stage timing/usage recording for agent nodes."""
from datetime import datetime
from typing import Optional

from app.contracts.agent import AgentState


def record_stage_metrics(
    state: AgentState,
    stage: str,
    started: datetime,
    *,
    llm_calls: int,
    token_usage: Optional[dict],
) -> None:
    """Record one stage's timing and LLM usage on the agent state."""
    if state.stage_timings is None:
        state.stage_timings = {}
    state.stage_timings[stage] = {
        "started_at": started,
        "ended_at": datetime.now(),
    }

    if state.stage_llm_usage is None:
        state.stage_llm_usage = {}
    state.stage_llm_usage[stage] = {
        "llm_calls": llm_calls,
        "token_usage": token_usage,
    }
