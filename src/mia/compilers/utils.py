from calendar import monthrange
from datetime import date

from .base import UnsupportedIntentError


def require_backend_mapping(registry, obj: dict, backend: str, *required: str) -> dict:
    try:
        mapping = registry.backend_mapping(obj, backend)
    except ValueError as exc:
        raise UnsupportedIntentError(str(exc)) from exc
    missing = [key for key in required if key not in mapping]
    if missing:
        raise UnsupportedIntentError(
            f'{obj.get("id", "object")} {backend} mapping lacks required fields: {missing}'
        )
    return mapping


def complete_ordering(intent) -> tuple[dict[str, str], ...]:
    """Validate requested order keys and append deterministic output tie-breakers."""
    output_keys = ("metric_time", *intent.dimensions, *intent.metrics)
    allowed = set(output_keys)
    seen: set[str] = set()
    result: list[dict[str, str]] = []
    for order in intent.ordering:
        key = order["key"]
        if key not in allowed:
            raise UnsupportedIntentError(f"order key is not present in output: {key}")
        if key in seen:
            raise UnsupportedIntentError(f"duplicate order key: {key}")
        seen.add(key)
        result.append(order)
    if result:
        result.extend({"key": key, "direction": "asc"} for key in output_keys if key not in seen)
    return tuple(result)


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def quote_literal(value: object) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def require_aligned_closed_interval(time: dict, temporal_grain: str) -> None:
    """Reject intervals whose lowering differs between MetricFlow and direct SQL."""
    if time.get("completeness") != "closed":
        raise UnsupportedIntentError("compilers only preserve closed interval semantics")
    if time.get("temporal_grain") != temporal_grain:
        raise UnsupportedIntentError("time grain and output grain must agree")
    try:
        start = date.fromisoformat(time["start"])
        end = date.fromisoformat(time["end"])
    except (KeyError, TypeError, ValueError) as exc:
        raise UnsupportedIntentError("compilation requires valid ISO date boundaries") from exc

    if temporal_grain == "day":
        aligned = True
    elif temporal_grain == "week":
        aligned = start.weekday() == 0 and end.weekday() == 6
    elif temporal_grain == "month":
        aligned = start.day == 1 and end.day == monthrange(end.year, end.month)[1]
    elif temporal_grain == "quarter":
        aligned = (
            start.day == 1 and start.month in {1, 4, 7, 10}
            and end.month in {3, 6, 9, 12}
            and end.day == monthrange(end.year, end.month)[1]
        )
    elif temporal_grain == "year":
        aligned = start.month == 1 and start.day == 1 and end.month == 12 and end.day == 31
    else:
        aligned = False
    if not aligned:
        raise UnsupportedIntentError(f"{temporal_grain} interval boundaries are not grain-aligned")
