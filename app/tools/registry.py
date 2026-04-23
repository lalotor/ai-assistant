from app.tools.code_explainer import code_explainer
from app.tools.doc_retriever import doc_retriever
from app.tools.architecture_advisor import architecture_advisor

TOOLS = {
    "code_explainer": {
        "function": code_explainer,
        "description": "Use when user provides code snippets that need explanation or analysis"
    },
    "doc_retriever": {
        "function": doc_retriever,
        "description": "Use when user asks about documentation, API references, or needs to look up information"
    },
    "architecture_advisor": {
        "function": architecture_advisor,
        "description": "Use when user asks about software architecture, design patterns, or system design questions"
    },
    "none": {
        "function": None,
        "description": "Use for general questions that don't require any specific tool"
    }
}
