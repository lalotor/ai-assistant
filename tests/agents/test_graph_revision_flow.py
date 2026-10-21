"""Graph-level tests for the bounded review/revision workflow.

The graph is exercised through its public ``get_graph()`` seam. The LLM
boundaries inside the real planner/reviewer/revision nodes are mocked, so
these tests verify routing, the revision budget, and trace-visible state
without network access or API cost.
"""
from unittest.mock import Mock

import pytest

from app.agents.graph import get_graph, route_after_review
from app.contracts.agent import AgentState, ReviewResult
from app.contracts.errors import WorkflowStageError
from app.contracts.tools import ToolDecision


def make_state(**overrides) -> AgentState:
    defaults = dict(
        user_input="what are the source types?",
        selected_tool="doc_retriever",
        revision_enabled=True,
        trace_id="graph-trace",
    )
    defaults.update(overrides)
    return AgentState(**defaults)


def patch_planner(mocker, tool="doc_retriever", tool_input=None):
    decision = ToolDecision(
        tool=tool,
        reason="Look this up in the internal documentation.",
        tool_input=tool_input or {"query": "source types"},
    )
    structured = Mock()
    structured.invoke.return_value = {"raw": Mock(usage_metadata=None), "parsed": decision}
    llm = Mock(
        model_name="gpt-5.4-mini",
        with_structured_output=Mock(return_value=structured),
    )
    mocker.patch("app.agents.planner.get_llm", return_value=llm)
    return llm


def patch_worker(mocker):
    fake_tool = {
        "description": "Fake internal documentation tool.",
        "invoke": Mock(return_value={
            "result": "the tool evidence",
            "sources": ["source.md"],
            "retrieval_trace": None,
            "llm_calls": 1,
            "token_usage": {"input_tokens": 10, "output_tokens": 2, "model": "gpt-5.4-mini"},
        }),
    }
    mocker.patch.dict("app.agents.worker.TOOLS", {"doc_retriever": fake_tool}, clear=True)
    return fake_tool["invoke"]


def patch_reviewer(mocker, *responses):
    prompts = []

    def invoke(prompt):
        prompts.append(prompt)
        parsed = responses[len(prompts) - 1]
        return {"raw": Mock(usage_metadata=None), "parsed": parsed}

    structured = Mock()
    structured.invoke.side_effect = invoke
    llm = Mock(
        model_name="gpt-5.4-mini",
        with_structured_output=Mock(return_value=structured),
    )
    mocker.patch("app.agents.reviewer.get_llm", return_value=llm)
    return prompts, structured


def patch_revision(mocker, content="the revised answer", side_effect=None):
    response = Mock(content=content, usage_metadata=None)
    llm = Mock(model_name="gpt-5.4-mini")
    if side_effect is not None:
        llm.invoke.side_effect = side_effect
    else:
        llm.invoke.return_value = response
    mocker.patch("app.agents.revision.get_llm", return_value=llm)
    return llm


def revise_then(decision, feedback="Add the missing source types explicitly."):
    return ReviewResult(
        decision="revise",
        final_answer="Tool result:\nthe tool evidence",
        feedback=feedback,
        evidence_sufficient=True,
    )


@pytest.mark.unit
class TestRouteAfterReview:
    def test_routes_to_revision_only_when_every_budget_condition_holds(self):
        state = make_state(
            review_decision="revise",
            revision_feedback="Name the missing source types.",
            revision_count=0,
            revision_enabled=True,
        )

        assert route_after_review(state) == "revision"

    @pytest.mark.parametrize(
        "overrides",
        [
            {"revision_enabled": False},
            {"review_decision": "approve"},
            {"review_decision": "abstain"},
            {"revision_count": 1},
            {"revision_feedback": "   "},
            {"revision_feedback": None},
            {"selected_tool": "none"},
            {"selected_tool": None},
        ],
    )
    def test_returns_end_when_revision_is_not_allowed(self, overrides):
        state = make_state(
            review_decision="revise",
            revision_feedback="Name the missing source types.",
            revision_count=0,
            revision_enabled=True,
        )
        for key, value in overrides.items():
            setattr(state, key, value)

        assert route_after_review(state) == "end"


@pytest.mark.integration
class TestRevisionGraphFlow:
    def test_full_graph_revises_then_approves(self, mocker):
        patch_planner(mocker)
        patch_worker(mocker)
        prompts, _ = patch_reviewer(
            mocker,
            revise_then("revise"),
            ReviewResult(
                decision="approve",
                final_answer="the revised answer",
                feedback="The revised answer is grounded in the evidence.",
                evidence_sufficient=True,
            ),
        )
        revision_llm = patch_revision(mocker, content="the revised answer")

        result = get_graph().invoke(make_state())

        assert result["final_answer"] == "the revised answer"
        assert result["review_decision"] == "approve"
        assert result["review_outcome"] == "revised"
        assert result["revision_count"] == 1
        assert result["initial_review_decision"] == "revise"
        assert result["stage_timings"]["reviewer"]["started_at"] is not None
        assert result["stage_timings"]["revision"]["started_at"] is not None
        assert result["stage_timings"]["reviewer_final"]["started_at"] is not None

        assert len(prompts) == 2
        assert "A single revision is available" in prompts[0]
        assert "No revision attempt is available" in prompts[1]
        assert "Add the missing source types explicitly." in revision_llm.invoke.call_args.args[0]
        assert "the tool evidence" in revision_llm.invoke.call_args.args[0]
        assert "source.md" in revision_llm.invoke.call_args.args[0]

    def test_budget_is_enforced_after_one_revision(self, mocker):
        patch_planner(mocker)
        patch_worker(mocker)
        prompts, _ = patch_reviewer(
            mocker,
            revise_then("revise"),
            ReviewResult(
                decision="revise",
                final_answer="the revised answer",
                feedback="It still omits an important detail.",
                evidence_sufficient=True,
            ),
        )
        revision_llm = patch_revision(mocker, content="the revised answer")

        result = get_graph().invoke(make_state())

        assert result["review_outcome"] == "budget_exhausted"
        assert result["review_decision"] == "revise"
        assert result["revision_count"] == 1
        assert result["final_answer"].startswith("the revised answer")
        assert "revised once" in result["final_answer"]
        assert len(prompts) == 2
        revision_llm.invoke.assert_called_once()

    def test_abstention_does_not_start_a_revision(self, mocker):
        patch_planner(mocker)
        patch_worker(mocker)
        prompts, _ = patch_reviewer(
            mocker,
            ReviewResult(
                decision="abstain",
                final_answer="I cannot answer reliably.",
                feedback="The retrieved evidence is incomplete.",
                evidence_sufficient=False,
            ),
        )
        revision_llm = patch_revision(mocker)

        result = get_graph().invoke(make_state())

        assert result["review_outcome"] == "abstained"
        assert result["revision_count"] == 0
        assert result["final_answer"] == (
            "The available documentation does not provide enough evidence to "
            "answer this question reliably."
        )
        assert len(prompts) == 1
        revision_llm.invoke.assert_not_called()

    def test_single_pass_revision_request_is_finalized_without_revision(self, mocker):
        patch_planner(mocker)
        patch_worker(mocker)
        prompts, _ = patch_reviewer(
            mocker,
            ReviewResult(
                decision="revise",
                final_answer="the reviewer's improved answer",
                feedback="A dedicated revision would help here.",
                evidence_sufficient=True,
            ),
        )
        revision_llm = patch_revision(mocker)

        result = get_graph().invoke(make_state(revision_enabled=False))

        assert result["review_outcome"] == "revision_skipped"
        assert result["revision_count"] == 0
        assert result["final_answer"] == "the reviewer's improved answer"
        assert len(prompts) == 1
        assert "No revision attempt is available" in prompts[0]
        revision_llm.invoke.assert_not_called()

    def test_malformed_reviewer_output_fails_without_a_final_answer(self, mocker):
        patch_planner(mocker)
        patch_worker(mocker)
        structured = Mock()
        structured.invoke.side_effect = ValueError("malformed structured output")
        reviewer_llm = Mock(
            model_name="gpt-5.4-mini",
            with_structured_output=Mock(return_value=structured),
        )
        mocker.patch("app.agents.reviewer.get_llm", return_value=reviewer_llm)

        with pytest.raises(WorkflowStageError) as exc_info:
            get_graph().invoke(make_state())

        assert exc_info.value.stage == "reviewer"
        assert exc_info.value.failure_category == "reviewer_failure"
        assert exc_info.value.failure_type == "ValueError"

    def test_final_reviewer_failure_keeps_the_initial_decision_in_safe_metadata(self, mocker):
        patch_planner(mocker)
        patch_worker(mocker)
        structured = Mock()
        structured.invoke.side_effect = [
            {"raw": Mock(usage_metadata=None), "parsed": revise_then("revise")},
            ValueError("malformed final review output"),
        ]
        reviewer_llm = Mock(
            model_name="gpt-5.4-mini",
            with_structured_output=Mock(return_value=structured),
        )
        mocker.patch("app.agents.reviewer.get_llm", return_value=reviewer_llm)
        patch_revision(mocker, content="the revised answer")

        with pytest.raises(WorkflowStageError) as exc_info:
            get_graph().invoke(make_state())

        assert exc_info.value.stage == "reviewer_final"
        assert exc_info.value.failure_category == "reviewer_final_failure"
        assert exc_info.value.review_state["initial_decision"] == "revise"
        assert exc_info.value.review_state["revision_attempted"] is True
        assert exc_info.value.review_state["revision_count"] == 1

    def test_revision_failure_fails_the_graph_without_returning_the_draft(self, mocker):
        patch_planner(mocker)
        patch_worker(mocker)
        patch_reviewer(mocker, revise_then("revise"))
        patch_revision(mocker, side_effect=TimeoutError("provider timed out"))

        with pytest.raises(WorkflowStageError) as exc_info:
            get_graph().invoke(make_state())

        assert exc_info.value.stage == "revision"
        assert exc_info.value.failure_category == "operation_timeout"
        assert exc_info.value.failure_type == "TimeoutError"
        assert "revision" in exc_info.value.stage_timings
        assert exc_info.value.review_state == {
            "initial_decision": "revise",
            "revision_attempted": True,
            "revision_count": 0,
            "final_decision": None,
            "final_feedback": None,
            "outcome": None,
        }
