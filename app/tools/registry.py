from app.tools.code_explainer import code_explainer
from app.tools.doc_retriever import doc_retriever
from app.tools.architecture_advisor import architecture_advisor

TOOLS = {
    "code_explainer": code_explainer,
    "doc_retriever": doc_retriever,
    "architecture_advisor": architecture_advisor,
}
