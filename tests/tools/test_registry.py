"""Unit tests for app.tools.registry's TOOLS registry and invoke adapters.

Each TOOLS[name]["invoke"](tool_input, user_input) -> dict is the seam
under test. Each tool's underlying function (code_explainer,
doc_retriever, architecture_advisor) is mocked at its own module
boundary, since correctness of the tool itself belongs to that tool's
own tests, not the registry's.
"""
import pytest

from app.contracts.tools import ArchOutput, CodeOutput, DocOutput
from app.contracts.trace import RetrievalTrace
from app.tools.registry import TOOLS


@pytest.mark.unit
class TestToolsRegistryShape:
    def test_every_entry_has_a_description_and_an_invoke_adapter(self):
        for name, entry in TOOLS.items():
            assert "description" in entry, f"{name} is missing a description"
            assert "invoke" in entry, f"{name} is missing an invoke adapter"
            assert callable(entry["invoke"]), f"{name}'s invoke is not callable"


@pytest.mark.unit
class TestCodeExplainerInvoke:
    def test_uses_code_from_tool_input_when_present(self, mocker):
        mock_fn = mocker.patch(
            "app.tools.registry.code_explainer",
            return_value=CodeOutput(explanation="explained"),
        )

        outcome = TOOLS["code_explainer"]["invoke"]({"code": "print(1)"}, "fallback")

        assert outcome == {"result": "explained", "sources": None, "retrieval_trace": None}
        mock_fn.assert_called_once()
        assert mock_fn.call_args[0][0].code == "print(1)"

    def test_falls_back_to_user_input_when_no_code_given(self, mocker):
        mock_fn = mocker.patch(
            "app.tools.registry.code_explainer",
            return_value=CodeOutput(explanation="explained"),
        )

        TOOLS["code_explainer"]["invoke"]({}, "def f(): pass")

        assert mock_fn.call_args[0][0].code == "def f(): pass"


@pytest.mark.unit
class TestDocRetrieverInvoke:
    def test_surfaces_context_sources_and_retrieval_trace(self, mocker):
        trace = RetrievalTrace(query="q")
        mocker.patch(
            "app.tools.registry.doc_retriever",
            return_value=DocOutput(context="the context", sources=["a.md"], retrieval_trace=trace),
        )

        outcome = TOOLS["doc_retriever"]["invoke"]({"query": "what is X?"}, "fallback")

        assert outcome == {"result": "the context", "sources": ["a.md"], "retrieval_trace": trace}


@pytest.mark.unit
class TestArchitectureAdvisorInvoke:
    def test_surfaces_advice_as_result_with_no_sources(self, mocker):
        mocker.patch(
            "app.tools.registry.architecture_advisor",
            return_value=ArchOutput(advice="use microservices"),
        )

        outcome = TOOLS["architecture_advisor"]["invoke"]({"question": "should I?"}, "fallback")

        assert outcome == {"result": "use microservices", "sources": None, "retrieval_trace": None}


@pytest.mark.unit
class TestNoneInvoke:
    def test_passes_user_input_through_as_the_result(self):
        outcome = TOOLS["none"]["invoke"]({}, "what's 2+2?")

        assert outcome == {"result": "what's 2+2?", "sources": None, "retrieval_trace": None}
