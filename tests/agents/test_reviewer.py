"""Unit tests for the reviewer_node() seam in app.agents.reviewer.

reviewer_node(state: AgentState) -> AgentState is the module's only
public interface. The LLM boundary (app.agents.reviewer.get_llm) is
mocked so these run without network access or API cost.
"""
import pytest
from structlog.testing import capture_logs

from app.agents.reviewer import reviewer_node
from app.contracts.agent import AgentState


def make_structured_llm(
    mocker,
    final_answer="the final answer",
    feedback="looks good",
    evidence_sufficient=True,
    decision="approve",
    usage_metadata=None,
):
    """Mirrors tests/agents/test_planner.py's make_structured_llm: builds a
    mock get_llm() replacement whose with_structured_output(...,
    include_raw=True) returns {"raw": ..., "parsed": ...}, matching
    LangChain's include_raw=True contract.
    """
    parsed = mocker.Mock(
        decision=decision,
        final_answer=final_answer,
        feedback=feedback,
        evidence_sufficient=evidence_sufficient,
    )
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
        retrieved_sources=["source.md"],
        revision_enabled=True,
        trace_id="trace-1",
    )
    defaults.update(overrides)
    return AgentState(**defaults)


@pytest.mark.unit
class TestReviewerNode:
    def test_does_not_log_user_input_draft_or_review_feedback(self, mocker):
        secret = "review-private-needle-61ab"
        mocker.patch(
            "app.agents.reviewer.get_llm",
            return_value=make_structured_llm(mocker, feedback=secret),
        )
        state = make_state(user_input=secret, draft_answer=secret)

        with capture_logs() as logs:
            reviewer_node(state)

        assert all(secret not in repr(event) for event in logs)

    def test_sets_final_answer_and_review_feedback_from_structured_output(self, mocker):
        mock_llm = make_structured_llm(mocker, final_answer="X is ...", feedback="clear and grounded")
        mocker.patch("app.agents.reviewer.get_llm", return_value=mock_llm)
        state = make_state()

        result = reviewer_node(state)

        assert result.final_answer == "X is ..."
        assert result.review_feedback == "clear and grounded"

    def test_approves_and_records_the_decision(self, mocker):
        mock_llm = make_structured_llm(mocker, decision="approve", final_answer="X is ...")
        mocker.patch("app.agents.reviewer.get_llm", return_value=mock_llm)
        state = make_state()

        result = reviewer_node(state)

        assert result.review_decision == "approve"
        assert result.review_outcome == "approved"
        assert result.revision_count == 0
        assert result.final_answer == "X is ..."
        assert result.initial_review_decision == "approve"
        assert result.initial_review_feedback == "looks good"

    def test_final_review_receives_the_original_tool_output_and_sources(self, mocker):
        mock_llm = make_structured_llm(mocker, decision="approve")
        mocker.patch("app.agents.reviewer.get_llm", return_value=mock_llm)
        state = make_state(
            revision_count=1,
            draft_answer="the revised answer",
            tool_output="ProcessController calls computeDiff(request.getJobId(), ...)",
            retrieved_sources=["ProcessController.java", "DiffService.java"],
        )

        reviewer_node(state)

        prompt = mock_llm.with_structured_output.return_value.invoke.call_args.args[0]
        assert "Original Worker tool output" in prompt
        assert "ProcessController calls computeDiff" in prompt
        assert "ProcessController.java, DiffService.java" in prompt

    def test_initial_review_uses_the_worker_draft_as_evidence(self, mocker):
        mock_llm = make_structured_llm(mocker, decision="approve")
        mocker.patch("app.agents.reviewer.get_llm", return_value=mock_llm)
        state = make_state()

        reviewer_node(state)

        prompt = mock_llm.with_structured_output.return_value.invoke.call_args.args[0]
        assert "draft above is the Worker's raw tool output" in prompt

    def test_requests_a_revision_with_actionable_feedback(self, mocker):
        feedback = "Name the three source types explicitly; the evidence lists them."
        mock_llm = make_structured_llm(mocker, decision="revise", feedback=feedback)
        mocker.patch("app.agents.reviewer.get_llm", return_value=mock_llm)
        state = make_state()

        result = reviewer_node(state)

        assert result.review_decision == "revise"
        assert result.revision_feedback == feedback
        assert result.review_outcome is None
        assert result.final_answer is None
        assert result.initial_review_decision == "revise"
        assert result.initial_review_feedback == feedback

    def test_single_pass_revise_uses_the_reviewers_answer_without_revision(self, mocker):
        mock_llm = make_structured_llm(
            mocker,
            decision="revise",
            final_answer="the reviewer's improved answer",
            feedback="Add the missing source types.",
        )
        mocker.patch("app.agents.reviewer.get_llm", return_value=mock_llm)
        state = make_state(revision_enabled=False)

        result = reviewer_node(state)

        assert result.review_decision == "revise"
        assert result.review_outcome == "revision_skipped"
        assert result.final_answer == "the reviewer's improved answer"
        assert result.revision_count == 0

    def test_single_pass_revise_without_a_new_answer_abstains(self, mocker):
        mock_llm = make_structured_llm(
            mocker,
            decision="revise",
            final_answer="Tool result:\nsome context",
            feedback="Add the missing detail.",
        )
        mocker.patch("app.agents.reviewer.get_llm", return_value=mock_llm)
        state = make_state(revision_enabled=False)

        result = reviewer_node(state)

        assert result.review_decision == "abstain"
        assert result.review_outcome == "abstained"
        assert result.initial_review_decision == "revise"
        assert result.final_answer == "I couldn't produce a reliable answer to this question."

    def test_no_tool_route_never_requests_a_revision(self, mocker):
        mock_llm = make_structured_llm(
            mocker,
            decision="revise",
            final_answer="No technical question or no tool selected, try again",
            feedback="No tool output is available.",
        )
        mocker.patch("app.agents.reviewer.get_llm", return_value=mock_llm)
        state = make_state(selected_tool="none", retrieved_sources=None)

        result = reviewer_node(state)

        assert result.review_outcome == "revision_skipped"
        assert result.final_answer == "No technical question or no tool selected, try again"
        prompt = mock_llm.with_structured_output.return_value.invoke.call_args.args[0]
        assert "No revision attempt is available" in prompt

    def test_revise_without_actionable_feedback_does_not_request_revision(self, mocker):
        mock_llm = make_structured_llm(
            mocker,
            decision="revise",
            final_answer="the reviewer's improved answer",
            feedback="   ",
        )
        mocker.patch("app.agents.reviewer.get_llm", return_value=mock_llm)
        state = make_state()

        result = reviewer_node(state)

        assert result.review_outcome == "revision_skipped"
        assert result.final_answer == "the reviewer's improved answer"
        assert result.revision_feedback is None

    def test_final_review_budget_exhausted_finalizes_with_a_limitation(self, mocker):
        mock_llm = make_structured_llm(
            mocker,
            decision="revise",
            final_answer="the revised answer",
            feedback="The answer still omits the source types.",
        )
        mocker.patch("app.agents.reviewer.get_llm", return_value=mock_llm)
        state = make_state(revision_count=1, draft_answer="the revised answer")

        result = reviewer_node(state)

        assert result.review_decision == "revise"
        assert result.review_outcome == "budget_exhausted"
        assert result.final_answer.startswith("the revised answer")
        assert "revised once" in result.final_answer
        assert result.revision_count == 1

    def test_budget_exhaustion_without_a_final_answer_uses_a_safe_limitation(self, mocker):
        mock_llm = make_structured_llm(
            mocker,
            decision="revise",
            final_answer=None,
            feedback="The answer still omits the source types.",
        )
        mocker.patch("app.agents.reviewer.get_llm", return_value=mock_llm)
        state = make_state(revision_count=1, draft_answer="")

        result = reviewer_node(state)

        assert result.review_outcome == "budget_exhausted"
        assert result.final_answer.startswith(
            "The revised answer could not be fully approved."
        )
        assert "revised once" in result.final_answer

    def test_budget_exhaustion_does_not_duplicate_an_existing_limitation(self, mocker):
        limitation = (
            "the revised answer\n\nNote: this answer was revised once, but the "
            "reviewer still identified a material deficiency within the "
            "available evidence. Treat it as provisional."
        )
        mock_llm = make_structured_llm(
            mocker,
            decision="revise",
            final_answer=limitation,
            feedback="Still incomplete.",
        )
        mocker.patch("app.agents.reviewer.get_llm", return_value=mock_llm)
        state = make_state(revision_count=1, draft_answer=limitation)

        result = reviewer_node(state)

        assert result.final_answer == limitation
        assert result.final_answer.count("revised once") == 1

    def test_final_review_approval_marks_the_answer_as_revised(self, mocker):
        mock_llm = make_structured_llm(mocker, decision="approve", final_answer="the revised answer")
        mocker.patch("app.agents.reviewer.get_llm", return_value=mock_llm)
        state = make_state(revision_count=1)

        result = reviewer_node(state)

        assert result.review_decision == "approve"
        assert result.review_outcome == "revised"
        assert result.final_answer == "the revised answer"

    def test_abstains_when_the_reviewer_chooses_abstain(self, mocker):
        mock_llm = make_structured_llm(
            mocker,
            decision="abstain",
            final_answer="I cannot answer reliably.",
            feedback="The evidence is incomplete.",
        )
        mocker.patch("app.agents.reviewer.get_llm", return_value=mock_llm)
        state = make_state(selected_tool="architecture_advisor", retrieved_sources=None)

        result = reviewer_node(state)

        assert result.review_decision == "abstain"
        assert result.review_outcome == "abstained"
        assert result.final_answer == "I couldn't produce a reliable answer to this question."
        assert result.revision_count == 0

    def test_review_prompt_contains_quality_criteria_and_revision_policy(self, mocker):
        mock_llm = make_structured_llm(mocker)
        mocker.patch("app.agents.reviewer.get_llm", return_value=mock_llm)
        state = make_state()

        reviewer_node(state)

        review_prompt = mock_llm.with_structured_output.return_value.invoke.call_args.args[0]
        assert "correctness" in review_prompt.lower()
        assert "evidence support" in review_prompt.lower()
        assert "relevance" in review_prompt.lower()
        assert "completeness" in review_prompt.lower()
        assert "single revision is available" in review_prompt.lower()

    @pytest.mark.parametrize(
        "draft_answer",
        [
            "Tool result:\nThe source discusses a different topic.",
            "Tool result:\nThe policy allows retries, but does not state how many.",
        ],
    )
    def test_abstains_when_sources_do_not_sufficiently_support_the_answer(
        self, mocker, draft_answer
    ):
        mock_llm = make_structured_llm(
            mocker,
            final_answer="The unsupported value is 42.",
            feedback="The sources do not mention this value.",
            evidence_sufficient=False,
        )
        mocker.patch("app.agents.reviewer.get_llm", return_value=mock_llm)
        state = make_state(
            draft_answer=draft_answer,
            retrieved_sources=["unrelated.md"],
        )

        result = reviewer_node(state)

        assert result.final_answer == (
            "The available documentation does not provide enough evidence to answer this question reliably."
        )
        assert result.review_feedback == (
            "The retrieved sources did not sufficiently support an answer; abstained to avoid unsupported claims."
        )
        assert result.review_decision == "abstain"
        assert result.review_outcome == "abstained"
        review_prompt = mock_llm.with_structured_output.return_value.invoke.call_args.args[0]
        assert "source presence alone does not establish evidence sufficiency" in review_prompt
        assert "only partially support" in review_prompt
        assert "reproduce supported names and values verbatim" in review_prompt
        assert "call site is direct evidence of the arguments passed" in review_prompt
        assert "do not require the method declaration or type signature" in review_prompt

    def test_abstains_without_calling_llm_when_doc_retriever_returns_no_sources(self, mocker):
        get_llm = mocker.patch("app.agents.reviewer.get_llm")
        state = make_state(draft_answer="Tool result:\nNo relevant documentation found.", retrieved_sources=[])

        result = reviewer_node(state)

        assert result.final_answer == "I couldn't find relevant documentation to support an answer to this question."
        assert result.review_feedback == "No retrieved sources were available; abstained to avoid an unsupported answer."
        assert result.review_decision == "abstain"
        assert result.review_outcome == "abstained"
        get_llm.assert_not_called()
        assert result.stage_llm_usage["reviewer"] == {"llm_calls": 0, "token_usage": None}

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
