"""Unit tests for app.utils.llm's extract_usage() seam.

extract_usage(ai_message, model_name) -> dict | None is the shared helper
every LLM-calling site (planner, reviewer, code_explainer,
architecture_advisor, doc_retriever's reranking step) uses to turn an
AIMessage's usage_metadata into the {"input_tokens", "output_tokens",
"model"} shape stored on StageEvent.token_usage (Week 9: cost/perf
tracing, not correctness data).
"""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import openai
import pytest
from langchain_openai import ChatOpenAI

from app.utils.llm import (
    LLM_MAX_RETRIES,
    LLM_REQUEST_TIMEOUT_SECONDS,
    extract_usage,
    get_llm,
)


def _chat_completion_response(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "created": 1_700_000_000,
            "model": "gpt-4o-mini",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "ok"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "total_tokens": 2,
            },
        },
        request=request,
    )


def _test_chat_model(http_client: httpx.Client, *, max_retries: int = 2, timeout: float = 1) -> ChatOpenAI:
    return ChatOpenAI(
        model="gpt-4o-mini",
        api_key="test-key",
        base_url="https://provider.test/v1",
        http_client=http_client,
        max_retries=max_retries,
        request_timeout=timeout,
    )


@pytest.mark.unit
class TestGetLlmReliabilityConfiguration:
    def test_configures_bounded_retries_and_request_timeout(self, mocker):
        chat_openai = mocker.patch("app.utils.llm.ChatOpenAI")

        result = get_llm()

        chat_openai.assert_called_once_with(
            model="gpt-5.4-mini",
            temperature=0,
            max_retries=LLM_MAX_RETRIES,
            request_timeout=LLM_REQUEST_TIMEOUT_SECONDS,
        )
        assert result is chat_openai.return_value

    def test_preserves_requested_model_and_temperature(self, mocker):
        chat_openai = mocker.patch("app.utils.llm.ChatOpenAI")

        get_llm(model="another-model", temperature=0.4)

        chat_openai.assert_called_once_with(
            model="another-model",
            temperature=0.4,
            max_retries=LLM_MAX_RETRIES,
            request_timeout=LLM_REQUEST_TIMEOUT_SECONDS,
        )


@pytest.mark.unit
class TestOpenAiClientResilience:
    def test_transient_provider_failure_retries_and_then_succeeds(self):
        attempts = 0
        retry_counts = []

        def respond(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            retry_counts.append(request.headers["x-stainless-retry-count"])
            if attempts == 1:
                return httpx.Response(
                    503,
                    headers={"retry-after-ms": "1"},
                    json={"error": {"message": "temporarily unavailable", "type": "server_error"}},
                    request=request,
                )
            return _chat_completion_response(request)

        client = httpx.Client(transport=httpx.MockTransport(respond))
        try:
            result = _test_chat_model(client).invoke("hello")
        finally:
            client.close()

        assert result.content == "ok"
        assert attempts == 2
        assert retry_counts == ["0", "1"]

    def test_transient_provider_failure_stops_after_configured_attempt_limit(self):
        attempts = 0
        retry_counts = []

        def respond(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            retry_counts.append(request.headers["x-stainless-retry-count"])
            return httpx.Response(
                503,
                headers={"retry-after-ms": "1"},
                json={"error": {"message": "temporarily unavailable", "type": "server_error"}},
                request=request,
            )

        client = httpx.Client(transport=httpx.MockTransport(respond))
        try:
            with pytest.raises(openai.InternalServerError):
                _test_chat_model(client).invoke("hello")
        finally:
            client.close()

        assert attempts == LLM_MAX_RETRIES + 1
        assert retry_counts == ["0", "1", "2"]

    def test_permanent_provider_error_is_not_retried(self):
        attempts = 0

        def respond(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            return httpx.Response(
                400,
                json={
                    "error": {
                        "message": "invalid request",
                        "type": "invalid_request_error",
                        "param": None,
                        "code": "invalid_request",
                    }
                },
                request=request,
            )

        client = httpx.Client(transport=httpx.MockTransport(respond))
        try:
            with pytest.raises(openai.BadRequestError):
                _test_chat_model(client).invoke("hello")
        finally:
            client.close()

        assert attempts == 1

    def test_provider_timeout_terminates_the_actual_request(self):
        request_count = 0

        class SlowProviderHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                nonlocal request_count
                request_count += 1
                time.sleep(0.2)
                body = json.dumps(
                    {
                        "id": "chatcmpl-test",
                        "object": "chat.completion",
                        "created": 1_700_000_000,
                        "model": "gpt-4o-mini",
                        "choices": [
                            {
                                "index": 0,
                                "message": {"role": "assistant", "content": "too late"},
                                "finish_reason": "stop",
                            }
                        ],
                        "usage": {
                            "prompt_tokens": 1,
                            "completion_tokens": 1,
                            "total_tokens": 2,
                        },
                    }
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                try:
                    self.wfile.write(body)
                except BrokenPipeError:
                    pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), SlowProviderHandler)
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        client = httpx.Client()
        try:
            model = ChatOpenAI(
                model="gpt-4o-mini",
                api_key="test-key",
                base_url=f"http://127.0.0.1:{server.server_port}/v1",
                http_client=client,
                max_retries=0,
                request_timeout=0.05,
            )
            with pytest.raises(openai.APITimeoutError):
                model.invoke("hello")
        finally:
            client.close()
            server.shutdown()
            server.server_close()
            server_thread.join(timeout=1)

        assert request_count == 1


class FakeAIMessage:
    def __init__(self, usage_metadata=None):
        self.usage_metadata = usage_metadata


@pytest.mark.unit
class TestExtractUsage:
    def test_extracts_input_and_output_tokens_with_model_name(self):
        message = FakeAIMessage(usage_metadata={"input_tokens": 120, "output_tokens": 30, "total_tokens": 150})

        usage = extract_usage(message, model_name="gpt-5.4-mini")

        assert usage == {"input_tokens": 120, "output_tokens": 30, "model": "gpt-5.4-mini"}

    def test_returns_none_when_usage_metadata_is_absent(self):
        """None (not zeros) is the honest signal that the provider returned
        no usage data at all - a token report must be able to tell that
        apart from "this call genuinely used zero tokens"."""
        message = FakeAIMessage(usage_metadata=None)

        assert extract_usage(message, model_name="gpt-5.4-mini") is None

    def test_returns_none_when_the_message_has_no_usage_metadata_attribute(self):
        """Defensive: some message-like objects (e.g. a bare Mock without
        the attribute configured) won't even have the attribute."""
        class BareObject:
            pass

        assert extract_usage(BareObject(), model_name="gpt-5.4-mini") is None

    def test_defaults_missing_token_fields_to_zero(self):
        message = FakeAIMessage(usage_metadata={})

        usage = extract_usage(message, model_name="gpt-5.4-mini")

        assert usage == {"input_tokens": 0, "output_tokens": 0, "model": "gpt-5.4-mini"}
