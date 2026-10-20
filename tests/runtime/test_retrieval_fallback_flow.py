"""End-to-end retrieval fallback coverage through AssistantRuntime."""
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.documents import Document

from app.agents.graph import get_graph
from app.contracts.agent import ReviewResult
from app.contracts.response import QueryResponse
from app.contracts.retrieval import LoadedDocument
from app.contracts.tools import ToolDecision
from app.api.routes.ask import router as ask_router
from app.rag.chunking import chunk_document
from app.runtime.assistant_runtime import AssistantRuntime


def _structured_llm(parsed, *, model_name="gpt-5.4-mini", invoke=None):
    structured = Mock()
    structured.invoke.side_effect = invoke or (lambda _prompt: {
        "raw": Mock(usage_metadata=None),
        "parsed": parsed,
    })
    model = Mock(
        model_name=model_name,
        with_structured_output=Mock(return_value=structured),
    )
    return model, structured


@pytest.mark.unit
class TestRetrievalFallbackFlow:
    def test_keyword_fallback_reaches_final_answer_with_degraded_trace(self, mocker):
        decision = ToolDecision(
            tool="doc_retriever",
            reason="Look up the inputs to DiffService in the internal documentation.",
            tool_input={"query": "DiffService inputs internal documentation"},
        )
        planner_llm, _ = _structured_llm(decision)
        mocker.patch("app.agents.planner.get_llm", return_value=planner_llm)

        reviewed = ReviewResult(
            final_answer=(
                "DiffService.computeDiff takes jobId, systemAData, systemBData, "
                "and algorithm."
            ),
            feedback="The answer is supported by the retrieved API implementation.",
            evidence_sufficient=True,
        )
        reviewer_prompts = []

        def review_prompt(prompt):
            reviewer_prompts.append(prompt)
            return {"raw": Mock(usage_metadata=None), "parsed": reviewed}

        reviewer_llm, reviewer_structured = _structured_llm(reviewed, invoke=review_prompt)
        mocker.patch("app.agents.reviewer.get_llm", return_value=reviewer_llm)

        source_path = (
            "data/docs/java-service/src/main/java/com/example/controller/"
            "ProcessController.java"
        )
        source_document = LoadedDocument(
            content=Path(source_path).read_text(encoding="utf-8"),
            source=source_path,
            type=".java",
        )
        keyword_chunks = [
            Document(
                page_content=(
                    f"Reference {index}: Internal documentation gives a general "
                    "service overview."
                ),
                metadata={"source": f"data/docs/README-{index}.md", "file_type": ".md"},
            )
            for index in range(4)
        ] + chunk_document(source_document)
        assert any(
            "diffService.computeDiff" in chunk.page_content
            for chunk in keyword_chunks
        )
        mocker.patch(
            "app.tools.doc_retriever.get_vector_store",
            side_effect=RuntimeError("vector index unavailable"),
        )
        mocker.patch(
            "app.tools.doc_retriever.get_cached_chunks",
            return_value=keyword_chunks,
        )
        reranker_llm = Mock(
            model_name="gpt-5.4-mini",
            invoke=Mock(return_value=Mock(content="0,1,2,3", usage_metadata=None)),
        )
        mocker.patch("app.tools.doc_retriever.get_llm", return_value=reranker_llm)
        runtime = AssistantRuntime()
        runtime.graph = get_graph()
        mocker.patch.object(runtime, "setup", return_value=True)

        response = runtime.run_question(
            "Considering only your internal documentation, what inputs does "
            "DiffService take?",
            trace_id="fallback-flow",
        )

        assert isinstance(response, QueryResponse)
        assert response.final_answer == (
            "DiffService.computeDiff takes jobId, systemAData, systemBData, "
            "and algorithm."
        )
        assert response.retrieved_sources == [
            "data/docs/java-service/src/main/java/com/example/controller/ProcessController.java"
        ]
        assert len(reviewer_prompts) == 1
        assert "diffService.computeDiff(" in reviewer_prompts[0]
        assert "request.getSystemAData()" in reviewer_prompts[0]
        assert "request.getSystemBData()" in reviewer_prompts[0]
        assert "request.getAlgorithm()" in reviewer_prompts[0]
        assert "ProcessController.java" in reviewer_prompts[0]
        assert "vector retrieval failed" in reviewer_prompts[0].lower()
        assert response.execution_trace.outcome == "degraded"
        assert response.execution_trace.retrieval_trace.vector_search_status == "failed"
        assert response.execution_trace.retrieval_trace.keyword_search_status == "succeeded"
        assert response.execution_trace.retrieval_trace.fallback_used is True
        reviewer_structured.invoke.assert_called_once_with(reviewer_prompts[0])

    def test_reviewer_failure_returns_generic_api_error_and_logs_safe_failed_trace(self, mocker):
        decision = ToolDecision(
            tool="none",
            reason="No specialized tool is needed.",
            tool_input={},
        )
        planner_llm, _ = _structured_llm(decision)
        mocker.patch("app.agents.planner.get_llm", return_value=planner_llm)

        reviewer_structured = Mock()
        reviewer_structured.invoke.side_effect = TimeoutError("PRIVATE_PROVIDER_DETAIL")
        reviewer_llm = Mock(
            model_name="gpt-5.4-mini",
            with_structured_output=Mock(return_value=reviewer_structured),
        )
        mocker.patch("app.agents.reviewer.get_llm", return_value=reviewer_llm)
        runtime = AssistantRuntime()
        runtime.graph = get_graph()
        mocker.patch.object(runtime, "setup", return_value=True)
        api = FastAPI()
        api.state.runtime = runtime
        api.include_router(ask_router)
        error_log = mocker.patch("app.runtime.assistant_runtime.logger.error")

        response = TestClient(api).post(
            "/ask",
            json={"question": "PRIVATE QUESTION", "trace_id": "reviewer-failure"},
        )

        assert response.status_code == 500
        assert response.json()["detail"] == "The agent encountered an error processing your question."
        event = error_log.call_args.kwargs
        assert event["outcome"] == "failed"
        assert event["failure_category"] == "operation_timeout"
        assert event["execution_trace"]["failed_stage"] == "reviewer"
        assert event["execution_trace"]["failure_type"] == "TimeoutError"
        assert event["execution_trace"]["reviewer_events"][0]["started_at"] is not None
        assert event["execution_trace"]["reviewer_events"][0]["ended_at"] is not None
        assert event["execution_trace"]["planner_events"][0]["duration_ms"] is not None
        assert event["execution_trace"]["worker_events"][0]["duration_ms"] is not None
        assert event["execution_trace"]["reviewer_events"][0]["input_snapshot"] == {}
        assert event["execution_trace"]["reviewer_events"][0]["output_snapshot"] == {}
        serialized_trace = str(event["execution_trace"])
        assert "PRIVATE QUESTION" not in serialized_trace
        assert "PRIVATE_PROVIDER_DETAIL" not in serialized_trace
        assert event["execution_trace"]["outcome"] == "failed"
