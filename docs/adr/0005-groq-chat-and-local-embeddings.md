# ADR 0005: Groq chat with local embeddings

## Status

Accepted

## Context

The assistant supports remote OpenAI and Gemini chat and embedding providers.
Groq offers an OpenAI-compatible chat endpoint, but it does not provide the
embeddings endpoint used by the assistant's RAG pipeline. Relying on Gemini or
OpenAI embeddings would still require an additional provider key and available
quota.

## Decision

- Add `groq` as an optional `LLM_PROVIDER`, using LangChain's `ChatOpenAI` with
  Groq's OpenAI-compatible Chat Completions base URL.
- Use `openai/gpt-oss-20b` as the Groq chat default; `LLM_MODEL` can override
  it.
- Use function-calling structured output for Groq. Its strict JSON-schema
  handling rejected the Planner's nested `tool_input` schema because it
  required every possible tool-specific field at once.
- Add `local` as an `EMBEDDING_PROVIDER`, implemented with
  `HuggingFaceEmbeddings` and `sentence-transformers/all-MiniLM-L6-v2` on CPU.
- Keep OpenAI as the default chat and embedding provider.
- Continue recording the embedding provider and model with the FAISS index so
  changing to local embeddings triggers a rebuild and re-embeds the corpus.

## Consequences

- A Groq chat plus local embeddings configuration requires only `GROQ_API_KEY`;
  the embedding model downloads from Hugging Face on first use and then runs
  locally.
- Building or switching the vector index uses local compute and no embedding
  API quota, but takes time and disk space for the model and index.
- Local embeddings can rank documents differently from OpenAI or Gemini
  embeddings, so retrieval quality may change after the rebuild.
- Groq model availability, account quota, and live structured-output behavior
  must be verified with the user's own Groq account; no key is stored in the
  repository.

## References

- [Groq OpenAI compatibility](https://console.groq.com/docs/openai)
- [Groq Structured Outputs](https://console.groq.com/docs/structured-outputs)
- [Groq Tool Use](https://console.groq.com/docs/tool-use)
