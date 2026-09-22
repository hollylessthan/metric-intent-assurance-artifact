from __future__ import annotations

from typing import Any

from .base import CompilationResult, UnsupportedIntentError
from .utils import complete_ordering, quote_identifier, quote_literal, require_aligned_closed_interval, require_backend_mapping
from ..models import Intent
from ..registry import Registry


class DuckDBCompiler:
    """Independent executable reference target; never silently drops an intent field."""

    backend = "duckdb"

    def compile(self, intent: Intent, registry: Registry) -> CompilationResult:
        if intent.comparison is not None:
            raise UnsupportedIntentError("DuckDB reference compiler does not yet preserve typed comparisons")
        if intent.subject_scope:
            raise UnsupportedIntentError("subject_scope must be lowered to governed filters before DuckDB compilation")
        if intent.time.get("timezone") != "UTC":
            raise UnsupportedIntentError("DuckDB fixture only proves UTC-preserving compilation")
        calendar = registry.calendar(intent.time["calendar_id"])
        if not calendar:
            raise UnsupportedIntentError("DuckDB compilation requires a registered calendar")
        calendar_mapping = require_backend_mapping(registry, calendar, self.backend, "executable")
        if not calendar_mapping["executable"]:
            raise UnsupportedIntentError("calendar is valid canonically but not executable on the DuckDB fixture")

        metrics = [registry.metric(metric_id) for metric_id in intent.metrics]
        if any(metric is None for metric in metrics):
            raise UnsupportedIntentError("intent contains an unknown metric")
        sources = [self._source(metric, intent, registry) for metric in metrics if metric]
        metric_entities = {metric["entity"] for metric in metrics if metric}
        if len(metric_entities) != 1:
            raise UnsupportedIntentError("reference compiler requires metrics at one governed entity")
        tables = {source["table"] for source in sources}
        time_columns = {source["time_column"] for source in sources}
        if len(tables) != 1 or len(time_columns) != 1:
            raise UnsupportedIntentError("reference compiler requires one table and one governed time column")
        table, time_column = tables.pop(), time_columns.pop()

        dimensions = []
        joins: dict[str, str] = {}
        referenced_dimension_ids = list(dict.fromkeys([
            *intent.dimensions,
            *(predicate["attribute"] for predicate in intent.filters),
        ]))
        referenced_dimensions: dict[str, dict[str, Any]] = {}
        for dimension_id in referenced_dimension_ids:
            dimension = registry.dimension(dimension_id)
            if not dimension:
                raise UnsupportedIntentError(f"unknown dimension: {dimension_id}")
            referenced_dimensions[dimension_id] = dimension
            mapping = require_backend_mapping(registry, dimension, self.backend, "column")
            dimension_table = mapping.get("table", table)
            if dimension_id in intent.dimensions:
                dimensions.append((dimension_id, dimension_table, mapping["column"]))
            if dimension_table != table:
                path = registry.entity_path(metrics[0]["entity"], dimension["entity"])
                path_mapping = require_backend_mapping(
                    registry, path, self.backend, "from_table", "to_table", "from_key", "to_key"
                ) if path else None
                if not path_mapping or path_mapping["from_table"] != table or path_mapping["to_table"] != dimension_table:
                    raise UnsupportedIntentError(f"no semantics-preserving DuckDB join for dimension: {dimension_id}")
                joins[dimension_table] = (
                    f'JOIN {quote_identifier(dimension_table)} ON '
                    f'{quote_identifier(table)}.{quote_identifier(path_mapping["from_key"])} = '
                    f'{quote_identifier(dimension_table)}.{quote_identifier(path_mapping["to_key"])}'
                )

        self._validate_entity_grain(intent, metrics, referenced_dimensions)

        temporal = intent.output_grain["temporal"]
        if temporal not in {"day", "week", "month", "quarter", "year"}:
            raise UnsupportedIntentError(f"unsupported DuckDB temporal grain: {temporal}")
        require_aligned_closed_interval(intent.time, temporal)
        qualified_time = f'{quote_identifier(table)}.{quote_identifier(time_column)}'
        time_expr = f"date_trunc('{temporal}', {qualified_time})"
        select = [f'{time_expr} AS {quote_identifier("metric_time") }']
        select += [f'{quote_identifier(dimension_table)}.{quote_identifier(column)} AS {quote_identifier(dimension_id)}'
                   for dimension_id, dimension_table, column in dimensions]
        select += [
            f'{source["aggregation"]}({quote_identifier(table)}.{quote_identifier(source["column"])}) AS {quote_identifier(metric["id"])}'
            for metric, source in zip(metrics, sources)
            if metric
        ]

        where = [
            f'{qualified_time} >= {quote_literal(intent.time["start"])}',
            f'{qualified_time} <= {quote_literal(intent.time["end"])}',
        ]
        where += [self._predicate(predicate, registry, table) for predicate in intent.filters]
        sql = f'SELECT {", ".join(select)} FROM {quote_identifier(table)}'
        if joins:
            sql += " " + " ".join(joins.values())
        sql += f' WHERE {" AND ".join(where)}'
        group_by = [time_expr, *[f'{quote_identifier(t)}.{quote_identifier(c)}' for _, t, c in dimensions]]
        sql += " GROUP BY " + ", ".join(group_by)
        ordering = complete_ordering(intent)
        if ordering:
            sql += " ORDER BY " + ", ".join(self._order(order, registry) for order in ordering)
        if intent.limit is not None:
            sql += f" LIMIT {intent.limit}"

        return CompilationResult(
            backend=self.backend,
            artifact=sql,
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
            metadata={"table": table, "time_column": time_column, "joins": sorted(joins),
                      "deterministic_ordering": list(ordering)},
        )

    @staticmethod
    def _validate_entity_grain(
        intent: Intent,
        metrics: list[dict[str, Any] | None],
        dimensions: dict[str, dict[str, Any]],
    ) -> None:
        output_entity = intent.output_grain.get("entity")
        grouped_entities = {dimensions[x]["entity"] for x in intent.dimensions if x in dimensions}
        metric_entities = {metric["entity"] for metric in metrics if metric}
        represented = grouped_entities == {output_entity} if intent.dimensions else metric_entities == {output_entity}
        if not represented:
            raise UnsupportedIntentError(
                f"output entity grain {output_entity!r} is not represented by the grouped entity context"
            )

    def _source(self, metric: dict[str, Any], intent: Intent, registry: Registry) -> dict[str, Any]:
        version_id = MetricVersionResolver.resolve(metric, intent)
        version = registry.version(metric, version_id)
        if not version:
            raise UnsupportedIntentError(f"metric version is not mapped: {version_id}")
        return require_backend_mapping(
            registry, version, self.backend, "table", "column", "aggregation", "time_column"
        )

    def _predicate(self, predicate: dict[str, Any], registry: Registry, base_table: str) -> str:
        if predicate.get("scope") != "row":
            raise UnsupportedIntentError("DuckDB fixture only supports row-scoped predicates")
        dimension = registry.dimension(predicate["attribute"])
        if not dimension:
            raise UnsupportedIntentError(f'unknown filter dimension: {predicate["attribute"]}')
        mapping = require_backend_mapping(registry, dimension, self.backend, "column")
        column = f'{quote_identifier(mapping.get("table", base_table))}.{quote_identifier(mapping["column"])}'
        operators = {"eq": "=", "neq": "!=", "gt": ">", "gte": ">=", "lt": "<", "lte": "<=", "in": "IN", "not_in": "NOT IN"}
        operator = operators.get(predicate["operator"])
        if not operator:
            raise UnsupportedIntentError(f'unsupported DuckDB filter operator: {predicate["operator"]}')
        value = predicate["value"]
        if predicate["operator"] in {"in", "not_in"}:
            rendered = "(" + ", ".join(quote_literal(x) for x in value) + ")"
        else:
            rendered = quote_literal(value)
        return f"{column} {operator} {rendered}"

    @staticmethod
    def _order(order: dict[str, str], registry: Registry) -> str:
        key = order["key"]
        if key == "metric_time" or registry.metric(key):
            column = key
        else:
            dimension = registry.dimension(key)
            if not dimension:
                raise UnsupportedIntentError(f"unknown order key: {key}")
            column = key
        direction = "DESC" if order.get("direction", "asc") == "desc" else "ASC"
        return f"{quote_identifier(column)} {direction}"


class MetricVersionResolver:
    @staticmethod
    def resolve(metric: dict[str, Any], intent: Intent) -> str:
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
        matches = [x for x in metric["versions"] if x["effective_from"] <= start and (not x.get("effective_to") or end <= x["effective_to"])]
        if len(matches) > 1:
            defaults = [x for x in matches if x.get("default")]
            if len(defaults) == 1:
                return defaults[0]["id"]
        if len(matches) != 1:
            raise UnsupportedIntentError(f'{metric["id"]} does not resolve to one effective version')
        return matches[0]["id"]
