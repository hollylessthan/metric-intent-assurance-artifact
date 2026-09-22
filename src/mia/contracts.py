from __future__ import annotations

import json
import math
from datetime import date
from typing import Any


class ContractError(ValueError):
    """An external payload does not satisfy the frozen Phase 3 contract."""


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError(f"{path} must be an object")
    return value


def _closed(value: dict[str, Any], required: set[str], allowed: set[str], path: str) -> None:
    missing = required - set(value)
    extra = set(value) - allowed
    if missing:
        raise ContractError(f"{path} is missing required fields: {sorted(missing)}")
    if extra:
        raise ContractError(f"{path} contains unknown fields: {sorted(extra)}")


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise ContractError(f"{path} must be a non-empty string")
    return value


def _strings(value: Any, path: str, *, unique: bool = False) -> list[str]:
    if not isinstance(value, list):
        raise ContractError(f"{path} must be an array")
    result = [_string(item, f"{path}[{index}]") for index, item in enumerate(value)]
    if unique and len(result) != len(set(result)):
        raise ContractError(f"{path} must contain unique values")
    return result


def _iso_date(value: Any, path: str) -> str:
    text = _string(value, path)
    try:
        date.fromisoformat(text)
    except ValueError as exc:
        raise ContractError(f"{path} must be an ISO date") from exc
    return text


def validate_context_payload(value: Any) -> None:
    value = _object(value, "context")
    _closed(value, {"role"}, {"role", "org_scope", "calendar_default", "timezone"}, "context")
    _string(value["role"], "context.role")
    if "org_scope" in value:
        _strings(value["org_scope"], "context.org_scope", unique=True)
    if value.get("calendar_default") is not None:
        _string(value["calendar_default"], "context.calendar_default")
    if "timezone" in value:
        _string(value["timezone"], "context.timezone")


def validate_intent_payload(value: Any) -> None:
    value = _object(value, "intent")
    fields = {
        "metrics", "dimensions", "filters", "time", "output_grain", "comparison", "ordering", "limit",
        "version_policy", "metric_versions", "subject_scope", "provenance",
    }
    _closed(value, fields, fields, "intent")
    metrics = _strings(value["metrics"], "intent.metrics", unique=True)
    if not metrics:
        raise ContractError("intent.metrics must not be empty")
    _strings(value["dimensions"], "intent.dimensions", unique=True)
    _strings(value["provenance"], "intent.provenance", unique=True)

    filters = value["filters"]
    if not isinstance(filters, list):
        raise ContractError("intent.filters must be an array")
    filter_fields = {"attribute", "operator", "value", "value_type", "scope"}
    operators = {"eq", "neq", "gt", "gte", "lt", "lte", "in", "not_in"}
    value_types = {"string", "number", "integer", "boolean", "date"}
    for index, item in enumerate(filters):
        item = _object(item, f"intent.filters[{index}]")
        _closed(item, filter_fields, filter_fields, f"intent.filters[{index}]")
        _string(item["attribute"], f"intent.filters[{index}].attribute")
        if item["operator"] not in operators:
            raise ContractError(f"intent.filters[{index}].operator is invalid")
        if item["value_type"] not in value_types:
            raise ContractError(f"intent.filters[{index}].value_type is invalid")
        _string(item["scope"], f"intent.filters[{index}].scope")

    time = _object(value["time"], "intent.time")
    time_fields = {"start", "end", "calendar_id", "temporal_grain", "completeness", "timezone"}
    _closed(time, time_fields, time_fields, "intent.time")
    _iso_date(time["start"], "intent.time.start")
    _iso_date(time["end"], "intent.time.end")
    _string(time["calendar_id"], "intent.time.calendar_id")
    if time["temporal_grain"] not in {"day", "week", "month", "quarter", "year"}:
        raise ContractError("intent.time.temporal_grain is invalid")
    _string(time["completeness"], "intent.time.completeness")
    _string(time["timezone"], "intent.time.timezone")

    grain = _object(value["output_grain"], "intent.output_grain")
    _closed(grain, {"entity", "temporal"}, {"entity", "temporal"}, "intent.output_grain")
    _string(grain["entity"], "intent.output_grain.entity")
    _string(grain["temporal"], "intent.output_grain.temporal")
    if value["comparison"] is not None and not isinstance(value["comparison"], dict):
        raise ContractError("intent.comparison must be an object or null")

    ordering = value["ordering"]
    if not isinstance(ordering, list):
        raise ContractError("intent.ordering must be an array")
    for index, item in enumerate(ordering):
        item = _object(item, f"intent.ordering[{index}]")
        _closed(item, {"key", "direction"}, {"key", "direction"}, f"intent.ordering[{index}]")
        _string(item["key"], f"intent.ordering[{index}].key")
        if item["direction"] not in {"asc", "desc"}:
            raise ContractError(f"intent.ordering[{index}].direction is invalid")

    limit = value["limit"]
    if limit is not None and (not isinstance(limit, int) or isinstance(limit, bool) or limit < 1):
        raise ContractError("intent.limit must be a positive integer or null")
    if value["version_policy"] not in {"effective_time", "restated", "explicit"}:
        raise ContractError("intent.version_policy is invalid")
    versions = _object(value["metric_versions"], "intent.metric_versions")
    for metric_id, version_id in versions.items():
        _string(metric_id, "intent.metric_versions key")
        _string(version_id, f"intent.metric_versions.{metric_id}")
    _object(value["subject_scope"], "intent.subject_scope")


def validate_candidate_payload(value: Any) -> None:
    value = _object(value, "candidate")
    _closed(value, {"intent", "support"}, {"intent", "support", "evidence"}, "candidate")
    validate_intent_payload(value["intent"])
    support = value["support"]
    if not isinstance(support, (int, float)) or isinstance(support, bool) or not math.isfinite(support) or not 0 <= support <= 1:
        raise ContractError("candidate.support must be a finite number between 0 and 1")
    if "evidence" in value:
        _strings(value["evidence"], "candidate.evidence", unique=True)


def validate_registry_payload(value: Any) -> None:
    value = _object(value, "registry")
    top = {"registry_id", "snapshot_version", "snapshot_hash", "metrics", "dimensions", "calendars", "entity_paths", "policies"}
    _closed(value, top - {"snapshot_hash"}, top, "registry")
    _string(value["registry_id"], "registry.registry_id")
    _string(value["snapshot_version"], "registry.snapshot_version")
    if "snapshot_hash" in value:
        claimed = _string(value["snapshot_hash"], "registry.snapshot_hash")
        if not claimed.startswith("sha256:") or len(claimed) != 71:
            raise ContractError("registry.snapshot_hash must be a sha256 digest")

    for family in ("metrics", "dimensions", "calendars", "entity_paths", "policies"):
        if not isinstance(value[family], list):
            raise ContractError(f"registry.{family} must be an array")

    metric_fields = {"id", "name", "aliases", "active", "entity", "additivity", "allowed_dimensions", "allowed_grains", "allowed_calendars", "versions"}
    version_fields = {
        "id", "effective_from", "effective_to", "published_at",
        "restated", "default", "backends",
    }
    for index, metric in enumerate(value["metrics"]):
        path = f"registry.metrics[{index}]"
        metric = _object(metric, path)
        _closed(metric, metric_fields - {"aliases"}, metric_fields, path)
        for field in ("id", "name", "entity"):
            _string(metric[field], f"{path}.{field}")
        if "aliases" in metric:
            _strings(metric["aliases"], f"{path}.aliases")
        if not isinstance(metric["active"], bool):
            raise ContractError(f"{path}.active must be boolean")
        if metric["additivity"] not in {"additive", "semi_additive", "semi_additive_time", "non_additive"}:
            raise ContractError(f"{path}.additivity is invalid")
        for field in ("allowed_dimensions", "allowed_grains", "allowed_calendars"):
            _strings(metric[field], f"{path}.{field}", unique=True)
        if not isinstance(metric["versions"], list) or not metric["versions"]:
            raise ContractError(f"{path}.versions must be a non-empty array")
        for vindex, version in enumerate(metric["versions"]):
            vpath = f"{path}.versions[{vindex}]"
            version = _object(version, vpath)
            _closed(version, {"id", "effective_from", "backends"}, version_fields, vpath)
            _string(version["id"], f"{vpath}.id")
            _iso_date(version["effective_from"], f"{vpath}.effective_from")
            if version.get("effective_to") is not None:
                _iso_date(version["effective_to"], f"{vpath}.effective_to")
            if "restated" in version and not isinstance(version["restated"], bool):
                raise ContractError(f"{vpath}.restated must be boolean")
            if "default" in version and not isinstance(version["default"], bool):
                raise ContractError(f"{vpath}.default must be boolean")
            if version.get("published_at") is not None:
                _iso_date(version["published_at"], f"{vpath}.published_at")
            _object(version["backends"], f"{vpath}.backends")

    dimension_fields = {"id", "name", "type", "entity", "allowed_values", "policy_tags", "backends"}
    for index, dimension in enumerate(value["dimensions"]):
        path = f"registry.dimensions[{index}]"
        dimension = _object(dimension, path)
        _closed(dimension, dimension_fields - {"policy_tags", "allowed_values"}, dimension_fields, path)
        for field in ("id", "name", "entity"):
            _string(dimension[field], f"{path}.{field}")
        if dimension["type"] not in {"string", "number", "integer", "boolean", "date"}:
            raise ContractError(f"{path}.type is invalid")
        if "policy_tags" in dimension:
            _strings(dimension["policy_tags"], f"{path}.policy_tags", unique=True)
        if "allowed_values" in dimension:
            allowed_values = dimension["allowed_values"]
            if not isinstance(allowed_values, list) or not allowed_values:
                raise ContractError(f"{path}.allowed_values must be a non-empty array")
            if any(isinstance(item, (dict, list)) or item is None for item in allowed_values):
                raise ContractError(f"{path}.allowed_values must contain scalar values")
            if len({json.dumps(item, sort_keys=True) for item in allowed_values}) != len(allowed_values):
                raise ContractError(f"{path}.allowed_values must be unique")
        _object(dimension["backends"], f"{path}.backends")

    calendar_fields = {"id", "name", "supported_grains", "completeness_rules", "backends"}
    for index, calendar in enumerate(value["calendars"]):
        path = f"registry.calendars[{index}]"
        calendar = _object(calendar, path)
        _closed(calendar, calendar_fields, calendar_fields, path)
        _string(calendar["id"], f"{path}.id")
        _string(calendar["name"], f"{path}.name")
        _strings(calendar["supported_grains"], f"{path}.supported_grains", unique=True)
        _strings(calendar["completeness_rules"], f"{path}.completeness_rules", unique=True)
        _object(calendar["backends"], f"{path}.backends")

    path_fields = {"id", "from", "to", "allowed", "backends"}
    for index, entity_path in enumerate(value["entity_paths"]):
        path = f"registry.entity_paths[{index}]"
        entity_path = _object(entity_path, path)
        _closed(entity_path, {"id", "from", "to", "allowed"}, path_fields, path)
        for field in ("id", "from", "to"):
            _string(entity_path[field], f"{path}.{field}")
        if not isinstance(entity_path["allowed"], bool):
            raise ContractError(f"{path}.allowed must be boolean")
        if "backends" in entity_path:
            _object(entity_path["backends"], f"{path}.backends")

    policy_fields = {"id", "object_id", "effect", "roles", "org_scopes"}
    for index, policy in enumerate(value["policies"]):
        path = f"registry.policies[{index}]"
        policy = _object(policy, path)
        _closed(policy, {"id", "object_id", "effect"}, policy_fields, path)
        _string(policy["id"], f"{path}.id")
        _string(policy["object_id"], f"{path}.object_id")
        if policy["effect"] not in {"allow", "deny"}:
            raise ContractError(f"{path}.effect is invalid")
        for field in ("roles", "org_scopes"):
            if field in policy:
                _strings(policy[field], f"{path}.{field}", unique=True)
