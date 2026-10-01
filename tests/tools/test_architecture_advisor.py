"""Unit tests for the architecture_advisor() seam in
app.tools.architecture_advisor.

architecture_advisor(ArchInput) -> ArchOutput is the module's only
public interface. The LLM boundary
(app.tools.architecture_advisor.get_llm) is mocked so these run without
network access or API cost.
"""
import pytest

from app.contracts.tools import ArchInput
from app.tools.architecture_advisor import architecture_advisor


@pytest.mark.unit
class TestArchitectureAdvisor:
    def test_returns_the_llm_response_content_as_advice(self, mocker):
        fake_llm = mocker.Mock()
        fake_llm.invoke.return_value = mocker.Mock(content="use microservices", usage_metadata=None)
        mocker.patch("app.tools.architecture_advisor.get_llm", return_value=fake_llm)

        result = architecture_advisor(ArchInput(question="should I use microservices?"))

        assert result.advice == "use microservices"

    def test_returns_token_usage_when_the_provider_gives_usage_metadata(self, mocker):
        fake_llm = mocker.Mock()
        fake_llm.model_name = "gpt-5.4-mini"
        fake_llm.invoke.return_value = mocker.Mock(
            content="advice",
            usage_metadata={"input_tokens": 90, "output_tokens": 25, "total_tokens": 115},
        )
        mocker.patch("app.tools.architecture_advisor.get_llm", return_value=fake_llm)

        result = architecture_advisor(ArchInput(question="a question"))

        assert result.token_usage == {"input_tokens": 90, "output_tokens": 25, "model": "gpt-5.4-mini"}

    def test_returns_none_token_usage_when_the_provider_gives_none(self, mocker):
        fake_llm = mocker.Mock()
        fake_llm.invoke.return_value = mocker.Mock(content="advice", usage_metadata=None)
        mocker.patch("app.tools.architecture_advisor.get_llm", return_value=fake_llm)

        result = architecture_advisor(ArchInput(question="a question"))

        assert result.token_usage is None
