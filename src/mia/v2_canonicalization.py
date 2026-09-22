from __future__ import annotations

from datetime import date
from typing import Any

from .models import Context, Intent
from .registry import Registry


class MixedEntityGrouping(ValueError):
    """Raised when v2 canonicalization reaches a grouping the v1 intent cannot encode."""


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def _resolve_effective_version(metric: dict[str, Any], start: str, end: str) -> str | None:
    start_date = _parse_date(start)
    end_date = _parse_date(end)
    if not start_date or not end_date:
        return None

    matches = []
    for version in metric.get("versions", []):
        effective_from = _parse_date(version.get("effective_from"))
        effective_to = _parse_date(version.get("effective_to"))
        if effective_from and effective_from <= start_date and (
            effective_to is None or end_date <= effective_to
        ):
            matches.append(version)

    if len(matches) == 1:
        return matches[0]["id"]
    originals = [item for item in matches if not item.get("restated", False)]
    if len(matches) > 1 and len(originals) == 1:
        return originals[0]["id"]
    return None


def canonicalize_model_intent_v2(
    payload: dict[str, Any],
    *,
    registry: Registry,
    context: Context,
) -> Intent:
    """Convert the smaller v2 model-facing intent into the existing canonical Intent.

    MIA-v1 classes/schemas/validators remain unchanged. This adapter derives
    structural fields that the model should not independently invent.
    """
    metrics = list(payload.get("metrics", []))
    dimensions = list(payload.get("dimensions", []))
    filters = list(payload.get("filters", []))
    time_value = dict(payload.get("time", {}))

    metric_objects = [registry.metric(metric_id) for metric_id in metrics]
    dimension_objects = [registry.dimension(dimension_id) for dimension_id in dimensions]
    if any(item is None for item in metric_objects):
        raise ValueError("cannot canonicalize unknown metric id")
    if any(item is None for item in dimension_objects):
        raise ValueError("cannot canonicalize unknown dimension id")

    # The frozen v1 Intent schema requires a string calendar_id, while the
    # validator already treats a falsey calendar_id plus no context default as
    # CLR_CALENDAR. Use the empty-string sentinel only inside this compatibility
    # adapter so an unresolved calendar reaches deterministic assurance instead
    # of becoming a parser/runtime failure.
    calendar_id = time_value.get("calendar_id") or context.calendar_default or ""

    temporal_grain = time_value["temporal_grain"]

    if dimensions:
        grouped_entities = sorted({item["entity"] for item in dimension_objects if item})
        if len(grouped_entities) != 1:
            raise MixedEntityGrouping(
                "mixed-entity grouping requires the v2 semantic-compiler capability path"
            )
        output_entity = grouped_entities[0]
    else:
        metric_entities = sorted({item["entity"] for item in metric_objects if item})
        if len(metric_entities) != 1:
            raise MixedEntityGrouping(
                "multi-entity metric output requires the v2 semantic-compiler capability path"
            )
        output_entity = metric_entities[0]

    explicit_versions = dict(payload.get("explicit_metric_versions", {}))
    unresolved_explicit_versions = set(payload.get("unresolved_explicit_version_metrics", ()))
    # Empty-string version ids are an internal compatibility sentinel. The
    # frozen validator maps them to CLR_VERSION_POLICY for explicit requests
    # whose named definition is unresolved.
    for metric_id in unresolved_explicit_versions:
        explicit_versions[metric_id] = ""
    version_policy = "explicit" if explicit_versions else "effective_time"

    provenance = set(metrics) | set(dimensions)
    provenance |= {
        item["attribute"]
        for item in filters
        if item.get("attribute")
    }
    if calendar_id:
        provenance.add(calendar_id)

    if explicit_versions:
        provenance |= {version_id for version_id in explicit_versions.values() if version_id}
    else:
        for metric in metric_objects:
            assert metric is not None
            resolved = _resolve_effective_version(
                metric,
                time_value["start"],
                time_value["end"],
            )
            if resolved:
                provenance.add(resolved)

    canonical = {
        "metrics": metrics,
        "dimensions": dimensions,
        "filters": filters,
        "time": {
            "start": time_value["start"],
            "end": time_value["end"],
            "calendar_id": calendar_id,
            "temporal_grain": temporal_grain,
            "completeness": "closed",
            "timezone": context.timezone,
        },
        "output_grain": {
            "entity": output_entity,
            "temporal": temporal_grain,
        },
        "comparison": None,
        "ordering": list(payload.get("ordering", [])),
        "limit": payload.get("limit"),
        "version_policy": version_policy,
        "metric_versions": explicit_versions,
        "subject_scope": {},
        "provenance": sorted(provenance),
    }
    return Intent.from_dict(canonical)
