# Revision-focused evaluation

Questions: 5 unique; runs: 15 baseline, 15 revision

## Summary

Answer score:      0.68 -> 0.91 (+0.24)  [improved 3, unchanged 2, degraded 0]
Retrieval score:   1.00 -> 1.00 (+0.00)  [improved 0, unchanged 5, degraded 0]
Latency avg:       3900.2 ms -> 5199.8 ms (+1299.7 ms)
Latency P50:       3850.8 ms -> 4176.3 ms
Latency P95:       4444.3 ms -> 10067.3 ms
LLM calls:         45 -> 55 total; 3.00 -> 3.67 per question (+0.67)
Tokens:            67887 -> 89212 total; 4526 -> 5947 per question (+1422)
Review outcomes:   baseline: abstained=4, approved=11; revision: abstained=1, approved=10, revised=4
Revision attempts: 5 across revision runs on 3 of 5 questions; final answers changed vs draft: 15

## Per-question

| Question | Base score | Rev score | Δ score | Base retrieval | Rev retrieval | Δ retrieval | Δ latency ms | Δ calls | Δ tokens | Rev count | Changed | Outcome |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Considering only your internal documentation, what inputs does DiffService take? | 0.67 | 1.00 | +0.33 | 1.00 | 1.00 | +0.00 | +2631 | +1.33 | +2388 | 2 | 3 | approved=1, revised=2 |
| Considering only your internal documentation, enumerate the common and status-specific fields returned by get_status for processing, completed, and failed jobs, and include its not-found response. | 0.97 | 0.97 | +0.00 | 1.00 | 1.00 | +0.00 | +1313 | +0.67 | +2103 | 1 | 3 | approved=2, revised=1 |
| Considering only your internal documentation, enumerate the file-storage lifecycle tiers with their storage class and age range, and include the documented expiration and database archival policies. | 0.00 | 0.58 | +0.58 | 1.00 | 1.00 | +0.00 | +2484 | +1.33 | +2776 | 2 | 3 | abstained=1, approved=1, revised=1 |
| Considering only your internal documentation, what context key does normalize_stage read, which context keys does it write, and how does it distinguish string content from an already-parsed value? Include the normalization_applied value. | 1.00 | 1.00 | +0.00 | 1.00 | 1.00 | +0.00 | +288 | +0.00 | -115 | 0 | 3 | approved=3 |
| Considering only your internal documentation, trace the asynchronous processing flow from POST /process through the four specialized queues to the client's status lookup. Name each queue in order and state the main worker action before the next handoff. | 0.74 | 1.00 | +0.26 | 1.00 | 1.00 | +0.00 | -218 | +0.00 | -45 | 0 | 3 | approved=3 |

## Reading

Quality signal: 3 improved, 2 unchanged, 0 degraded on keyword-based answer score.
Cost signal: revision adds one revision call and one final-review call only on runs where the reviewer requests revision.
Changed counts final answers that differ from the Worker draft; this includes single-pass reviewer edits as well as revisions.
Caveat: keyword/source overlap is a proxy for answer quality; inspect the raw result files for representative answers before making a default-on decision.

## Calibration and manual audit

The tracked dataset was pruned to five cases after calibration. Broad source-code
questions that consistently hit the evidence gate, and the `process_file` case
that intermittently failed retrieval, were not retained.

Across the three final revision runs, the reviewer attempted revision 5 times on
3 of 5 questions. This is a higher trigger density than the Week 11 full-suite
run, but it is not evidence that revision should be enabled by default.

- **DiffService inputs**: the actual Java call has four arguments:
  `request.getJobId()`, `request.getSystemAData()`,
  `request.getSystemBData()`, and `request.getAlgorithm()`. One revised answer
  incorrectly counted `request.getJobId()` twice because overlapping retrieved
  chunks repeated a boundary line. Treat the keyword-score improvement as
  provisional and audit this case against the source file.
- **Job status fields**: the revised answer correctly enumerated common fields,
  processing/completed/failed fields, and the 404 body. The baseline was already
  nearly complete, so the revision did not improve its measured score.
- **File-storage lifecycle**: the successful revised answer correctly listed the
  three tiers, `expires_at` transition policy, and one-year database archival.
  Another run abstained, so the score improvement partly reflects
  abstention-to-answer behavior rather than a consistently correct revision.
- **Normalization-stage and async-flow cases**: neither triggered in this
  comparison; their score differences are sampling variance, not revision
  effects.

The focused set is intentionally small and diagnostic. Keep using it alongside
the unchanged full and smoke datasets; do not combine its aggregate score with
the general regression benchmark.
