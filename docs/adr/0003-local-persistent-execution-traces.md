# ADR 0003: Local persistent execution traces

**Status:** Accepted

## Context

The REST API needs to return a compact answer from `POST /ask` while allowing
operators to inspect the full execution trace later, including traces for
workflow-stage failures. An in-memory store would lose traces on restart, while
a shared database or hosted trace service is outside this local integration's
scope. Traces contain questions, answers, retrieved content, and stage
snapshots, so persistence and exposure must remain bounded.

## Decision

Persist successful and workflow-stage-failure traces in a local SQLite database
at `data/traces/execution_traces.sqlite3`. Expose retrieval through
`GET /trace/{trace_id}` and retain records for seven days; expired records are
not returned and are pruned on subsequent writes. The API remains unauthenticated
and is intended for trusted local/internal use only, bound to loopback for local
development by the documented startup command.

## Consequences

- A trace remains available across process restarts until its retention period
  expires.
- Trace IDs are primary keys; reusing a caller-supplied ID replaces its prior
  trace, so callers should use unique IDs.
- The trace endpoint returns full content, so the API must not be exposed to
  public or untrusted networks.
- SQLite is a single-process/local-storage choice, not a production shared
  datastore or a multi-instance consistency mechanism.
- Retention bounds storage duration but is not a substitute for access control,
  encryption, or a data-classification policy.
