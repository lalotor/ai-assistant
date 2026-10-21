# Week 11 — Controlled Reflection and Revision

**Project:** AI Engineering Assistant  
**Duration:** 4 hours  
**Core stack:** Python, LangGraph, LangChain, FAISS, OpenAI API, FastAPI

## 1. Mission

Week 10 strengthened reliability: the assistant now has explicit recovery behavior, bounded retries/timeouts, retrieval fallback handling, and failure-oriented tests. First, verify the actual state of those changes in the repository rather than assuming every item is implemented exactly as planned.

This week, investigate whether a **bounded critique-and-revision loop** can improve the assistant's answers enough to justify its additional latency and token cost.

The existing workflow already has a planner, worker, and reviewer. Do not add another agent just to make the architecture look more sophisticated. Refine the current reviewer into an explicit decision point and add one controlled revision path.

### Deliverables

- Explicit answer-quality criteria.
- A structured reviewer decision: `approve`, `revise`, or `abstain` (or equivalent values consistent with current contracts).
- At most one revision attempt in the initial implementation.
- Clear stopping conditions and a revision budget.
- Preservation of retrieved-source provenance through revision.
- Automated tests for approval, revision, abstention, and exhausted budget.
- A controlled comparison of single-pass and revision-enabled evaluation results.

**Core question:** Does revision measurably improve answer quality on this project, without an unacceptable increase in latency or token consumption?

## 2. Engineering principles

1. **Reflection must have a purpose.** Revise only when the reviewer identifies a specific, actionable deficiency.
2. **Keep the loop bounded.** The initial implementation permits at most one revision attempt.
3. **Make decisions explicit.** The reviewer must return structured output that the graph can validate and route on.
4. **Preserve evidence.** Revision must not discard or fabricate retrieved-source provenance.
5. **Do not confuse confidence with correctness.** A model's self-critique is not proof that an answer is correct.
6. **Measure the trade-off.** Compare quality, latency, LLM calls, and token usage against a single-pass baseline.
7. **Keep the existing architecture.** Extend the current planner → worker → reviewer graph instead of introducing a new multi-agent subsystem.
8. **Reuse Week 10 reliability policies.** A reviewer or revision call can fail, time out, or exhaust its budget; those cases must follow explicit existing policies.

## 3. Define the answer-quality criteria

Start with criteria that fit the assistant's current use cases. Use a small rubric rather than an elaborate scoring system.

| Criterion | Question for the reviewer |
|---|---|
| Correctness | Is the answer supported by the available evidence and consistent with what is known? |
| Evidence support | Are factual claims grounded in the retrieved sources when the question requires internal documentation? |
| Relevance | Does the answer address the user's actual question? |
| Completeness | Does it cover the important parts of the request without unnecessary material? |

The reviewer should return actionable feedback when it chooses `revise`. For example, “Name the three source types explicitly; the retrieved evidence lists them” is more useful than “Improve the answer.”

For questions that require internal documentation, lack of sufficient evidence should lead to abstention or a qualified limitation—not an instruction to invent missing facts. Do not force every answer through the same evidence standard if the repository supports other tool types, such as architecture advice or code explanation; define criteria appropriate to the route and document any route-specific behavior.

## 4. Proposed workflow

Keep the current workflow and add a bounded conditional transition after review.

```text
START → planner → worker → reviewer
                           ├─ approve → END
                           ├─ abstain → END
                           └─ revise → worker (one attempt) → reviewer/finalize
```

The exact graph can differ to fit the existing implementation. The important constraints are:

- A normal answer can be approved without revision.
- An unsupported answer can be rejected or marked for abstention.
- A revision is attempted only when the reviewer provides actionable feedback.
- After the single allowed revision, the workflow terminates; it must not loop indefinitely.
- The final result and trace should show whether revision occurred and why.

For the revised answer, choose and document whether the reviewer evaluates it again or whether the workflow finalizes it after the revision. Prefer a final evaluation if it fits the existing graph and four-hour scope, but do not allow a second revision. If the final evaluation is unavailable, the result must not be presented as reviewer-approved.

## 5. Four-hour work plan

### Session 1 — Inspect and define the rubric (45 minutes)

**Goal:** Understand the existing reviewer and define the smallest useful contract change.

1. Inspect the current planner → worker → reviewer graph, state schema, prompts, output parsing, tests, execution trace, and evaluation runner.
2. Check the Week 10 reliability changes and identify how reviewer/revision failures should be handled.
3. Define the criteria the reviewer should evaluate.
4. Define the structured reviewer decision and what fields are needed to support actionable feedback.
5. Decide how the graph should behave for `approve`, `revise`, and `abstain`.

**Deliverable:** A short reviewer contract and an updated design note or existing architecture documentation.

### Session 2 — Implement structured review and bounded routing (60 minutes)

**Goal:** Make the review decision explicit and add one conditional revision path.

1. Use the project's existing typed-contract conventions (for example, its current Pydantic models if applicable).
2. Validate the review decision and feedback before routing.
3. Add graph state only where needed to track the review decision, revision count, and relevant feedback.
4. Add a conditional edge for approval, abstention, or revision.
5. Enforce a maximum of one revision attempt in the graph logic—not just in the prompt.
6. Ensure invalid reviewer output follows a safe, documented error path.

**Deliverable:** A working bounded review-and-revision path with tests for the routing logic.

### Session 3 — Preserve evidence and trace the loop (60 minutes)

**Goal:** Make revisions grounded, explainable, and observable.

1. Pass the original question, current draft, reviewer feedback, and relevant retrieved evidence to the revision step.
2. Avoid unnecessary re-retrieval unless the existing architecture has a clear reason to retrieve more evidence.
3. Preserve source metadata and provenance in the final result.
4. Extend the existing execution trace with review decisions, revision count, and per-stage timings/usage where available.
5. Apply Week 10 timeout, retry, and failure policies to reviewer and revision calls.
6. Make it clear when the final answer was revised, abstained, or could not be fully reviewed.

**Deliverable:** An end-to-end trace showing an initial draft, critique, bounded revision, and final outcome.

### Session 4 — Evaluate the value of revision (75 minutes)

**Goal:** Determine whether revision improves the assistant on the existing evaluation dataset.

1. Run the current evaluation in single-pass mode and preserve the results.
2. Run the same questions with revision enabled.
3. Keep model configuration, prompts other than the intended revision changes, dataset, and evaluation settings consistent where possible.
4. Compare answer-quality proxies, source/retrieval scores, latency, LLM calls, and token usage.
5. Inspect representative improved, unchanged, and degraded answers.
6. Document the result and recommend whether revision should be enabled by default.

**Deliverable:** A concise comparison report with limitations and a recommendation based on evidence.

## 6. Implementation guidance

### 6.1 Use a structured reviewer contract

Adapt the following conceptual fields to the existing state and model conventions; do not copy them blindly if equivalent fields already exist.

- **Decision:** `approve`, `revise`, or `abstain`.
- **Criteria results:** brief assessment of correctness, evidence support, relevance, and completeness.
- **Feedback:** specific, actionable changes required for a revision.
- **Evidence limitation:** what could not be verified, when relevant.
- **Reason:** a concise explanation of the decision.

Keep the contract small. Avoid adding numeric confidence scores unless you have a defined interpretation and use for them. A score that is not calibrated or evaluated can create false precision.

### 6.2 Make the revision budget enforceable

- Initialize the revision count explicitly.
- Increment it only when a revision attempt is actually made.
- Permit no more than one revision attempt in this week's implementation.
- Route to finalization or abstention when the budget is exhausted.
- Do not rely on prompt wording alone to prevent additional iterations.
- Ensure a failure during revision cannot restart the whole loop indefinitely.

If the graph's state is persisted or reused, ensure the revision count is scoped to the current request/execution rather than accidentally carried over from a previous question.

### 6.3 Give the worker actionable feedback

The revision step should receive:

- The original user question.
- The current draft.
- The reviewer's specific feedback.
- The relevant retrieved evidence and source metadata.
- Any output constraints already applied by the original workflow.

The revision instruction should say to correct the identified deficiency while preserving supported claims and source attribution. It should not encourage adding details that are absent from the evidence.

### 6.4 Handle abstention and reviewer failures deliberately

Abstention is a valid outcome when evidence is insufficient or the answer cannot be responsibly produced.

If the reviewer or revision call fails, apply the Week 10 policy. Do not silently treat an unreviewed draft as approved. Depending on existing API contracts, return an explicit degraded outcome, a safe limitation, or a terminal failure. Document which behavior is used.

### 6.5 Extend existing tracing, not a separate system

Build on the existing `ExecutionTrace` and telemetry. Record, where available:

- Initial reviewer decision.
- Revision attempted: yes/no.
- Revision count.
- Structured reason for revision or abstention.
- Reviewer and revision-stage durations.
- LLM call counts and token usage.
- Final outcome and whether the final answer was revised.
- Source/provenance information retained for the final answer.

Avoid logging sensitive prompt or document contents unnecessarily. Use structured fields rather than parsing free-form log messages to infer what happened.

## 7. Required automated tests

Use deterministic unit tests and controlled LLM/reviewer fakes where possible. Avoid relying exclusively on live model behavior to test graph control flow.

| Test | Expected assertion |
|---|---|
| Reviewer approves the initial answer | No revision is attempted |
| Reviewer requests revision | Exactly one revision is attempted |
| Reviewer abstains due to insufficient evidence | Workflow returns the documented abstention/limitation outcome |
| Reviewer requests revision after the budget is exhausted | No additional revision occurs |
| Reviewer output is malformed or invalid | Safe, documented error handling occurs |
| Revision call fails or times out | Week 10 failure policy is applied; no unbounded loop |
| Revised answer is produced | Original question and actionable feedback reach the revision step |
| Revision occurs | Source provenance is preserved and final trace reflects the loop |
| Revision makes an answer worse | Evaluation can record the regression; the system does not claim revision is inherently better |
| Normal approval path | Existing single-pass behavior remains available |

Add at least one integration test that exercises the full graph path from initial draft through review and revision to final outcome.

## 8. Evaluation methodology

The key experiment is **single-pass versus revision-enabled** on the same evaluation questions.

### Keep the comparison fair

- Use the same evaluation dataset.
- Keep model selection and configuration consistent where possible.
- Use the same scoring implementation for both modes.
- Preserve raw per-question results, not just aggregate scores.
- Record whether a revision was attempted and whether the final result changed.
- If model output variability is material, consider repeated runs for a small representative subset rather than drawing strong conclusions from one run.

### Compare these dimensions

| Dimension | What to inspect |
|---|---|
| Answer score | Did the existing answer-quality proxy improve? |
| Retrieval/source score | Did revision preserve grounding and source attribution? |
| Latency | What happened to average, p50, and p95 latency? |
| LLM calls | How many extra calls did revision introduce? |
| Tokens | How much additional input/output usage did revision consume? |
| Per-question outcome | Which answers improved, stayed the same, or became worse? |
| Abstention | Did the workflow abstain appropriately, or too often? |

The current evaluation scores are proxies, not definitive measures of correctness or groundedness. Supplement them with manual inspection of representative examples. Do not claim the system is more correct solely because a keyword-overlap score increased.

### Decision rule

At the end of the experiment, choose one of these outcomes:

- **Enable by default:** evidence suggests a meaningful quality benefit at acceptable cost and latency.
- **Keep optional:** benefits are limited to certain routes or question categories.
- **Do not enable by default:** improvements are not measurable, regressions occur, or the extra cost is not justified.

A negative or inconclusive result is a valid engineering outcome.

**Week 11 outcome (2026-10-20): Keep optional.** Across three full runs per
mode, the answer-score proxy rose from 0.73 to 0.86, but only four revisions
were attempted on two Doc Retriever questions. Manual inspection found one
genuine improvement (DiffService inputs) and one unreliable result (ingestion
source types, where substring matching inflated the score despite a missing
base class). The benefit is therefore question-specific and the evidence is
not strong enough to enable revision by default. See
`evaluation/reports/revision_comparison.md` and `docs/reliability.md`.

## 9. Definition of done

- [ ] Existing reviewer and graph behavior inspected before changes.
- [ ] Answer-quality criteria are documented.
- [ ] Reviewer returns validated structured decisions.
- [ ] Conditional routing supports approval, revision, and abstention.
- [ ] Revision budget is enforced in graph logic, with at most one attempt.
- [ ] Revision feedback is actionable and includes relevant evidence/context.
- [ ] Source provenance is preserved through revision.
- [ ] Week 10 reliability policies cover reviewer and revision failures.
- [ ] Traces show review decisions, revision attempts, and final outcome.
- [ ] Automated tests cover the normal path, revision, abstention, budget exhaustion, malformed output, and failures.
- [ ] Single-pass and revision-enabled evaluations are compared on the same dataset.
- [ ] A recommendation is documented based on quality, latency, and token usage.

## 10. Targeted references

Use these as targeted references, not additional courses:

- [LangGraph documentation](https://docs.langchain.com/oss/python/langgraph/overview) — graph state, conditional routing, and workflow structure.
- [Pydantic documentation](https://docs.pydantic.dev/latest/) — structured contracts and output validation, if consistent with the existing project.
- [OpenAI API documentation](https://platform.openai.com/docs/overview) — current API behavior and structured-output capabilities relevant to the model/client already in use.

Prefer existing project conventions and installed dependencies over introducing new ones solely for this week's task.

## 11. Final engineering challenge

Demonstrate this scenario end to end:

> The assistant drafts an answer from internal documentation. The reviewer identifies a specific omission and requests a revision. The worker revises the answer using the feedback and existing evidence. The workflow terminates within the one-revision limit, preserves source attribution, and records the review/revision sequence in the execution trace.

Also demonstrate:
1. An answer approved without revision.
2. An answer that should abstain because evidence is insufficient.
3. A reviewer or revision failure handled under the Week 10 reliability policy.
4. An evaluation comparison showing whether revision improved or degraded results.

Week 11 is complete when the revision loop is bounded, testable, observable, and evaluated—not merely when the graph can call the model twice.

**Core principle:** Reflection is useful only when it leads to measurable improvement. A controlled, evidence-grounded revision policy is more valuable than an open-ended loop of model-generated critique.

## 12. Instructions for the AI coding companion

Work incrementally and inspect the repository before making changes.

1. **Inspect first.** Review the current graph, state schema, planner/worker/reviewer nodes, prompts, output parsing, `ExecutionTrace`, evaluation runner, tests, and the Week 10 reliability implementation.
2. **Report before editing.** Summarize the current architecture, what already exists, likely files to change, and any contract or test gaps.
3. **Propose the minimal design.** Explain the reviewer contract, conditional routing, revision budget, abstention behavior, trace changes, and evaluation plan before implementing.
4. **Preserve existing conventions.** Reuse current typed models, state fields, graph patterns, error handling, and telemetry where possible. Avoid unnecessary dependencies and unrelated refactoring.
5. **Implement in small steps.** Add/adjust contracts and deterministic tests, implement bounded routing, preserve provenance, extend traces, then run the evaluation comparison.
6. **Enforce the limit in code.** Do not rely only on prompt instructions to limit revisions. The graph/state logic must prevent more than one revision attempt.
7. **Test deterministically.** Use fakes/mocks for control-flow tests; use live model calls only where needed for a clearly identified integration or evaluation experiment.
8. **Compare fairly.** Run single-pass and revision-enabled modes against the same dataset and scoring configuration. Preserve raw results and report actual differences.
9. **Report honestly.** Summarize files changed, tests actually run, their results, evaluation differences, latency/token trade-offs, and known limitations. Do not claim a test passed unless it was executed successfully.
10. **Do not silently change contracts.** If API, state, trace, or evaluation schemas change, explain the change and update related tests/documentation consistently.
11. **Stop at Week 11 scope.** Do not build an open-ended autonomous loop, a general reflection framework, or persistent/resumable workflow infrastructure. Those are outside this week's objective.

Begin by inspecting the repository and reporting a concise implementation plan. Do not start with a large code change.
