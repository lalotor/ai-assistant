# AI Workflow: Skills & Agents

How work in this repo is expected to flow from now on, using the skills in
`.agents/skills/` and the two-axis code-review pattern. This is the
durable reference; point to it from a prompt or session start rather than
re-deriving the process each time.

## Why this exists

As of the `ai-enhancements` track's foundation pass (commit `33b3965`),
this repo has:
- A domain glossary (`CONTEXT.md`) and an ADR log (`docs/adr/`).
- 11 generic engineering skills (from `mattpocock/skills`, tracked via
  `skills-lock.json`) plus 4 project-specific scaffolding/evaluation
  skills, all git-tracked in `.agents/skills/` so any Agent
  Skills-compliant harness picks them up.
- A proven-closed eval feedback loop (`run-and-triage-evaluation`) and a
  parallel-subagent review pattern (`code-review`) used on every
  substantive change so far.

This doc names the steady-state loop those pieces compose into, so future
sessions don't have to reconstruct it from commit archaeology.

## How to ask for work: plan first, by default

You never need to name a skill explicitly. Describe the feature or problem
in plain language ("let's do the caching piece of week 9") and the right
skill(s) get picked up from the table below, the same way skill
descriptions are designed to be matched.

**Planning precedes implementation by default, with an explicit
approval gate in between.** For anything beyond a trivial fix, the loop
is:

1. **You describe the feature or problem.** Informal is fine — a plan
   phase exists precisely so scope gets nailed down together rather than
   assumed upfront.
2. **A plan is produced first, not code.** Scope, files touched,
   approach, risks, open questions, and test scenarios. Right-sized to
   the work: a short in-chat plan for a single-tool change, a written
   `docs/plans/<name>.md` file for anything spanning multiple sessions or
   touching several modules.
3. **You review the plan and can request adjustments.** Nothing gets
   implemented until you say go. Revisions happen to the plan, not to
   code, until it's approved — this is the checkpoint where scope creep
   or a wrong assumption gets caught cheaply, before any tests or code
   exist.
4. **Only after approval does implementation start**, following the
   core loop below.

**Exception**: trivial, obviously-scoped fixes (a typo, a one-line bug, a
wording tweak) skip the plan-approval round trip — that would only add
friction for something with no real scope to review. Anything that
touches architecture, adds a new tool/endpoint/pipeline stage, or belongs
to a themed effort (e.g. a "week N" milestone) always goes through the
plan step first.

## The core loop (post-approval, or for trivial fixes)

Once a plan is approved (or the change is trivial enough to skip
planning):

1. **Orient**: read `CONTEXT.md` for domain vocabulary and check
   `docs/adr/` for decisions in the area you're about to touch. Every
   scaffolding and diagnosis skill below expects this as step zero.
2. **Pick the entry skill** for the kind of change (table below).
3. **Build test-first** where the change has clear input/output
   behavior — call the `tdd` skill for the red→green loop. Seam-only
   tests, mocked at system boundaries (file I/O, LLM calls), never
   against internals; see `tests/tools/test_registry.py` and
   `tests/agents/test_worker.py` as the established pattern.
4. **Update the domain model as you go**, not after: if the change
   introduces a concept not in `CONTEXT.md`, call `domain-modeling`
   (or `grilling` first if the concept itself is still fuzzy) before
   writing code that uses an ad hoc name for it.
5. **Record architectural decisions** that a future change might
   otherwise re-litigate as an ADR in `docs/adr/` (numbered,
   `NNNN-short-title.md`, following `0001`'s shape: context, options
   considered, consequences).
6. **Review before considering it done**: call the `code-review` skill.
   It runs two independent, fresh-context parallel subagents — Standards
   (repo conventions + the fixed Fowler smell baseline) and Spec (does it
   match what was asked) — and reports them side by side, un-merged.
   Don't skip this because the diff feels small; the eval-loop fix in
   `33b3965` used this on every sub-change and it caught things a single
   pass missed.
7. **Verify against the evaluation suite** if the change touches the
   Planner, Worker, Reviewer, Doc Retriever, or any tool routing/prompt:
   call `run-and-triage-evaluation`. This is a real-API-cost operation
   (subprocess calls to the live assistant) — run the smoke dataset while
   iterating, and confirm with the user before a full run.
8. **Run the full test suite** (`uv run pytest`) before calling anything
   closed.

## Which skill to start with

| Situation | Skill |
|---|---|
| New HTTP endpoint or `AssistantRuntime` method | `add-api-endpoint` |
| New LangGraph pipeline stage (planner/worker/reviewer-style node) | `add-langgraph-agent-node` |
| New Tool the Worker can invoke | `add-rag-tool` |
| Eval suite failed, or you want to know what a failure category means | `run-and-triage-evaluation` |
| Something is broken/throwing/slow and the cause isn't obvious | `diagnosing-bugs` |
| Building a feature or fixing a bug test-first | `tdd` |
| Reviewing a diff (branch, PR, or "review since X") | `code-review` |
| Domain terminology is unclear, or `CONTEXT.md`/an ADR needs writing | `domain-modeling` (interview first via `grilling` if the idea itself is still unsettled) |
| A module feels shallow, hard to test, or keeps causing shotgun-surgery edits | `improve-codebase-architecture` (scan) → `codebase-design` (vocabulary) → `grilling` (work the redesign) |
| Resolving an in-progress merge/rebase conflict | `resolving-merge-conflicts` |
| Something needs researching against primary sources before deciding | `research` |
| Creating or editing a skill, or writing agent-facing docs | `writing-for-agents` |

Each project-specific skill's own "When to Use" section cross-references
the others (e.g. `add-api-endpoint` defers to `add-rag-tool` for new
Tools, not new endpoints) — when unsure, read that section rather than
guessing from the table alone.

## Non-negotiables carried forward from the foundation pass

- **No module-level `llm = get_llm()`.** Call it inside the function.
  This exact anti-pattern has caused a dead-code bug and a pytest
  collection crash twice (`worker.py`, then `planner.py`/`reviewer.py`);
  every scaffolding skill for LLM-calling code should be read with this
  in mind even where not restated explicitly.
- **Routes stay thin.** `app/api/routes/*.py` extracts
  `app.state.runtime`, calls one runtime method, translates the
  result/exception, and does no orchestration — orchestration always
  lives in `AssistantRuntime`.
- **Tools stay collapsed behind one public function.** Multi-step
  internals are private `_`-prefixed helpers, not sibling public
  functions (see `doc_retriever.py`'s collapsed-seam shape).
- **New tools must be added to `ToolDecision.tool`'s Literal type** and
  to the registry's `invoke()` adapter — both are easy to miss and have
  been flagged as a pitfall in `add-rag-tool`.
- **Skills live in the repo, not in a machine-local store.** Project
  skills go in `.agents/skills/`, git-tracked, so they travel with the
  code — not in a tool's local project-memory directory (this was
  corrected once already; see `5ef3c4f`).

## What "done" means for a change

A change is closed when: the plan was approved before implementation
started (unless it qualified for the trivial-fix exception), the full
test suite passes, `code-review`'s two axes report no unresolved hard
violations, any new domain concept is in `CONTEXT.md`, any real
architectural decision is in `docs/adr/`, and — if the change touches
assistant behavior — the evaluation suite (smoke at minimum) confirms no
regression.

## Updating this doc

This doc itself should be treated as agent-facing: if the workflow
changes, read `writing-for-agents` before editing it, and update the
table above rather than letting it drift out of sync with what
`.agents/skills/` actually contains.
