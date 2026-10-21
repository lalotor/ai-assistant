# Optional one-revision loop after the existing Reviewer

The Week 11 experiment needed to test whether a reviewer-driven revision measurably improves answers without turning the Planner → Worker → Reviewer pipeline into an open-ended agent loop. The existing Reviewer already rewrote drafts inline, but that behavior was implicit and could not be evaluated separately from the single-pass path. We kept the three-stage graph and added a structured `approve`/`revise`/`abstain` decision, a single `revision` node that reuses the Worker's existing tool output and retrieved sources, and a second Reviewer pass (`reviewer_final`) that can only approve, abstain, or report that the revision budget is exhausted. Revision is opt-in (`revision_enabled=False` by default, `--revision` on the CLI, `revision_enabled` on `/ask`, `--revision` on the evaluation runner) so the normal path retains its existing cost and latency.

## Considered Options

- **Keep the Reviewer's inline rewrite only**: cheapest and already working, but the reviewer's correction and the model's self-critique remain one opaque call; there is no separate revision budget, evidence path, or trace event to evaluate.
- **Open-ended critique/revise loop**: conceptually flexible, but unbounded cost, latency, and failure modes; the week's scope explicitly excludes a general reflection framework.
- **One separate revision plus final review (chosen)**: adds at most one LLM call for revision and one for final review, makes the decision and budget observable, preserves the original retrieved evidence, and gives evaluation a clean single-pass vs. revision comparison.
- **Revision without final review**: cheaper, but the result could not honestly be presented as reviewer-approved after the revision; a final review is the minimum needed to report the revised answer's review status.

## Evaluation Outcome (2026-10-20)

Three full runs per mode showed a higher aggregate keyword answer score for
revision-enabled mode (0.73 -> 0.86), but only four revisions were attempted
on two Doc Retriever questions. Manual inspection found one genuine
improvement (DiffService inputs: 0.33 -> 1.00) and one unreliable result
(ingestion source types: every answering run still omitted the `FileSource` base class,
while substring keyword matching inflated the score). The no-revision
questions contributed only sampling variance. The decision is therefore to
keep revision opt-in; do not enable it by default until a larger,
within-question semantic evaluation shows a broader benefit.

## Consequences

- `ReviewResult.decision` is now required. Malformed or missing decisions fail through the existing Week 10 reviewer-failure path; an unreviewed draft is never returned.
- A revision consumes one budget unit in graph routing. Even if the final Reviewer requests another revision, the graph ends and the answer is marked `budget_exhausted` with an explicit limitation.
- Single-pass mode maps a `revise` decision to the Reviewer's inline answer and records `revision_skipped`; it does not make an extra revision or final-review call. If that inline answer is blank or identical to the original draft, the workflow abstains rather than presenting an unreviewed draft as the result.
- Revision uses the existing `tool_output`, `retrieved_sources`, and `retrieval_trace` and does not re-run retrieval, so source provenance is preserved. The post-revision Reviewer is given the original tool output and source list because the revised prose no longer contains the raw evidence. A revision failure is a terminal graph failure, not a silent fallback to the draft.
- The Execution Trace carries a Review Trace plus `reviewer`/`revision`/`reviewer_final` stage events. `abstained` and `budget_exhausted` outcomes mark the trace `degraded`; `revision_skipped` remains `success` because it is an explicit single-pass policy.
- The optional path adds one or two LLM calls only on questions where the Reviewer asks for revision. The evaluation comparison must justify whether that cost is worthwhile; revision is not presumed better.
