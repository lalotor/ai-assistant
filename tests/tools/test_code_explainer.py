"""Unit tests for the code_explainer() seam in app.tools.code_explainer.

code_explainer(CodeInput) -> CodeOutput is the module's only public
interface. The LLM boundary (app.tools.code_explainer.get_llm) is
mocked so these run without network access or API cost.
"""
import pytest

from app.contracts.tools import CodeInput
from app.tools.code_explainer import code_explainer


@pytest.mark.unit
class TestCodeExplainer:
    def test_returns_the_llm_response_content_as_explanation(self, mocker):
        fake_llm = mocker.Mock()
        fake_llm.invoke.return_value = mocker.Mock(content="this adds two numbers", usage_metadata=None)
        mocker.patch("app.tools.code_explainer.get_llm", return_value=fake_llm)

        result = code_explainer(CodeInput(code="def add(a, b): return a + b"))

        assert result.explanation == "this adds two numbers"

    def test_returns_token_usage_when_the_provider_gives_usage_metadata(self, mocker):
        fake_llm = mocker.Mock()
        fake_llm.model_name = "gpt-5.4-mini"
        fake_llm.invoke.return_value = mocker.Mock(
            content="explained",
            usage_metadata={"input_tokens": 80, "output_tokens": 30, "total_tokens": 110},
        )
        mocker.patch("app.tools.code_explainer.get_llm", return_value=fake_llm)

        result = code_explainer(CodeInput(code="print(1)"))

        assert result.token_usage == {"input_tokens": 80, "output_tokens": 30, "model": "gpt-5.4-mini"}

    def test_returns_none_token_usage_when_the_provider_gives_none(self, mocker):
        fake_llm = mocker.Mock()
        fake_llm.invoke.return_value = mocker.Mock(content="explained", usage_metadata=None)
        mocker.patch("app.tools.code_explainer.get_llm", return_value=fake_llm)

        result = code_explainer(CodeInput(code="print(1)"))

        assert result.token_usage is None
