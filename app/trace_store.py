import json
import sqlite3
from contextlib import contextmanager
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from app.contracts.trace import ExecutionTrace

_RETENTION = timedelta(days=7)
_DEFAULT_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "traces"
    / "execution_traces.sqlite3"
)


class TraceStore:
    """Persist full execution traces locally for a bounded retention period."""

    def __init__(
        self,
        path: str | Path | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._path = Path(path) if path is not None else _DEFAULT_PATH
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def save(self, trace: ExecutionTrace) -> None:
        now = self._now()
        created_at = now.isoformat()
        with self._connection() as connection:
            connection.execute(
                "DELETE FROM execution_traces WHERE created_at < ?",
                ((now - _RETENTION).isoformat(),),
            )
            connection.execute(
                """
                INSERT INTO execution_traces (trace_id, created_at, trace_json)
                VALUES (?, ?, ?)
                ON CONFLICT(trace_id) DO UPDATE SET
                    created_at = excluded.created_at,
                    trace_json = excluded.trace_json
                """,
                (trace.trace_id, created_at, json.dumps(trace.to_dict())),
            )

    def get(self, trace_id: str) -> dict[str, Any] | None:
        now = self._now()
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT trace_json FROM execution_traces
                WHERE trace_id = ? AND created_at >= ?
                """,
                (trace_id, (now - _RETENTION).isoformat()),
            ).fetchone()
        return json.loads(row[0]) if row is not None else None

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _connect(self) -> sqlite3.Connection:
        self._path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        connection = sqlite3.connect(self._path, timeout=30)
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS execution_traces (
                trace_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                trace_json TEXT NOT NULL
            )
            """
        )
        return connection

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None:
            return now.replace(tzinfo=timezone.utc)
        return now.astimezone(timezone.utc)
