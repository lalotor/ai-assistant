"""Shared review decision/outcome types.

Kept in a small module so the graph state, trace, response contract, and
API schema all use the same closed value sets without importing the agent
state module into the tracing layer.
"""
from typing import Literal

ReviewDecision = Literal["approve", "revise", "abstain"]
ReviewOutcome = Literal[
    "approved",
    "revised",
    "abstained",
    "budget_exhausted",
    "revision_skipped",
]
