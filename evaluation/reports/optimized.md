# Week 9 Session 2b - Optimized (skip-trivial-rerank only; k=10 retained), 3 full-dataset runs, 33 questions

Questions:            33 (32 evaluated)
Avg latency:          8478.5 ms
P50 latency:          4319.5 ms
P95 latency:          20130.2 ms

Planner avg:          1488.4 ms
Worker avg:           4906.7 ms
Reviewer avg:         2081.3 ms

  vector search avg:  552.2 ms
  keyword search avg: 38.2 ms
  merge avg:          0.0 ms
  rerank avg:         784.4 ms

Avg answer score:     0.7
Avg retrieval score:  0.5

Total LLM calls:      96
Avg LLM calls/Q:      3.0
  planner avg:        1.0
  worker avg:         1.0
  reviewer avg:       1.0

Total tokens:         121957
  input tokens:       92249
  output tokens:      29708
Avg tokens/Q:         3811.2

## Notes (Session 2b)

Two optimizations were evaluated against the Session 2a baseline:

1. **Skip LLM reranking when the merged candidate set is <= 3** - kept.
   Rerank avg dropped 884.3ms -> 784.4ms, total LLM calls dropped 99 -> 96
   (3 trivial-skip calls across 21 doc_retriever invocations), with no
   quality cost (avg_retrieval_score held/improved: 0.419 -> 0.474;
   avg_answer_score essentially unchanged within normal run-to-run noise:
   0.679 -> 0.673).

2. **Reduce vector search k from 10 to 5** - reverted, not included in
   this report's numbers. A separate live 3-run eval with k=5 showed no
   latency improvement (vector_search avg rose to 687ms, up from the
   587ms baseline) and a small answer-score dip, confirming vector
   search's cost here is dominated by the embedding API round-trip, not
   FAISS's local candidate-count scoring - k wasn't the right lever for
   this bottleneck. See app/tools/doc_retriever.py's `_VECTOR_SEARCH_K`
   comment for the full rationale.
