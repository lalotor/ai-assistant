from app.tools.code_explainer import code_explainer, CodeInput
from app.tools.doc_retriever import doc_retriever, DocInput
from app.tools.architecture_advisor import architecture_advisor, ArchInput


def _invoke_code_explainer(tool_input: dict, user_input: str) -> dict:
    code = tool_input.get("code") or user_input
    result = code_explainer(CodeInput(code=code))
    return {"result": result.explanation, "sources": None, "retrieval_trace": None}


def _invoke_doc_retriever(tool_input: dict, user_input: str) -> dict:
    query = tool_input.get("query") or user_input
    result = doc_retriever(DocInput(query=query))
    return {"result": result.context, "sources": result.sources, "retrieval_trace": result.retrieval_trace}


def _invoke_architecture_advisor(tool_input: dict, user_input: str) -> dict:
    question = tool_input.get("question") or user_input
    result = architecture_advisor(ArchInput(question=question))
    return {"result": result.advice, "sources": None, "retrieval_trace": None}


def _invoke_none(tool_input: dict, user_input: str) -> dict:
    """No tool needed: pass the user's input straight through as the result."""
    return {"result": user_input, "sources": None, "retrieval_trace": None}


TOOLS = {
    "code_explainer": {
        "description": "Use when user provides code snippets that need explanation or analysis",
        "invoke": _invoke_code_explainer,
    },
    "doc_retriever": {
        "description": "Use when user asks about documentation, API references, or needs to look up information for internal technical docs",
        "invoke": _invoke_doc_retriever,
    },
    "architecture_advisor": {
        "description": "Use when user asks about software architecture, design patterns, or system design questions",
        "invoke": _invoke_architecture_advisor,
    },
    "none": {
        "description": "Use for general questions that don't require any specific tool",
        "invoke": _invoke_none,
    },
}
