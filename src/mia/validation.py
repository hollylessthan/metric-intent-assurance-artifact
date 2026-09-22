from __future__ import annotations

from datetime import date
from typing import Any

from .models import Action, Context, Intent, Violation
from .registry import Registry


def _violation(family: str, code: str, message: str, action: Action, *object_ids: str) -> Violation:
    return Violation(family, code, message, action, tuple(x for x in object_ids if x))


def _parse_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        return None


def _type_matches(value: Any, declared: str) -> bool:
    if declared == "string":
        return isinstance(value, str)
    if declared == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if declared == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if declared == "boolean":
        return isinstance(value, bool)
    if declared == "date":
        return _parse_date(value) is not None
    return False


class Validator:
    """Deterministic implementation of the frozen Phase 2 validity contract."""

    def validate(self, intent: Intent, registry: Registry, context: Context) -> tuple[Violation, ...]:
        failures: list[Violation] = []
        metric_pairs = [(mid, registry.metric(mid)) for mid in intent.metrics]
        missing_metrics = [mid for mid, metric in metric_pairs if metric is None]
        if missing_metrics:
            failures.append(
                _violation(
                    "metric_identity",
                    "GAP_METRIC",
                    "Requested governed metric is absent from the registry",
                    Action.COVERAGE_GAP,
                    *missing_metrics,
                )
            )
        metrics = [metric for _, metric in metric_pairs if metric is not None]
        if not metrics:
            return tuple(failures)

        start_raw, end_raw = intent.time.get("start"), intent.time.get("end")
        start, end = _parse_date(start_raw), _parse_date(end_raw)
        if not start_raw or not end_raw:
            failures.append(_violation("time", "CLR_TIME_RANGE", "Time interval is unresolved", Action.CLARIFY))
        elif not start or not end or start > end:
            failures.append(_violation("time", "REJ_TIME_INVALID", "Time interval is invalid", Action.REJECT))

        calendar_id = intent.time.get("calendar_id") or context.calendar_default
        calendar = registry.calendar(calendar_id) if calendar_id else None
        if not calendar_id:
            failures.append(_violation("time", "CLR_CALENDAR", "Calendar is unresolved", Action.CLARIFY))
        elif calendar is None:
            failures.append(
                _violation(
                    "time", "GAP_CALENDAR_RULE", "Requested calendar is not registered", Action.COVERAGE_GAP, calendar_id
                )
            )

        temporal_grain = intent.output_grain.get("temporal") or intent.time.get("temporal_grain")
        if not temporal_grain:
            failures.append(_violation("grain", "CLR_GRAIN", "Temporal grain is unresolved", Action.CLARIFY))
        elif intent.time.get("temporal_grain") and intent.time["temporal_grain"] != temporal_grain:
            failures.append(
                _violation(
                    "grain", "REJ_GRAIN_ADDITIVITY", "Time and output grains disagree", Action.REJECT, temporal_grain
                )
            )

        if calendar and temporal_grain not in calendar.get("supported_grains", []):
            failures.append(
                _violation(
                    "time",
                    "GAP_CALENDAR_RULE",
                    "Calendar does not define the requested grain",
                    Action.COVERAGE_GAP,
                    calendar_id,
                )
            )
        completeness = intent.time.get("completeness")
        if calendar and completeness not in calendar.get("completeness_rules", []):
            failures.append(
                _violation(
                    "time",
                    "GAP_CALENDAR_RULE",
                    "Calendar completeness rule is unavailable",
                    Action.COVERAGE_GAP,
                    calendar_id,
                )
            )

        referenced_dimensions = list(intent.dimensions) + [x.get("attribute") for x in intent.filters]
        dimensions: dict[str, dict[str, Any]] = {}
        for dimension_id in dict.fromkeys(x for x in referenced_dimensions if x):
            dimension = registry.dimension(dimension_id)
            if not dimension:
                code = "GAP_FILTER_CONCEPT" if dimension_id in [x.get("attribute") for x in intent.filters] else "GAP_DIMENSION"
                failures.append(
                    _violation("dimension", code, "Requested dimension is not registered", Action.COVERAGE_GAP, dimension_id)
                )
                continue
            dimensions[dimension_id] = dimension
            incompatible = [m["id"] for m in metrics if dimension_id not in m.get("allowed_dimensions", [])]
            if incompatible:
                failures.append(
                    _violation(
                        "compatibility",
                        "REJ_DIMENSION_INCOMPATIBLE",
                        "Dimension is explicitly incompatible with metric",
                        Action.REJECT,
                        dimension_id,
                        *incompatible,
                    )
                )
            for metric in metrics:
                path = registry.entity_path(metric["entity"], dimension["entity"])
                if path is None:
                    failures.append(
                        _violation(
                            "entity_path",
                            "GAP_ENTITY_RELATION",
                            "Required entity relationship is not modeled",
                            Action.COVERAGE_GAP,
                            metric["entity"],
                            dimension["entity"],
                        )
                    )
                elif not path.get("allowed", False):
                    failures.append(
                        _violation(
                            "entity_path",
                            "REJ_ENTITY_PATH",
                            "Entity relationship is prohibited",
                            Action.REJECT,
                            metric["entity"],
                            dimension["entity"],
                        )
                    )

        supported_operators = {"eq", "neq", "gt", "gte", "lt", "lte", "in", "not_in"}
        for predicate in intent.filters:
            dimension = dimensions.get(predicate.get("attribute"))
            if not dimension:
                continue
            operator = predicate.get("operator")
            if operator not in supported_operators:
                failures.append(
                    _violation(
                        "compatibility",
                        "REJ_OPERATION_INVALID",
                        "Filter operator is outside the governed contract",
                        Action.REJECT,
                        str(operator),
                    )
                )
            declared_type = predicate.get("value_type")
            expected_type = dimension.get("type")
            value = predicate.get("value")
            typed_value = value
            if operator in {"in", "not_in"}:
                if not isinstance(value, list) or not value:
                    typed_value = None
                elif all(_type_matches(item, expected_type) for item in value):
                    typed_value = value[0]
                else:
                    typed_value = None
            if declared_type != expected_type or typed_value is None or not _type_matches(typed_value, expected_type):
                failures.append(
                    _violation(
                        "compatibility",
                        "REJ_OPERATION_INVALID",
                        "Filter value does not match the registered type",
                        Action.REJECT,
                        predicate.get("attribute", ""),
                    )
                )

        resolved_versions: list[str] = []
        requested_version_keys = set(intent.metric_versions)
        metric_ids = set(intent.metrics)
        if requested_version_keys - metric_ids:
            failures.append(
                _violation(
                    "version", "REJ_VERSION_INVALID",
                    "Version map contains an entry for an unrequested metric", Action.REJECT,
                    *sorted(requested_version_keys - metric_ids),
                )
            )
        if intent.version_policy != "explicit" and requested_version_keys:
            failures.append(
                _violation(
                    "version", "REJ_VERSION_INVALID",
                    "Named metric versions are only valid with explicit version policy", Action.REJECT,
                    *sorted(requested_version_keys),
                )
            )
        for metric in metrics:
            if not metric.get("active", True):
                failures.append(
                    _violation(
                        "metric_identity", "GAP_METRIC", "Metric is inactive in this snapshot", Action.COVERAGE_GAP, metric["id"]
                    )
                )
            if calendar_id and calendar_id not in metric.get("allowed_calendars", []):
                failures.append(
                    _violation(
                        "time", "REJ_TIME_INVALID", "Metric does not permit the requested calendar", Action.REJECT, metric["id"], calendar_id
                    )
                )
            if temporal_grain and temporal_grain not in metric.get("allowed_grains", []):
                failures.append(
                    _violation(
                        "grain",
                        "REJ_GRAIN_ADDITIVITY",
                        "Output grain violates metric additivity",
                        Action.REJECT,
                        metric["id"],
                    )
                )
            version = self._resolve_version(intent, metric, start, end, failures)
            if version:
                resolved_versions.append(version["id"])

        self._validate_policies(intent, registry, context, failures)

        output_entity = intent.output_grain.get("entity")
        grouped_entities = {
            dimensions[dimension_id]["entity"]
            for dimension_id in intent.dimensions
            if dimension_id in dimensions
        }
        metric_entities = {metric["entity"] for metric in metrics}
        if not output_entity:
            failures.append(_violation("grain", "CLR_ENTITY_SCOPE", "Output entity is unresolved", Action.CLARIFY))
        elif intent.dimensions and grouped_entities != {output_entity}:
            failures.append(
                _violation(
                    "grain", "REJ_GRAIN_ADDITIVITY",
                    "Output entity must exactly represent the grouped entity context", Action.REJECT, output_entity
                )
            )
        elif not intent.dimensions and metric_entities != {output_entity}:
            failures.append(
                _violation(
                    "grain", "REJ_GRAIN_ADDITIVITY",
                    "Ungrouped output entity must match the metric entity", Action.REJECT, output_entity
                )
            )

        output_order_keys = {"metric_time", *intent.metrics, *intent.dimensions}
        seen_order_keys: set[str] = set()
        for order in intent.ordering:
            key = order.get("key")
            if key not in output_order_keys or key in seen_order_keys:
                failures.append(
                    _violation(
                        "compatibility", "REJ_OPERATION_INVALID",
                        "Ordering must use each output field at most once", Action.REJECT, str(key)
                    )
                )
            seen_order_keys.add(key)

        required_refs = set(intent.metrics) | set(intent.dimensions)
        required_refs |= {x["attribute"] for x in intent.filters if x.get("attribute")}
        required_refs |= set(resolved_versions)
        if calendar_id:
            required_refs.add(calendar_id)
        missing_refs = required_refs - set(intent.provenance)
        if missing_refs:
            failures.append(
                _violation(
                    "provenance",
                    "INT_PROVENANCE",
                    "Registry references required to reproduce the intent are missing",
                    Action.REJECT,
                    *sorted(missing_refs),
                )
            )
        return tuple(self._deduplicate(failures))

    @staticmethod
    def _validate_policies(intent, registry, context, failures):
        """Evaluate ACLs with deny-overrides and disjunctive allow semantics.

        An object with one or more allow policies is authorized when any allow
        matches the context. A matching deny always wins. This avoids the
        accidental conjunction produced by evaluating every allow independently.
        """
        object_ids = set(intent.metrics) | set(intent.dimensions)
        object_ids |= {x.get("attribute") for x in intent.filters if x.get("attribute")}
        policies = registry.data.get("policies", [])
        for object_id in object_ids:
            object_policies = [policy for policy in policies if policy["object_id"] == object_id]
            allows = [policy for policy in object_policies if policy["effect"] == "allow"]
            denies = [policy for policy in object_policies if policy["effect"] == "deny"]
            matching_denies = [policy for policy in denies if Validator._policy_matches(policy, context)]
            matching_allows = [policy for policy in allows if Validator._policy_matches(policy, context)]
            if matching_denies or (allows and not matching_allows):
                evidence = matching_denies or allows
                failures.append(_violation("policy", "REJ_AUTHORIZATION",
                                           "Authorized context does not satisfy registry policy",
                                           Action.REJECT, *(policy["id"] for policy in evidence), object_id))

    @staticmethod
    def _policy_matches(policy, context) -> bool:
        role_match = not policy.get("roles") or context.role in policy["roles"]
        required_scope = set(policy.get("org_scopes", []))
        scope_match = not required_scope or bool(required_scope.intersection(context.org_scope))
        return role_match and scope_match

    def _resolve_version(
        self,
        intent: Intent,
        metric: dict[str, Any],
        start: date | None,
        end: date | None,
        failures: list[Violation],
    ) -> dict[str, Any] | None:
        versions = metric.get("versions", [])
        if intent.version_policy == "explicit":
            version_id = intent.metric_versions.get(metric["id"])
            if not version_id:
                failures.append(
                    _violation(
                        "version", "CLR_VERSION_POLICY", "Explicit version is unresolved", Action.CLARIFY, metric["id"]
                    )
                )
                return None
            version = next((x for x in versions if x["id"] == version_id), None)
            if not version:
                failures.append(
                    _violation(
                        "version", "GAP_VERSION_HISTORY", "Explicit version is unavailable", Action.COVERAGE_GAP, version_id
                    )
                )
            return version
        if intent.version_policy == "restated":
            version = next((x for x in versions if x.get("restated", False)), None)
            if not version:
                failures.append(
                    _violation(
                        "version", "GAP_VERSION_HISTORY", "Restated definition is unavailable", Action.COVERAGE_GAP, metric["id"]
                    )
                )
            return version
        if intent.version_policy != "effective_time":
            failures.append(
                _violation("version", "REJ_VERSION_INVALID", "Unknown version policy", Action.REJECT, intent.version_policy)
            )
            return None
        if not start or not end:
            return None
        matches = []
        for version in versions:
            effective_from = _parse_date(version.get("effective_from"))
            effective_to = _parse_date(version.get("effective_to")) if version.get("effective_to") else None
            if effective_from and effective_from <= start and (not effective_to or end <= effective_to):
                matches.append(version)
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            # A restated variant may deliberately share the original
            # definition's effective interval. Effective-time requests retain
            # the unique original; version_policy="restated" opts into the
            # retrospective variant. Multiple originals remain invalid.
            originals = [version for version in matches if not version.get("restated", False)]
            if len(originals) == 1:
                return originals[0]
        code = "GAP_VERSION_HISTORY" if not versions else "REJ_VERSION_INVALID"
        action = Action.COVERAGE_GAP if not versions else Action.REJECT
        failures.append(
            _violation(
                "version", code, "Interval does not resolve to exactly one governed version", action, metric["id"]
            )
        )
        return None

    @staticmethod
    def _deduplicate(failures: list[Violation]) -> list[Violation]:
        seen: set[tuple[Any, ...]] = set()
        result = []
        for failure in failures:
            key = (failure.family, failure.code, failure.object_ids)
            if key not in seen:
                seen.add(key)
                result.append(failure)
        return result
