from __future__ import annotations

from typing import Any

from .base import CompilationResult, UnsupportedIntentError
from .utils import complete_ordering, require_aligned_closed_interval, require_backend_mapping
from ..models import Intent
from ..registry import Registry


class MetricFlowCompiler:
    """Compile canonical intent into the open-source MetricFlow CLI contract."""

    backend = "metricflow"

    def compile(self, intent: Intent, registry: Registry, *, explain: bool = True) -> CompilationResult:
        if intent.comparison is not None:
            raise UnsupportedIntentError("MetricFlow fixture does not yet preserve typed comparison semantics")
        if intent.subject_scope:
            raise UnsupportedIntentError("subject_scope must be lowered to governed filters before MetricFlow compilation")
        if intent.time.get("timezone") != "UTC":
            raise UnsupportedIntentError("MetricFlow fixture only proves UTC-preserving compilation")

        metrics = [registry.metric(metric_id) for metric_id in intent.metrics]
        if any(metric is None for metric in metrics):
            raise UnsupportedIntentError("intent contains an unknown metric")
        metric_map = {metric["id"]: self._metric_name(metric, intent, registry) for metric in metrics if metric}
        if len({metric["entity"] for metric in metrics if metric}) != 1:
            raise UnsupportedIntentError("MetricFlow fixture requires metrics at one governed entity")
        metric_names = list(metric_map.values())

        dimensions = []
        dimension_objects = {}
        for dimension_id in intent.dimensions:
            dimension = registry.dimension(dimension_id)
            if not dimension:
                raise UnsupportedIntentError(f"unknown dimension: {dimension_id}")
            dimension_objects[dimension_id] = dimension
            dimensions.append(require_backend_mapping(registry, dimension, self.backend, "group_by")["group_by"])

        self._validate_entity_grain(intent, metrics, dimension_objects)

        calendar = registry.calendar(intent.time["calendar_id"])
        if not calendar:
            raise UnsupportedIntentError("MetricFlow compilation requires a registered calendar")
        calendar_mapping = require_backend_mapping(registry, calendar, self.backend, "executable", "time_grains")
        if not calendar_mapping["executable"]:
            raise UnsupportedIntentError("calendar is valid canonically but not executable on the MetricFlow fixture")
        time_group_by = calendar_mapping.get("time_grains", {}).get(intent.output_grain["temporal"])
        if not time_group_by:
            raise UnsupportedIntentError("calendar has no MetricFlow mapping for requested temporal grain")
        require_aligned_closed_interval(intent.time, intent.output_grain["temporal"])
        group_by = [time_group_by, *dimensions]

        where = [self._predicate(predicate, registry) for predicate in intent.filters]
        command: list[str] = ["mf", "query", "--metrics", ",".join(metric_names), "--group-by", ",".join(group_by)]
        if where:
            command += ["--where", " and ".join(f"({part})" for part in where)]
        command += ["--start-time", intent.time["start"], "--end-time", intent.time["end"]]

        ordering = complete_ordering(intent)
        order_by = [self._order(order, registry, metric_map, time_group_by) for order in ordering]
        if order_by:
            # Pinned open-source dbt-metricflow 0.13 exposes this as --order.
            command += ["--order", ",".join(order_by)]
        if intent.limit is not None:
            command += ["--limit", str(intent.limit)]
        if explain:
            command.append("--explain")

        return CompilationResult(
            backend=self.backend,
            artifact=tuple(command),
            registry_hash=registry.snapshot_hash,
            intent_hash=intent.equivalence_key,
            audit_hash=intent.audit_hash,
            capabilities={
                "metrics": True,
                "dimensions": True,
                "filters": True,
                "time": True,
                "grain": True,
                "ordering_limit": True,
                "version": True,
                "comparison": intent.comparison is None,
                "subject_scope": not intent.subject_scope,
            },
            metadata={"metrics": metric_names, "metric_map": metric_map, "group_by": group_by, "where": where, "explain": explain,
                      "deterministic_ordering": list(ordering)},
        )

    @staticmethod
    def _validate_entity_grain(intent: Intent, metrics, dimensions) -> None:
        output_entity = intent.output_grain.get("entity")
        grouped_entities = {dimensions[x]["entity"] for x in intent.dimensions if x in dimensions}
        metric_entities = {metric["entity"] for metric in metrics if metric}
        represented = grouped_entities == {output_entity} if intent.dimensions else metric_entities == {output_entity}
        if not represented:
            raise UnsupportedIntentError(
                f"output entity grain {output_entity!r} is not represented by the grouped entity context"
            )

    def _metric_name(self, metric: dict[str, Any], intent: Intent, registry: Registry) -> str:
        version_id = self._version_id(metric, intent)
        version = registry.version(metric, version_id)
        if not version:
            raise UnsupportedIntentError(f"metric version is not mapped: {version_id}")
        return require_backend_mapping(registry, version, self.backend, "metric_name")["metric_name"]

    @staticmethod
    def _version_id(metric: dict[str, Any], intent: Intent) -> str:
        if intent.version_policy == "explicit":
            version_id = intent.metric_versions.get(metric["id"])
            if not version_id:
                raise UnsupportedIntentError(f'{metric["id"]} has no explicit version selection')
            return version_id
        if intent.version_policy == "restated":
            version = next((x for x in metric["versions"] if x.get("restated", False)), None)
            if not version:
                raise UnsupportedIntentError(f'{metric["id"]} has no restated version')
            return version["id"]
        if intent.version_policy != "effective_time":
            raise UnsupportedIntentError(f"unknown version policy: {intent.version_policy}")
        start, end = intent.time["start"], intent.time["end"]
        matches = [
            x for x in metric["versions"]
            if x["effective_from"] <= start and (not x.get("effective_to") or end <= x["effective_to"])
        ]
        if len(matches) > 1:
            defaults = [x for x in matches if x.get("default")]
            if len(defaults) == 1:
                return defaults[0]["id"]
        if len(matches) != 1:
            raise UnsupportedIntentError(f'{metric["id"]} does not resolve to one effective version')
        return matches[0]["id"]

    def _predicate(self, predicate: dict[str, Any], registry: Registry) -> str:
        if predicate.get("scope") != "row":
            raise UnsupportedIntentError("MetricFlow fixture only supports row-scoped predicates")
        dimension = registry.dimension(predicate["attribute"])
        if not dimension:
            raise UnsupportedIntentError(f'unknown filter dimension: {predicate["attribute"]}')
        name = require_backend_mapping(registry, dimension, self.backend, "filter_name")["filter_name"]
        reference = "{{ Dimension('" + name.replace("'", "''") + "') }}"
        operators = {"eq": "=", "neq": "!=", "gt": ">", "gte": ">=", "lt": "<", "lte": "<=", "in": "in", "not_in": "not in"}
        operator = operators.get(predicate["operator"])
        if not operator:
            raise UnsupportedIntentError(f'unsupported MetricFlow filter operator: {predicate["operator"]}')
        value = predicate["value"]
        if predicate["operator"] in {"in", "not_in"}:
            rendered = "(" + ", ".join(self._literal(x) for x in value) + ")"
        else:
            rendered = self._literal(value)
        return f"{reference} {operator} {rendered}"

    @staticmethod
    def _literal(value: Any) -> str:
        if isinstance(value, bool):
            return "True" if value else "False"
        if isinstance(value, (int, float)):
            return str(value)
        return "'" + str(value).replace("'", "''") + "'"

    @staticmethod
    def _order(order: dict[str, str], registry: Registry, metric_map: dict[str, str], time_group_by: str) -> str:
        key = order["key"]
        if key == "metric_time":
            mapped = time_group_by
        elif key in metric_map:
            mapped = metric_map[key]
        else:
            dimension = registry.dimension(key)
            if not dimension:
                raise UnsupportedIntentError(f"unknown order key: {key}")
            mapped = require_backend_mapping(registry, dimension, "metricflow", "group_by")["group_by"]
        return ("-" if order.get("direction", "asc") == "desc" else "") + mapped
