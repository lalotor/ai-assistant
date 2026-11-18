"""Unit tests for the revision_node() seam in app.agents.revision.

revision_node(state: AgentState) -> AgentState is the module's public
interface. The LLM boundary (app.agents.revision.get_llm) is mocked so
these run without network access or API cost.
"""
import pytest
from structlog.testing import capture_logs

from app.agents.revision import revision_node
from app.contracts.agent import AgentState
from app.contracts.trace import RetrievalTrace


def make_llm(mocker, content="the revised answer", usage_metadata=None):
    response = mocker.Mock(content=content, usage_metadata=usage_metadata)
    mock_llm = mocker.Mock()
    mock_llm.model_name = "gpt-5.4-mini"
    mock_llm.invoke.return_value = response
    return mock_llm


def make_state(**overrides) -> AgentState:
    defaults = dict(
        user_input="what is X?",
        draft_answer="Tool result:\nthe original draft",
        tool_output="the original draft",
        selected_tool="doc_retriever",
        retrieved_sources=["source.md"],
        revision_feedback="Name the three source types explicitly.",
        review_feedback="stale feedback",
        revision_enabled=True,
        trace_id="trace-1",
    )
    defaults.update(overrides)
    return AgentState(**defaults)


@pytest.mark.unit
class TestRevisionNode:
    def test_revises_the_draft_and_increments_the_revision_count(self, mocker):
        mock_llm = make_llm(
            mocker,
            content="the revised answer",
            usage_metadata={"input_tokens": 200, "output_tokens": 50, "total_tokens": 250},
        )
        mocker.patch("app.agents.revision.get_llm", return_value=mock_llm)
        state = make_state(retrieval_trace=RetrievalTrace(query="what is X?"))

        result = revision_node(state)

        assert result.draft_answer == "the revised answer"
        assert result.revision_count == 1
        assert result.review_decision is None
        assert result.retrieved_sources == ["source.md"]
        assert result.retrieval_trace == RetrievalTrace(query="what is X?")
        assert result.stage_llm_usage["revision"] == {
            "llm_calls": 1,
            "token_usage": {
                "input_tokens": 200,
                "output_tokens": 50,
                "model": "gpt-5.4-mini",
            },
        }

    def test_records_the_revision_stage_timing(self, mocker):
        mocker.patch("app.agents.revision.get_llm", return_value=make_llm(mocker))
        state = make_state()

        result = revision_node(state)

        assert result.stage_timings["revision"]["started_at"] is not None
        assert result.stage_timings["revision"]["ended_at"] is not None

    def test_revision_prompt_contains_question_draft_feedback_evidence_and_sources(self, mocker):
        mock_llm = make_llm(mocker)
        mocker.patch("app.agents.revision.get_llm", return_value=mock_llm)
        state = make_state()

        revision_node(state)

        prompt = mock_llm.invoke.call_args.args[0]
        assert "what is X?" in prompt
        assert "the original draft" in prompt
        assert "Name the three source types explicitly." in prompt
        assert "source.md" in prompt
        assert "doc_retriever" in prompt
        assert "stale feedback" not in prompt

    def test_does_not_log_question_draft_feedback_or_evidence_content(self, mocker):
        secret = "revision-private-needle-91ac"
        mocker.patch("app.agents.revision.get_llm", return_value=make_llm(mocker, content=secret))
        state = make_state(
            user_input=secret,
            draft_answer=secret,
            tool_output=secret,
            revision_feedback=secret,
            retrieved_sources=[secret],
        )

        with capture_logs() as logs:
            revision_node(state)

        assert all(secret not in repr(event) for event in logs)

    def test_empty_revision_output_raises_without_consuming_the_budget(self, mocker):
        mocker.patch("app.agents.revision.get_llm", return_value=make_llm(mocker, content="   "))
        state = make_state()

        with pytest.raises(ValueError, match="empty answer"):
            revision_node(state)

        assert state.revision_count == 0
        assert state.draft_answer == "Tool result:\nthe original draft"

    def test_revision_failure_propagates_without_mutating_the_draft(self, mocker):
        mock_llm = make_llm(mocker)
        mock_llm.invoke.side_effect = TimeoutError("provider timed out")
        mocker.patch("app.agents.revision.get_llm", return_value=mock_llm)
        state = make_state()

        with pytest.raises(TimeoutError):
            revision_node(state)

        assert state.revision_count == 0
        assert state.draft_answer == "Tool result:\nthe original draft"
