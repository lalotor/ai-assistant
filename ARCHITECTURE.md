# AI Assistant - System Architecture Documentation

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Principles](#architecture-principles)
3. [High-Level Architecture](#high-level-architecture)
4. [Component Architecture](#component-architecture)
5. [Data Flow](#data-flow)
6. [Technology Stack](#technology-stack)
7. [Module Details](#module-details)
8. [Configuration Management](#configuration-management)
9. [Logging and Observability](#logging-and-observability)
10. [RAG Pipeline](#rag-pipeline)
11. [Deployment Considerations](#deployment-considerations)
12. [Future Enhancements](#future-enhancements)

---

## System Overview

### Purpose

The AI Assistant is a **multi-agent conversational system** built using LangGraph that intelligently routes user questions to specialized tools. It leverages Retrieval-Augmented Generation (RAG) to provide context-aware responses from technical documentation.

### Key Capabilities

- **Multi-Agent Orchestration**: Planner → Worker → Reviewer workflow
- **Tool-Based Routing**: Intelligent selection between code explanation, documentation retrieval, and architecture advice
- **RAG-Powered Knowledge Base**: Vector store-based document retrieval with FAISS
- **Structured Logging**: Production-ready observability with correlation tracking
- **Environment Validation**: Startup validation ensures all required configuration is present

### System Characteristics

- **Language**: Python 3.13.5
- **Framework**: LangGraph (LangChain ecosystem)
- **LLM Provider**: OpenAI (GPT-5-nano)
- **Vector Store**: FAISS (Facebook AI Similarity Search)
- **Logging**: Structlog with JSON/console output modes
- **Package Manager**: uv (modern Python package manager)

---

## Architecture Principles

### 1. **Separation of Concerns**
- Agents handle workflow orchestration
- Tools encapsulate domain-specific logic
- RAG components manage knowledge retrieval
- Configuration modules handle environment and logging

### 2. **Modularity**
- Each component is independently testable
- Clear interfaces between modules (Pydantic models)
- Tool registry pattern for extensibility

### 3. **Observability First**
- Structured logging throughout the system
- Correlation IDs for request tracing
- Configurable log levels and formats

### 4. **Configuration as Code**
- Environment variable validation on startup
- Centralized configuration management
- Fail-fast approach for missing required config

### 5. **Persistence and Caching**
- Vector store persistence to disk
- Singleton pattern for vector store instance
- Lazy initialization with rebuild capability

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Interface                          │
│                      (CLI - main.py)                            │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LangGraph Workflow                           │
│  ┌──────────┐      ┌──────────┐      ┌──────────┐              │
│  │ Planner  │─────▶│  Worker  │─────▶│ Reviewer │              │
│  │  Agent   │      │  Agent   │      │  Agent   │              │
│  └──────────┘      └──────────┘      └──────────┘              │
│       │                  │                  │                   │
│       │                  ▼                  │                   │
│       │         ┌─────────────────┐         │                   │
│       │         │  Tool Registry  │         │                   │
│       │         └─────────────────┘         │                   │
│       │                  │                  │                   │
│       │         ┌────────┴────────┐         │                   │
│       │         ▼        ▼        ▼         │                   │
│       │    ┌────────┐ ┌────┐ ┌────────┐    │                   │
│       │    │  Code  │ │Doc │ │  Arch  │    │                   │
│       │    │Explain │ │Retr│ │Advisor │    │                   │
│       │    └────────┘ └──┬─┘ └────────┘    │                   │
│       │                  │                  │                   │
└───────┼──────────────────┼──────────────────┼───────────────────┘
        │                  │                  │
        ▼                  ▼                  ▼
┌─────────────┐   ┌──────────────────┐   ┌──────────┐
│     LLM     │   │   RAG Pipeline   │   │   LLM    │
│  (OpenAI)   │   │                  │   │(OpenAI)  │
└─────────────┘   │  ┌────────────┐  │   └──────────┘
                  │  │ Ingestion  │  │
                  │  └──────┬─────┘  │
                  │         ▼        │
                  │  ┌────────────┐  │
                  │  │  Chunking  │  │
                  │  └──────┬─────┘  │
                  │         ▼        │
                  │  ┌────────────┐  │
                  │  │ Embeddings │  │
                  │  └──────┬─────┘  │
                  │         ▼        │
                  │  ┌────────────┐  │
                  │  │Vector Store│  │
                  │  │   (FAISS)  │  │
                  │  └──────┬─────┘  │
                  │         ▼        │
                  │  ┌────────────┐  │
                  │  │ Retriever  │  │
                  │  └────────────┘  │
                  └──────────────────┘
```

---

## Component Architecture

### 1. **Entry Point** (`main.py`)

**Responsibilities:**
- Load environment variables (`.env`)
- Validate environment configuration
- Configure structured logging
- Initialize vector store
- Create agent state and invoke LangGraph workflow
- Generate graph visualization

**Key Functions:**
- `main()`: Orchestrates the entire workflow
- `save_graph_image()`: Generates Mermaid PNG visualization

**Initialization Sequence:**
```python
1. load_dotenv()                    # Load .env file
2. validate_environment()            # Validate required env vars
3. configure_logging()               # Setup structlog
4. initialize_vector_store()         # Load/build FAISS index
5. get_graph()                       # Compile LangGraph workflow
6. graph.invoke(initial_state)       # Execute workflow
```

---

### 2. **Agent System** (`app/agents/`)

#### **State Management** (`state.py`)

```python
class AgentState(BaseModel):
    user_input: str                    # Original user question
    plan: Optional[str]                # Planner's reasoning
    selected_tool: Optional[str]       # Tool to execute
    tool_input: Optional[Dict]         # Tool parameters
    tool_output: Optional[str]         # Tool execution result
    draft_answer: Optional[str]        # Worker's draft response
    final_answer: Optional[str]        # Reviewer's final answer
    review_feedback: Optional[str]     # Reviewer's feedback
```

**State Flow:**
```
user_input → plan → selected_tool → tool_output → draft_answer → final_answer
```

#### **Graph Orchestration** (`graph.py`)

**Workflow Definition:**
```
START → planner → worker → reviewer → END
```

**Graph Compilation:**
- Uses `StateGraph` from LangGraph
- Linear workflow (no conditional routing)
- No checkpointer (stateless execution)

#### **Planner Agent** (`planner.py`)

**Purpose**: Analyzes user input and selects the appropriate tool

**Process:**
1. Receives user question
2. Constructs tool selection prompt with available tools
3. Uses LLM with structured output (`ToolDecision` model)
4. Returns tool selection with reasoning

**Tool Selection Logic:**
- **code_explainer**: User provides code snippets
- **doc_retriever**: User asks about documentation/APIs
- **architecture_advisor**: User asks about design/architecture
- **none**: General questions not requiring tools

**Output Model:**
```python
class ToolDecision(BaseModel):
    tool: Literal["code_explainer", "doc_retriever", "architecture_advisor", "none"]
    reason: str
    tool_input: Dict[str, Any]
```

#### **Worker Agent** (`worker.py`)

**Purpose**: Executes the selected tool and generates draft answer

**Process:**
1. Receives tool selection from planner
2. Routes to appropriate tool function
3. Handles tool execution errors
4. Stores tool output in state

**Tool Routing:**
```python
if selected_tool == "code_explainer":
    result = code_explainer(CodeInput(code=...))
if selected_tool == "doc_retriever":
    result = doc_retriever(DocInput(query=...))
if selected_tool == "architecture_advisor":
    result = architecture_advisor(ArchInput(question=...))
```

#### **Reviewer Agent** (`reviewer.py`)

**Purpose**: Reviews draft answer and produces final response

**Process:**
1. Receives draft answer from worker
2. Evaluates quality and completeness
3. Improves answer if needed
4. Provides feedback

**Output Model:**
```python
class ReviewResult(BaseModel):
    final_answer: str
    feedback: str
```

---

### 3. **Tool System** (`app/tools/`)

#### **Tool Registry** (`registry.py`)

**Pattern**: Centralized tool registration

```python
TOOLS = {
    "code_explainer": {
        "function": code_explainer,
        "description": "Use when user provides code snippets..."
    },
    "doc_retriever": {...},
    "architecture_advisor": {...},
    "none": {...}
}
```

**Benefits:**
- Single source of truth for available tools
- Easy to add new tools
- Descriptions used in planner prompts

#### **Code Explainer** (`code_explainer.py`)

**Input**: `CodeInput(code: str)`
**Output**: `CodeOutput(explanation: str)`

**Functionality:**
- Accepts code snippet
- Uses LLM to generate detailed explanation
- Returns markdown-formatted response

#### **Documentation Retriever** (`doc_retriever.py`)

**Input**: `DocInput(query: str)`
**Output**: `DocOutput(context: str)`

**Functionality:**
- Queries vector store for relevant documents
- Retrieves top-k (k=10) similar chunks
- Filters by similarity threshold
- Consolidates context from multiple sources

**Integration:**
```python
vector_store = get_vector_store()  # Singleton instance
results = retrieve_context(vector_store, query, k=10)
```

#### **Architecture Advisor** (`architecture_advisor.py`)

**Input**: `ArchInput(question: str)`
**Output**: `ArchOutput(advice: str)`

**Functionality:**
- Accepts architecture/design question
- Uses LLM with senior architect persona
- Returns markdown-formatted advice

---

### 4. **RAG Pipeline** (`app/rag/`)

#### **Document Ingestion** (`ingestion.py`)

**Purpose**: Load documents from filesystem

**Process:**
1. Recursively scan `data/docs/` directory
2. Read file content (UTF-8 encoding)
3. Create `LoadedDocument` objects with metadata

**Model:**
```python
class LoadedDocument(BaseModel):
    content: str      # File content
    source: str       # File path
    type: str         # File extension
```

#### **Document Chunking** (`chunking.py`)

**Purpose**: Split documents into semantic chunks

**Strategies by File Type:**

| File Type | Strategy | Configuration |
|-----------|----------|---------------|
| `.md` | MarkdownHeaderTextSplitter | Split on #, ##, ### headers |
| `.py` | RecursiveCharacterTextSplitter | Python-specific separators, 600 chars, 90 overlap |
| `.js` | RecursiveCharacterTextSplitter | JS-specific separators, 600 chars, 90 overlap |
| `.java` | RecursiveCharacterTextSplitter | Java-specific separators, 600 chars, 90 overlap |
| `.tf` | RecursiveCharacterTextSplitter | Terraform blocks (resource, module, variable) |
| `.json`/`.yaml` | RecursiveJsonSplitter | Structure-aware, 500 chars max |
| Others | RecursiveCharacterTextSplitter | Generic, 1000 chars, 100 overlap |

**Metadata Enrichment:**
```python
chunk.metadata.update({
    "source": doc.source,
    "file_type": doc.type,
    "chunk_len": len(chunk.page_content)
})
```

#### **Embeddings** (`embeddings.py`)

**Purpose**: Generate vector embeddings for chunks

**Provider Configuration:**
```python
EMBEDDING_PROVIDER=openai  # Environment variable
model="text-embedding-3-small"  # OpenAI model
```

**Factory Pattern:**
```python
def get_embeddings():
    provider = os.getenv("EMBEDDING_PROVIDER", "openai")
    if provider == "openai":
        return OpenAIEmbeddings(model="text-embedding-3-small")
```

#### **Vector Store** (`vector_store.py`)

**Purpose**: Persistent FAISS vector database

**Singleton Pattern:**
```python
_vector_store: Optional[FAISS] = None

def get_vector_store() -> FAISS:
    global _vector_store
    if _vector_store is None:
        _vector_store = initialize_vector_store()
    return _vector_store
```

**Initialization Logic:**
1. Check if persisted store exists at `VECTOR_STORE_PATH`
2. If exists: Load from disk using `FAISS.load_local()`
3. If not exists or force_rebuild: Build from scratch
4. Persist to disk using `save_local()`

**Key Functions:**
- `initialize_vector_store()`: Load or build vector store
- `build_vector_store_from_documents()`: Create new FAISS index
- `save_vector_store()`: Persist to disk
- `add_documents_to_vector_store()`: Incremental updates
- `rebuild_vector_store()`: Force rebuild

**Build Process:**
```python
1. load_documents()           # Load all docs from data/docs/
2. chunk_document(doc)        # Chunk each document
3. FAISS.from_documents()     # Build vector index
4. save_local()               # Persist to disk
```

#### **Retriever** (`retriever.py`)

**Purpose**: Query vector store for relevant documents

**Similarity Search:**
```python
def retrieve_context(vector_store, query, k=7, score_threshold=1.2):
    docs_with_scores = vector_store.similarity_search_with_score(query, k=k)
    # Filter by L2 distance threshold
    filtered_docs = [d for d, score in docs_with_scores if score < threshold]
```

**Scoring:**
- Uses L2 distance (lower is better)
- Default threshold: 1.2 (configurable via `SIMILARITY_THRESHOLD`)
- Returns top-k documents below threshold

**Output Format:**
```python
[
    {
        "content": "...",
        "source": "data/docs/architecture/data-model.md",
        "file_type": ".md",
        "similarity_score": 0.85
    },
    ...
]
```

---

### 5. **Configuration Management** (`app/config/`)

#### **Environment Validator** (`env_validator.py`)

**Purpose**: Validate environment variables on startup

**Validation Rules:**

| Variable | Required | Default | Validation |
|----------|----------|---------|------------|
| `OPENAI_API_KEY` | ✅ Yes | - | Must start with `sk-`, length > 20 |
| `LOG_LEVEL` | ❌ No | `INFO` | Must be DEBUG/INFO/WARNING/ERROR/CRITICAL |
| `JSON_LOGS` | ❌ No | `false` | Must be true/false |
| `LOG_FILE_PATH` | ❌ No | `logs/app.log` | - |
| `ENABLE_FILE_LOGGING` | ❌ No | `false` | Must be true/false |
| `EMBEDDING_PROVIDER` | ❌ No | `openai` | Must be openai |
| `VECTOR_STORE_PATH` | ❌ No | `data/vector_store` | - |
| `SIMILARITY_THRESHOLD` | ❌ No | `1.2` | - |

**Validation Process:**
```python
1. Check if required vars are set
2. Validate against allowed values
3. Run custom validators
4. Apply defaults for missing optional vars
5. Print summary (with redaction for sensitive values)
6. Exit if validation fails in strict mode
```

**Security:**
- Redacts sensitive values in logs/output
- Patterns: `*_KEY`, `*_SECRET`, `*_TOKEN`, `PASSWORD*`

#### **Logging Configuration** (`logging_config.py`)

**Purpose**: Centralized structured logging setup

**Features:**
- **Structured Logging**: JSON or console output
- **Correlation IDs**: Request tracing across components
- **Context Processors**: Timestamps, log levels, agent metadata
- **File Logging**: Optional file output with rotation support

**Configuration:**
```python
configure_logging(
    log_level="INFO",              # DEBUG/INFO/WARNING/ERROR/CRITICAL
    json_logs=False,                # JSON (prod) vs console (dev)
    enable_file_logging=True,       # Enable file output
    log_file_path="logs/app.log"    # Log file path
)
```

**Processors:**
1. `merge_contextvars`: Correlation ID tracking
2. `add_correlation_id`: Include correlation ID in logs
3. `add_agent_context`: Agent-specific metadata
4. `add_log_level`: Log level information
5. `TimeStamper`: ISO timestamps
6. `format_exc_info`: Exception formatting
7. `JSONRenderer` or `ConsoleRenderer`: Output format

**Usage:**
```python
logger = structlog.get_logger(__name__)
logger.info(
    "tool_execution_completed",
    tool="doc_retriever",
    result_length=1500
)
```

---

### 6. **Utilities** (`app/utils/`)

#### **LLM Client** (`llm.py`)

**Purpose**: Centralized LLM client factory

```python
def get_llm(model="gpt-5-nano", temperature=0):
    return ChatOpenAI(model=model, temperature=temperature)
```

**Configuration:**
- Model: `gpt-5-nano` (default)
- Temperature: `0` (deterministic)
- API Key: From `OPENAI_API_KEY` environment variable

---

## Data Flow

### 1. **User Query Flow**

```
┌──────────────┐
│ User enters  │
│   question   │
└──────┬───────┘
       │
       ▼
┌──────────────────────────────────────────┐
│ main.py                                  │
│ - Create AgentState(user_input=question) │
│ - Generate correlation_id                │
└──────┬───────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────┐
│ Planner Agent                            │
│ - Analyze question                       │
│ - Select tool (LLM structured output)    │
│ - Set: plan, selected_tool, tool_input   │
└──────┬───────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────┐
│ Worker Agent                             │
│ - Route to selected tool                 │
│ - Execute tool function                  │
│ - Set: tool_output, draft_answer         │
└──────┬───────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────┐
│ Reviewer Agent                           │
│ - Review draft_answer                    │
│ - Improve if needed (LLM)                │
│ - Set: final_answer, review_feedback     │
└──────┬───────────────────────────────────┘
       │
       ▼
┌──────────────┐
│ Display to   │
│    user      │
└──────────────┘
```

### 2. **RAG Document Processing Flow**

```
┌─────────────────┐
│ Application     │
│   Startup       │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ initialize_vector_store()           │
│ - Check if persisted store exists   │
└────────┬────────────────────────────┘
         │
         ├─── Exists ────┐
         │               ▼
         │        ┌──────────────────┐
         │        │ FAISS.load_local │
         │        └──────────────────┘
         │
         └─── Not Exists ───┐
                            ▼
         ┌──────────────────────────────────┐
         │ build_vector_store_from_documents│
         └────────┬─────────────────────────┘
                  │
                  ▼
         ┌─────────────────┐
         │ load_documents()│
         │ (data/docs/)    │
         └────────┬────────┘
                  │
                  ▼
         ┌─────────────────────┐
         │ For each document:  │
         │ - chunk_document()  │
         │ - Add metadata      │
         └────────┬────────────┘
                  │
                  ▼
         ┌──────────────────────┐
         │ get_embeddings()     │
         │ (OpenAI)             │
         └────────┬─────────────┘
                  │
                  ▼
         ┌──────────────────────┐
         │ FAISS.from_documents │
         │ (build index)        │
         └────────┬─────────────┘
                  │
                  ▼
         ┌──────────────────────┐
         │ save_local()         │
         │ (persist to disk)    │
         └──────────────────────┘
```

### 3. **Document Retrieval Flow**

```
┌──────────────────┐
│ doc_retriever    │
│ tool called      │
└────────┬─────────┘
         │
         ▼
┌──────────────────────┐
│ get_vector_store()   │
│ (singleton)          │
└────────┬─────────────┘
         │
         ▼
┌──────────────────────────────────────┐
│ retrieve_context(query, k=10)        │
│ - similarity_search_with_score()     │
└────────┬─────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────┐
│ Filter by similarity threshold       │
│ (L2 distance < 1.2)                  │
└────────┬─────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────┐
│ Format results:                      │
│ [source]
│ content                              │
│ ---                                  │
└────────┬─────────────────────────────┘
         │
         ▼
┌──────────────────┐
│ Return context   │
│ to worker agent  │
└──────────────────┘
```

---

## Technology Stack

### **Core Dependencies**

| Category | Technology | Version | Purpose |
|----------|-----------|---------|----------|
| **Language** | Python | 3.13.5 | Runtime |
| **Package Manager** | uv | - | Dependency management |
| **LLM Framework** | LangChain Core | 1.2.28 | LLM abstractions |
| **Workflow** | LangGraph | 1.1.6 | Multi-agent orchestration |
| **LLM Provider** | LangChain OpenAI | 1.1.12 | OpenAI integration |
| **Embeddings** | LangChain OpenAI | 1.1.12 | Text embeddings |
| **Vector Store** | FAISS (CPU) | 1.13.2 | Similarity search |
| **Text Splitting** | LangChain Text Splitters | 1.1.1 | Document chunking |
| **Logging** | Structlog | 25.5.0 | Structured logging |
| **Environment** | python-dotenv | 1.2.2 | .env file loading |
| **Testing** | pytest | 9.0.3 | Unit testing |
| **Testing** | pytest-cov | 7.1.0 | Coverage reporting |
| **Testing** | pytest-mock | 3.15.1 | Mocking |
| **Interactive** | ipython | 9.12.0 | REPL |

### **LangChain Ecosystem**

```
langchain-core (1.2.28)
├── langchain-openai (1.1.12)
├── langchain-huggingface (1.2.1)
├── langchain-community (0.4.1)
├── langchain-text-splitters (1.1.1)
└── langgraph (1.1.6)
```

---

## Module Details

### **Project Structure**

```
ai-assistant/
├── main.py                      # Application entry point
├── pyproject.toml               # Project dependencies (uv)
├── pytest.ini                   # Pytest configuration
├── README.md                    # Setup instructions
├── .env.sample                  # Environment variable template
├── .env                         # Environment variables (gitignored)
├── graph_image.png              # Generated workflow visualization
│
├── app/                         # Application modules
│   ├── agents/                  # Multi-agent system
│   │   ├── graph.py            # LangGraph workflow definition
│   │   ├── state.py            # Agent state model
│   │   ├── planner.py          # Planner agent (tool selection)
│   │   ├── worker.py           # Worker agent (tool execution)
│   │   ├── reviewer.py         # Reviewer agent (answer refinement)
│   │   └── model.py            # Pydantic models (ToolDecision, ReviewResult)
│   │
│   ├── rag/                     # RAG pipeline
│   │   ├── ingestion.py        # Document loading
│   │   ├── chunking.py         # Document chunking strategies
│   │   ├── embeddings.py       # Embedding generation
│   │   ├── vector_store.py     # FAISS vector store management
│   │   └── retriever.py        # Similarity search
│   │
│   ├── tools/                   # Tool implementations
│   │   ├── registry.py         # Tool registry
│   │   ├── base.py             # Base models
│   │   ├── code_explainer.py   # Code explanation tool
│   │   ├── doc_retriever.py    # Documentation retrieval tool
│   │   └── architecture_advisor.py  # Architecture advice tool
│   │
│   ├── config/                  # Configuration management
│   │   ├── env_validator.py    # Environment variable validation
│   │   └── logging_config.py   # Structured logging setup
│   │
│   └── utils/                   # Utilities
│       └── llm.py              # LLM client factory
│
├── data/                        # Data directory
│   ├── docs/                   # Documentation corpus (RAG source)
│   │   ├── ARCHITECTURE.md
│   │   ├── DECISIONS.md
│   │   ├── README.md
│   │   ├── ROADMAP.md
│   │   ├── architecture/
│   │   │   ├── data-model.md
│   │   │   ├── high-level-design.md
│   │   │   └── sequence-diagram.md
│   │   ├── docs/
│   │   │   ├── api-contracts.md
│   │   │   ├── async-processing.md
│   │   │   ├── comparison-engine.md
│   │   │   ├── ingestion-flow.md
│   │   │   └── system-overview.md
│   │   ├── config/
│   │   │   ├── logging.yaml
│   │   │   └── settings.yaml
│   │   ├── data/
│   │   │   ├── sample_input_1.json
│   │   │   └── sample_input_2.json
│   │   ├── infra/
│   │   │   └── terraform/
│   │   │       ├── main.tf
│   │   │       └── variables.tf
│   │   ├── java-service/
│   │   │   └── src/main/java/com/example/
│   │   │       ├── App.java
│   │   │       └── controller/ProcessController.java
│   │   ├── src/
│   │   │   ├── api.py
│   │   │   ├── comparator.py
│   │   │   ├── ingestion.py
│   │   │   ├── main.py
│   │   │   ├── processor.py
│   │   │   ├── storage.py
│   │   │   └── utils/
│   │   │       ├── diff_utils.py
│   │   │       └── normalization.py
│   │   └── tests/
│   │       ├── test_comparator.py
│   │       └── test_ingestion.py
│   │
│   └── vector_store/           # Persisted FAISS index
│       ├── index.faiss
│       └── index.pkl
│
└── tests/                       # Test suite
```

---

## Configuration Management

### **Environment Variables**

**File**: `.env` (not committed to git)
**Template**: `.env.sample`

```bash
# API Keys
OPENAI_API_KEY=sk-...

# Logging Configuration
LOG_LEVEL=INFO                    # DEBUG, INFO, WARNING, ERROR, CRITICAL
JSON_LOGS=false                   # true for production, false for development
LOG_FILE_PATH=logs/app.log
ENABLE_FILE_LOGGING=true

# RAG Configuration
EMBEDDING_PROVIDER=openai
VECTOR_STORE_PATH=data/vector_store
SIMILARITY_THRESHOLD=1.2          # L2 distance threshold
```

### **Validation on Startup**

```python
# main.py
validated_env = validate_environment(verbose=True)
```

**Output:**
```
============================================================
🔧 Environment Configuration Summary
============================================================
✅ OPENAI_API_KEY          = ***REDACTED***      [env]
✅ LOG_LEVEL               = INFO                [env]
✅ JSON_LOGS               = false               [default]
✅ LOG_FILE_PATH           = logs/app.log        [default]
✅ ENABLE_FILE_LOGGING     = true                [env]
✅ EMBEDDING_PROVIDER      = openai              [default]
✅ VECTOR_STORE_PATH       = data/vector_store   [default]
✅ SIMILARITY_THRESHOLD    = 1.2                 [default]
============================================================
```

---

## Logging and Observability

### **Structured Logging**

**Library**: Structlog
**Formats**: JSON (production) or Console (development)

**Example Log Entry (Console):**
```
2024-01-15T10:30:45 [info     ] tool_execution_completed correlation_id=abc-123 node=worker_node selected_tool=doc_retriever draft_answer_length=1500
```

**Example Log Entry (JSON):**
```json
{
  "event": "tool_execution_completed",
  "correlation_id": "abc-123",
  "node": "worker_node",
  "selected_tool": "doc_retriever",
  "draft_answer_length": 1500,
  "timestamp": "2024-01-15T10:30:45.123456",
  "level": "info"
}
```

### **Correlation ID Tracking**

```python
# main.py
correlation_id = str(uuid.uuid4())
structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
```

**Purpose**: Trace a single user request through all agents and tools

### **Key Log Events**

| Event | Component | Purpose |
|-------|-----------|----------|
| `ai_assistant_started` | main.py | Application startup |
| `vector_store_ready` | main.py | Vector store initialized |
| `node_started` | Agents | Agent execution begins |
| `tool_decision_made` | Planner | Tool selection |
| `tool_execution_completed` | Worker | Tool execution finished |
| `review_complete` | Reviewer | Final answer generated |
| `retrieved_document` | Retriever | Document retrieved from vector store |
| `env_validation_successful` | Validator | Environment validated |

---

## RAG Pipeline

### **Document Corpus**

**Location**: `data/docs/`

**Content Types:**
- Markdown documentation (`.md`)
- Python code (`.py`)
- Java code (`.java`)
- JavaScript code (`.js`)
- Terraform configurations (`.tf`)
- JSON/YAML configurations

**Total Documents**: ~30 files across multiple subdirectories

### **Chunking Strategy**

**Markdown Documents:**
- Split on headers (#, ##, ###)
- Preserves document structure
- Metadata includes header hierarchy

**Code Documents:**
- Language-specific splitters
- 600 characters per chunk
- 90 character overlap
- Respects code structure (functions, classes)

**Structured Documents (JSON/YAML):**
- Structure-aware splitting
- 500 characters max
- Preserves nested structure

### **Vector Store**

**Technology**: FAISS (Facebook AI Similarity Search)
**Index Type**: Flat L2 (exact search)
**Persistence**: Disk-based (`data/vector_store/`)

**Initialization:**
1. Check for existing index on startup
2. Load from disk if available
3. Build from scratch if missing
4. Persist after building

**Rebuild Trigger:**
- Manual: `rebuild_vector_store()`
- Automatic: Missing or corrupted index

### **Retrieval Process**

1. **Query**: User question from `doc_retriever` tool
2. **Embedding**: Generate query embedding (OpenAI)
3. **Search**: FAISS similarity search (L2 distance)
4. **Filtering**: Keep documents with score < threshold (1.2)
5. **Ranking**: Sort by similarity score
6. **Formatting**: Consolidate into context string

**Parameters:**
- `k=10`: Retrieve top 10 candidates
- `score_threshold=1.2`: L2 distance cutoff

---

## Deployment Considerations

### **Environment Setup**

1. **Python Environment:**
   ```bash
   uv init --python 3.13.5 ai-assistant
   cd ai-assistant
   uv venv
   source .venv/bin/activate  # Linux/Mac
   ```

2. **Install Dependencies:**
   ```bash
   uv add langchain_core langchain-openai langgraph langchain-text-splitters \
          langchain-huggingface langchain_community ipython python-dotenv \
          structlog pytest pytest-cov pytest-mock faiss-cpu
   ```

3. **Configure Environment:**
   ```bash
   cp .env.sample .env
   # Edit .env and add OPENAI_API_KEY
   ```

4. **Initialize Vector Store:**
   ```bash
   python main.py
   # First run will build vector store (may take 1-2 minutes)
   ```

### **Production Recommendations**

#### **Logging**
- Enable JSON logs: `JSON_LOGS=true`
- Set appropriate log level: `LOG_LEVEL=INFO`
- Enable file logging: `ENABLE_FILE_LOGGING=true`
- Configure log rotation (external tool)

#### **Vector Store**
- Pre-build vector store before deployment
- Store in persistent volume
- Implement periodic rebuilds for updated docs
- Consider GPU-accelerated FAISS for large corpora

#### **API Keys**
- Use secrets management (AWS Secrets Manager, HashiCorp Vault)
- Rotate keys regularly
- Monitor API usage and costs

#### **Error Handling**
- Implement retry logic for LLM calls
- Add circuit breakers for external services
- Monitor error rates and latencies

#### **Scalability**
- Current design: Single-threaded, synchronous
- For concurrent requests: Add async support
- For high load: Deploy multiple instances with shared vector store

### **Monitoring**

**Key Metrics:**
- Request latency (end-to-end)
- Tool execution time
- LLM call latency
- Vector store query time
- Error rates by component
- Token usage (OpenAI)

**Logging Integration:**
- Structlog JSON output → Log aggregation (ELK, Splunk)
- Correlation IDs for distributed tracing
- Custom metrics extraction from structured logs

---
## Prompt Management

### Design Pattern
All LLM prompts are externalized to `app/prompts/` directory as `.txt` files.

### Loading Mechanism
- `load_prompt(path)` - Loads raw template
- `format_prompt(path, **vars)` - Loads and formats with variable validation

### Benefits
- Non-technical users can modify prompts
- Easy A/B testing and experimentation
- Clear version control of prompt changes

---

## Future Enhancements

### **Short-Term**

1. **Async Support**
   - Convert to async/await for concurrent requests
   - Use `asyncio` for parallel tool execution

2. **Conversation Memory**
   - Add LangGraph checkpointer for state persistence
   - Implement conversation history
   - Support follow-up questions

3. **Enhanced RAG**
   - Implement re-ranking for better retrieval
   - Add query expansion/reformulation
   - Experiment with hybrid search (keyword + semantic)

4. **Tool Expansion**
   - Add web search tool
   - Add code execution tool (sandboxed)
   - Add diagram generation tool

### **Medium-Term**

1. **Multi-Turn Conversations**
   - Implement conversation state management
   - Add clarification questions
   - Support context carryover

2. **Advanced Routing**
   - Implement conditional edges in LangGraph
   - Add tool chaining (multiple tools per query)
   - Support parallel tool execution

3. **Evaluation Framework**
   - Add automated testing for agent responses
   - Implement RAG evaluation metrics (precision, recall)
   - A/B testing for prompt variations

4. **UI/API Layer**
   - Build REST API (FastAPI)
   - Add web interface
   - Implement streaming responses

### **Long-Term**

1. **Multi-Modal Support**
   - Add image understanding (GPT-4V)
   - Support diagram analysis
   - Generate visualizations

2. **Advanced Agent Capabilities**
   - Implement self-reflection and planning
   - Add tool creation capabilities
   - Support agent collaboration

3. **Enterprise Features**
   - Multi-tenancy support
   - Role-based access control
   - Audit logging
   - Custom knowledge base per tenant

4. **Performance Optimization**
   - Implement caching layer (Redis)
   - Add GPU support for embeddings
   - Optimize vector store (HNSW index)
   - Batch processing for multiple queries

---

## Conclusion

The AI Assistant is a well-architected multi-agent system that demonstrates best practices in:

- **Modularity**: Clear separation between agents, tools, RAG, and configuration
- **Observability**: Comprehensive structured logging with correlation tracking
- **Robustness**: Environment validation and error handling
- **Extensibility**: Tool registry pattern for easy expansion
- **Performance**: Persistent vector store with efficient retrieval

The system is production-ready for single-user scenarios and can be extended to support concurrent users, conversation memory, and additional tools as needed.

---

**Document Version**: 1.0  
**Last Updated**: 2026-05-08  
**Author**: AI Assistant Architecture Analysis