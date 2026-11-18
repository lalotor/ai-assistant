# Week 11: single-pass vs revision-enabled (3 full runs each)

Questions: 11 unique; runs: 33 baseline, 33 revision

## Summary

Answer score:      0.73 -> 0.86 (+0.14)  [improved 4, unchanged 5, degraded 2]
Retrieval score:   0.53 -> 0.56 (+0.03)  [improved 1, unchanged 10, degraded 0]
Latency avg:       8421.3 ms -> 9000.4 ms (+579.1 ms)
Latency P50:       4311.0 ms -> 4397.6 ms
Latency P95:       24382.6 ms -> 22604.5 ms
LLM calls:         99 -> 107 total; 3.00 -> 3.24 per question (+0.24)
Tokens:            148161 -> 161252 total; 4490 -> 4886 per question (+397)
Review outcomes:   baseline: abstained=6, approved=27; revision: abstained=3, approved=26, revised=4
Revision attempts: 4 across revision runs on 2 of 11 questions; final answers changed vs draft: 33

## Per-question

| Question | Base score | Rev score | Δ score | Base retrieval | Rev retrieval | Δ retrieval | Δ latency ms | Δ calls | Δ tokens | Rev count | Changed | Outcome |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Considering only your internal documentation, how many ingestion file source types do we have? | 0.00 | 0.67 | +0.67 | 0.44 | 0.78 | +0.33 | +1964 | +1.33 | +1387 | 2 | 3 | approved=1, revised=2 |
| Considering only your internal documentation, what inputs does DiffService take? | 0.33 | 1.00 | +0.67 | 1.00 | 1.00 | +0.00 | +2695 | +1.33 | +2215 | 2 | 3 | approved=1, revised=2 |
| Considering only your internal documentation, what is the cache TTL config? | 0.75 | 0.75 | +0.00 | 0.67 | 0.67 | +0.00 | +96 | +0.00 | -36 | 0 | 3 | approved=3 |
| Considering only your internal documentation, how is the MongoDB being used? | 1.00 | 1.00 | +0.00 | 1.00 | 1.00 | +0.00 | +196 | +0.00 | +30 | 0 | 3 | abstained=3 |
| Considering only your internal documentation, what are the four specialized queue types used in the async processing architecture? | 1.00 | 1.00 | +0.00 | 0.67 | 0.67 | +0.00 | -147 | +0.00 | -11 | 0 | 3 | approved=3 |
| Considering only your internal documentation, what are the normalization stages applied before comparison in the comparison engine? | 1.00 | 1.00 | +0.00 | 1.00 | 1.00 | +0.00 | -490 | +0.00 | -133 | 0 | 3 | approved=3 |
| What retry behavior is documented for failed queue processing? | 0.83 | 0.75 | -0.08 | 1.00 | 1.00 | +0.00 | -451 | +0.00 | -237 | 0 | 3 | approved=3 |
| What are the pros and cons of using a queue-based asynchronous architecture versus synchronous REST for long-running file processing operations? | 0.60 | 0.80 | +0.20 | 0.00 | 0.00 | +0.00 | +162 | +0.00 | -276 | 0 | 3 | approved=3 |
| From a software architecture perspective, what are the benefits and trade-offs of using a polyglot architecture with Python for orchestration and Java for compute-intensive tasks? | 0.93 | 0.87 | -0.07 | 0.00 | 0.00 | +0.00 | +3662 | +0.00 | +1187 | 0 | 3 | approved=3 |
| Explain this code: class ProcessingPipeline:     def __init__(self, job_id):         self.job_id = job_id         self.stages = []     def add_stage(self, name, handler):         self.stages.append({'name': name, 'handler': handler})     def execute(self, context):         result = context         for idx, stage in enumerate(self.stages):             result = stage['handler'](result)         return result | 0.60 | 0.73 | +0.13 | 0.00 | 0.00 | +0.00 | -999 | +0.00 | -138 | 0 | 3 | approved=3 |
| Explain this code: def calculate_diff(source, target, path=''):     differences = []     if isinstance(source, dict):         all_keys = set(source.keys()) \| set(target.keys())         for key in all_keys:             differences.extend(calculate_diff(source.get(key), target.get(key), f'{path}.{key}'))     elif source != target:         differences.append({'path': path, 'type': 'modified', 'old': source, 'new': target})     return differences | 0.93 | 0.93 | +0.00 | 0.00 | 0.00 | +0.00 | -319 | +0.00 | +375 | 0 | 3 | approved=3 |

## Reading

Quality signal: 4 improved, 5 unchanged, 2 degraded on keyword-based answer score.
Cost signal: revision adds one revision call and one final-review call only on runs where the reviewer requests revision.
Changed counts final answers that differ from the Worker draft; this includes single-pass reviewer edits as well as revisions.
Caveat: keyword/source overlap is a proxy for answer quality; inspect the raw result files for representative answers before making a default-on decision.

## Manual audit of revision-triggered questions

Only two questions triggered a revision (four attempts total). The other nine
questions never called the revision node; their deltas are run-to-run sampling
and reviewer-policy variance, not revision effects.

| Question | Baseline (3 runs) | Revision (3 runs) | Manual check |
|---|---:|---:|---|
| Ingestion source types | 0.00 (1 abstain, 2 incomplete) | 0.67 (2 revisions, 1 approved) | Every non-abstaining run named the three concrete subclasses; none named the `FileSource` base class. The keyword scorer's substring match for `FileSource` inflates this result, so it is not a reliable quality gain. |
| DiffService inputs | 0.33 (2 abstain, 1 correct) | 1.00 (2 revisions, 1 approved) | Revision-enabled runs consistently listed the four call-site arguments. This is the clearest genuine improvement. |

The two revision-triggered questions contribute approximately +0.121 of the
+0.138 aggregate answer-score delta. If the ingestion result is discounted,
the defensible gain is roughly +0.061 from DiffService plus a small residual
from no-revision variance.

## Recommendation

**Keep revision opt-in (`revision_enabled=False`); do not enable it by default
for this release.** The loop is bounded and traceable, and it corrected the
DiffService call-site answer in all three revision-enabled runs. However:

- Only 2 of 11 questions triggered revision (four attempts across 33
  revision-mode runs), so there is no evidence of broad benefit outside
  Doc Retriever evidence failures.
- The ingestion result is not trustworthy: every revised answer still named
  only three source classes, and the keyword scorer credited `FileSource`
  through substring matching. The measured improvement there is partly an
  abstention-to-partial-answer/scoring artifact.
- The nine no-revision questions account for only residual variance; the
  aggregate +0.14 answer score should not be read as a general revision
  effect.
- Cost is modest but real: +0.24 LLM calls and +397 tokens per question, and
  +579 ms average latency. It is paid only when revision triggers, but that
  trigger is currently rare and uneven.

Revisit the default after a larger evaluation with a semantic or
answer-quality rubric and enough revision-triggered cases to compare within
question. Until then, `--revision` / `revision_enabled=true` remains the safe
path for experiments and targeted Doc Retriever failures.

## Method notes and limitations

- These six runs (three per mode) used the corrected Reviewer prompt from
  2026-10-20. An earlier comparison exposed that the post-revision Reviewer
  received only revised prose and no raw tool output; it abstained after
  revision. Passing the original tool output and sources fixed that failure
  before these runs.
- There are 11 unique questions and three independent runs per mode. No fixed
  model seed was used, so repeated-run scores include sampling variance. This
  is not a paired within-question experiment and has no statistical
  significance test.
- Keyword/source overlap is a proxy. Manual inspection found at least one
  baseline answer that was reviewer meta-commentary rather than an answer,
  plus the ingestion ambiguity above.
- No live run exhausted the revision budget, failed revision, or timed out;
  those paths are covered by unit and integration tests.