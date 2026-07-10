from datetime import datetime
from typing import Any

def serialize_value(value: Any) -> Any:
    """Recursively convert datetime objects to ISO 8601 strings for JSON serialization."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: serialize_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [serialize_value(item) for item in value]
    return value

def calculate_duration_ms(started_at, ended_at) -> float:
    """Calculate the duration in milliseconds between two datetime objects."""
    return (ended_at - started_at).total_seconds() * 1000
