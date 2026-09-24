# LLM-reranked hybrid retrieval instead of pure vector search or score fusion

The Doc Retriever tool (`app/tools/doc_retriever.py`) needed to handle both semantic questions ("how does X work conceptually?") and exact-identifier lookups ("what does `PaymentRetryService` do?"), which pure vector search handles unevenly: embeddings capture meaning well but often under-rank exact class/function names. We combine vector search (`app/rag/retriever.py`, k=10, L2 threshold) with a keyword search (`app/rag/keyword_retriever.py`, term-overlap scoring, top 4) via simple content-based dedup, then hand the merged, unranked set to the LLM (`_rerank_results`) with a prompt asking it to select and order the most relevant chunks by index, rather than fusing the two ranked lists with a formal algorithm like Reciprocal Rank Fusion (RRF).

## Considered Options

- **Pure vector search only**: simpler, but weak on exact identifier lookups (confirmed operationally: this is the majority failure mode in `evaluation/`'s `retrieval_failure` category).
- **Score-fusion (e.g. RRF) instead of LLM reranking**: cheaper and deterministic, but requires normalizing two very different scoring scales (L2 distance vs. keyword term-count) and doesn't use query-level semantic judgment the way an LLM rerank can.
- **LLM reranking (chosen)**: costs an extra LLM call per Doc Retriever invocation and depends on the model reliably returning parseable comma-separated indexes (`_parse_indexes` silently drops the reranked set to empty on a malformed response), but lets relevance be judged per-query rather than by a fixed scoring formula.

## Consequences

- Every Doc Retriever call makes two LLM calls total (structured tool-selection + rerank), which is a real cost/latency line item — the week 9 cost/latency instrumentation should account for this call separately from the Planner/Reviewer calls, not lump it into "one call per stage."
- The `_parse_indexes` failure mode (malformed LLM output → empty result set → "no relevant documentation found") is a silent quality cliff, not a crash — worth a specific eval failure category or retry/fallback if it recurs in practice.
