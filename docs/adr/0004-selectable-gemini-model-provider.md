# ADR 0004: Selectable Gemini model provider

**Status:** Accepted

## Context

The assistant used OpenAI for chat generation and vector embeddings. A Gemini
API key is available, so the application should support Gemini without
removing the existing OpenAI path or changing its default behavior. Retrieval
embeddings are persisted in a FAISS index; vectors produced by different
providers/models cannot safely be mixed or queried as if they shared one
embedding space.

## Decision

Keep OpenAI as the default provider for chat and embeddings. Add independent
`LLM_PROVIDER` and `EMBEDDING_PROVIDER` selection (`openai` or `gemini`), with
`GEMINI_API_KEY` required when either selected provider is Gemini.
`OPENAI_API_KEY` is required and validated only when at least one selected
provider is OpenAI. The `langchain-google-genai` integration supplies Gemini
chat structured output and text embeddings.

Persist the embedding provider and model alongside the FAISS index. Rebuild the
index when its recorded embedding configuration differs from the selected
provider/model. Existing unmarked indexes are treated as the historical
OpenAI `text-embedding-3-small` index; that legacy assumption applies only to
the default OpenAI configuration.

## Consequences

- Existing OpenAI deployments retain their provider defaults and API behavior.
- A Gemini-only setup must set both providers to `gemini` and provide
  `GEMINI_API_KEY`; the key is not stored in the repository.
- Switching embedding providers or model names rebuilds and re-embeds the
  corpus, which can incur API usage and startup delay.
- Provider construction, structured-output configuration, and embedding
  selection are tested without making live Gemini API calls. External model
  behavior still requires validation with the user's own key and model access.
