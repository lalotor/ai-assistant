"""Unit tests for the reviewer_node() seam in app.agents.reviewer.

reviewer_node(state: AgentState) -> AgentState is the module's only
public interface. The LLM boundary (app.agents.reviewer.get_llm) is
mocked so these run without network access or API cost.
"""
import pytest

from app.agents.reviewer import reviewer_node
from app.contracts.agent import AgentState


def make_structured_llm(mocker, final_answer="the final answer", feedback="looks good", usage_metadata=None):
    """Mirrors tests/agents/test_planner.py's make_structured_llm: builds a
    mock get_llm() replacement whose with_structured_output(...,
    include_raw=True) returns {"raw": ..., "parsed": ...}, matching
    LangChain's include_raw=True contract.
    """
    parsed = mocker.Mock(final_answer=final_answer, feedback=feedback)
    raw = mocker.Mock(usage_metadata=usage_metadata)
    mock_structured = mocker.Mock()
    mock_structured.invoke.return_value = {"raw": raw, "parsed": parsed}
    mock_llm = mocker.Mock()
    mock_llm.model_name = "gpt-5.4-mini"
    mock_llm.with_structured_output.return_value = mock_structured
    return mock_llm


def make_state(**overrides) -> AgentState:
    defaults = dict(
        user_input="what is X?",
        draft_answer="Tool result:\nsome context",
        selected_tool="doc_retriever",
        trace_id="trace-1",
    )
    defaults.update(overrides)
    return AgentState(**defaults)


@pytest.mark.unit
class TestReviewerNode:
    def test_sets_final_answer_and_review_feedback_from_structured_output(self, mocker):
        mock_llm = make_structured_llm(mocker, final_answer="X is ...", feedback="clear and grounded")
        mocker.patch("app.agents.reviewer.get_llm", return_value=mock_llm)
        state = make_state()

        result = reviewer_node(state)

        assert result.final_answer == "X is ..."
        assert result.review_feedback == "clear and grounded"

    def test_records_stage_timing(self, mocker):
        mock_llm = make_structured_llm(mocker)
        mocker.patch("app.agents.reviewer.get_llm", return_value=mock_llm)
        state = make_state()

        result = reviewer_node(state)

        assert "reviewer" in result.stage_timings
        assert result.stage_timings["reviewer"]["started_at"] is not None
        assert result.stage_timings["reviewer"]["ended_at"] is not None


@pytest.mark.unit
class TestReviewerNodeLlmUsage:
    """Week 9: reviewer_node records one LLM call and its token usage into
    state.stage_llm_usage["reviewer"], mirroring the planner's pattern."""

    def test_records_one_llm_call_and_token_usage(self, mocker):
        mock_llm = make_structured_llm(
            mocker,
            usage_metadata={"input_tokens": 150, "output_tokens": 40, "total_tokens": 190},
        )
        mocker.patch("app.agents.reviewer.get_llm", return_value=mock_llm)
        state = make_state()

        result = reviewer_node(state)

        assert result.stage_llm_usage["reviewer"]["llm_calls"] == 1
        assert result.stage_llm_usage["reviewer"]["token_usage"] == {
            "input_tokens": 150, "output_tokens": 40, "model": "gpt-5.4-mini"
        }

    def test_records_none_token_usage_when_the_provider_gives_none(self, mocker):
        mock_llm = make_structured_llm(mocker, usage_metadata=None)
        mocker.patch("app.agents.reviewer.get_llm", return_value=mock_llm)
        state = make_state()

        result = reviewer_node(state)

        assert result.stage_llm_usage["reviewer"]["llm_calls"] == 1
        assert result.stage_llm_usage["reviewer"]["token_usage"] is None
