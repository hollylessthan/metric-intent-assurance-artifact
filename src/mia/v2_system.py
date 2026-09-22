from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .assurance import Assurer
from .contracts import ContractError
from .generation import GAP_CODES, GenerationResult
from .models import Candidate, Context, MissingCapability
from .phase5_systems import BENCHMARK_GOLD_KEYS, canonical_json, gold_key_paths
from .registry import Registry
from .v2_canonicalization import MixedEntityGrouping, canonicalize_model_intent_v2


PROMPT_VERSION = "mia-v2-minimal-v3-semantic-coverage"


def _semantic_intent_wire_schema() -> dict[str, Any]:
    closed = {"type": "object", "additionalProperties": False}
    filter_item = {
        **closed,
        "required": ["attribute", "operator", "value_json", "value_type", "scope"],
        "properties": {
            "attribute": {"type": "string"},
            "operator": {"enum": ["eq", "neq", "gt", "gte", "lt", "lte", "in", "not_in"]},
            "value_json": {"type": "string"},
            "value_type": {"enum": ["string", "number", "integer", "boolean", "date"]},
            "scope": {"type": "string"},
        },
    }
    time = {
        **closed,
        "required": ["start", "end", "temporal_grain", "calendar_id"],
        "properties": {
            "start": {"type": "string"},
            "end": {"type": "string"},
            "temporal_grain": {"enum": ["day", "week", "month", "quarter", "year"]},
            "calendar_id": {"type": ["string", "null"]},
        },
    }
    version = {
        **closed,
        "required": ["metric_id", "version_id"],
        "properties": {
            "metric_id": {"type": "string"},
            "version_id": {"type": "string"},
        },
    }
    ordering = {
        **closed,
        "required": ["key", "direction"],
        "properties": {
            "key": {"type": "string"},
            "direction": {"enum": ["asc", "desc"]},
        },
    }
    return {
        **closed,
        "required": [
            "metrics", "dimensions", "filters", "time",
            "explicit_metric_versions", "unresolved_explicit_version_metrics",
            "unresolved_dimension_mentions", "unresolved_filter_value_attributes",
            "ordering", "limit",
        ],
        "properties": {
            "metrics": {"type": "array", "minItems": 1, "items": {"type": "string"}},
            "dimensions": {"type": "array", "items": {"type": "string"}},
            "filters": {"type": "array", "items": filter_item},
            "time": time,
            "explicit_metric_versions": {"type": "array", "items": version},
            "unresolved_explicit_version_metrics": {
                "type": "array", "items": {"type": "string"}
            },
            "unresolved_dimension_mentions": {
                "type": "array", "items": {"type": "string"}
            },
            "unresolved_filter_value_attributes": {
                "type": "array", "items": {"type": "string"}
            },
            "ordering": {"type": "array", "items": ordering},
            "limit": {"type": ["integer", "null"]},
        },
    }


def output_schema_v2() -> dict[str, Any]:
    closed = {"type": "object", "additionalProperties": False}
    evidence = {"type": "array", "items": {"type": "string"}}
    candidate = {
        **closed,
        "required": ["semantic_intent", "support", "evidence"],
        "properties": {
            "semantic_intent": _semantic_intent_wire_schema(),
            "support": {"type": "number", "minimum": 0, "maximum": 1},
            "evidence": evidence,
        },
    }
    missing = {
        "type": ["object", "null"],
        "additionalProperties": False,
        "required": ["code", "concept", "evidence"],
        "properties": {
            "code": {"enum": sorted(GAP_CODES)},
            "concept": {"type": "string"},
            "evidence": evidence,
        },
    }
    return {
        **closed,
        "required": ["candidates", "missing_capability", "outside_contract"],
        "properties": {
            "candidates": {"type": "array", "maxItems": 3, "items": candidate},
            "missing_capability": missing,
            "outside_contract": {"type": "boolean"},
        },
    }


def prompt_text_v2(prompts_root: str | Path) -> str:
    return (Path(prompts_root) / "mia.txt").read_text(encoding="utf-8")


def build_model_case_v2(input_record: dict[str, Any], registry: Registry) -> dict[str, Any]:
    if leaked := gold_key_paths(input_record, keys=BENCHMARK_GOLD_KEYS):
        raise ValueError(f"gold-bearing input cannot enter a v2 provider request: {leaked[:5]}")
    required = {"request_id", "case_id", "utterance_id", "domain", "request", "context", "registry_hash"}
    if missing := required - set(input_record):
        raise ValueError(f"v2 model input is missing fields: {sorted(missing)}")
    if input_record["registry_hash"] != registry.snapshot_hash:
        raise ValueError("v2 model input and registry snapshot hashes differ")
    result = {
        "request_id": input_record["request_id"],
        "case_id": input_record["case_id"],
        "utterance_id": input_record["utterance_id"],
        "domain": input_record["domain"],
        "request": input_record["request"],
        "context": deepcopy(input_record["context"]),
        "registry_hash": registry.snapshot_hash,
        "registry": deepcopy(registry.data),
    }
    if leaked := gold_key_paths(result, keys=BENCHMARK_GOLD_KEYS):
        raise AssertionError(f"v2 provider request contains a forbidden gold field: {leaked[:5]}")
    return result


def build_adapter_input_v2(
    input_record: dict[str, Any],
    registry: Registry,
    *,
    provider: str,
    model_id: str,
    decoding: dict[str, Any],
    prompts_root: str | Path,
) -> dict[str, Any]:
    return {
        "provider": provider,
        "model_id": model_id,
        "system_id": "mia-v2",
        "prompt_version": PROMPT_VERSION,
        "system_prompt": prompt_text_v2(prompts_root),
        "output_schema": output_schema_v2(),
        "decoding": deepcopy(decoding),
        "case": build_model_case_v2(input_record, registry),
    }


def _decode_json_string(value: Any, path: str) -> Any:
    if not isinstance(value, str):
        raise ValueError(f"{path} must be a JSON string")
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON") from exc


def decode_semantic_intent_wire(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("v2 semantic intent must be an object")
    required = {
        "metrics", "dimensions", "filters", "time",
        "explicit_metric_versions", "ordering", "limit",
    }
    allowed = required | {
        "unresolved_explicit_version_metrics",
        "unresolved_dimension_mentions",
        "unresolved_filter_value_attributes",
    }
    if not required.issubset(value) or set(value) - allowed:
        raise ValueError("v2 semantic intent fields differ from the minimal contract")

    filters = []
    for index, item in enumerate(value["filters"]):
        if not isinstance(item, dict) or set(item) != {
            "attribute", "operator", "value_json", "value_type", "scope"
        }:
            raise ValueError(f"v2 semantic filter {index} is malformed")
        filters.append({
            "attribute": item["attribute"],
            "operator": item["operator"],
            "value": _decode_json_string(item["value_json"], f"filters[{index}].value_json"),
            "value_type": item["value_type"],
            "scope": item["scope"],
        })

    # Exact duplicate selections collapse deterministically. Conflicting
    # selections for the same metric mean the model recognized an explicit
    # version request but could not choose one; preserve that as a governed
    # clarification signal instead of throwing a provider-response error.
    version_choices: dict[str, set[str]] = {}
    for item in value["explicit_metric_versions"]:
        version_choices.setdefault(item["metric_id"], set()).add(item["version_id"])
    unresolved = set(value.get("unresolved_explicit_version_metrics", ()))
    versions: dict[str, str] = {}
    for metric_id, choices in version_choices.items():
        if len(choices) == 1 and metric_id not in unresolved:
            versions[metric_id] = next(iter(choices))
        else:
            unresolved.add(metric_id)

    time_value = deepcopy(value["time"])
    return {
        "metrics": deepcopy(value["metrics"]),
        "dimensions": deepcopy(value["dimensions"]),
        "filters": filters,
        "time": time_value,
        "explicit_metric_versions": versions,
        "unresolved_explicit_version_metrics": sorted(unresolved),
        "unresolved_dimension_mentions": sorted(set(value.get("unresolved_dimension_mentions", ()))),
        "unresolved_filter_value_attributes": sorted(set(value.get("unresolved_filter_value_attributes", ()))),
        "ordering": deepcopy(value["ordering"]),
        "limit": value["limit"],
    }


def decode_provider_output_v2(raw: dict[str, Any]) -> dict[str, Any]:
    value = deepcopy(raw)
    candidates = value.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("MIA-v2 candidates must be an array")
    for item in candidates:
        semantic_wire = item.pop("semantic_intent", None)
        try:
            semantic = decode_semantic_intent_wire(semantic_wire)
            item["semantic_intent_json"] = canonical_json(semantic)
            item["semantic_decode_error"] = None
        except Exception as exc:
            # Provider transport succeeded; semantic-content mistakes should be
            # handled fail-closed by assurance rather than converted into a paid
            # adapter failure that cannot be replayed.
            item["semantic_intent_json"] = None
            item["semantic_decode_error"] = f"{type(exc).__name__}: {exc}"
    return value


def parse_generation_v2(
    raw: dict[str, Any],
    *,
    input_record: dict[str, Any],
    registry: Registry,
) -> GenerationResult:
    candidates_payload = raw.get("candidates")
    if not isinstance(candidates_payload, list) or len(candidates_payload) > 3:
        raise ValueError("MIA-v2 candidates must be an array with at most three entries")

    outside = raw.get("outside_contract")
    if not isinstance(outside, bool):
        raise ValueError("MIA-v2 outside_contract must be boolean")

    missing_payload = raw.get("missing_capability")
    missing = None
    if missing_payload is not None:
        if not isinstance(missing_payload, dict) or missing_payload.get("code") not in GAP_CODES:
            raise ValueError("MIA-v2 missing capability uses an invalid code")
        concept = missing_payload.get("concept")
        evidence = missing_payload.get("evidence")
        if not isinstance(concept, str) or not concept:
            raise ValueError("MIA-v2 missing capability concept must be non-empty")
        if not isinstance(evidence, list) or any(not isinstance(x, str) for x in evidence):
            raise ValueError("MIA-v2 missing capability evidence must be strings")
        missing = MissingCapability(missing_payload["code"], concept, tuple(evidence))

    # Explicit top-level dispositions dominate partial candidates. Models often
    # include a useful partial interpretation next to a missing-capability
    # diagnosis; that should remain fail-closed and replayable, not become an
    # invalid-output failure. Outside-contract is the strongest disposition.
    if outside:
        return GenerationResult(
            (), None, True, "mia-v2-provider", input_record["request_id"]
        )
    if missing is not None:
        return GenerationResult(
            (), missing, False, "mia-v2-provider", input_record["request_id"]
        )

    context = Context.from_dict(input_record["context"])
    candidates = []
    deferred_gaps: list[tuple[float, MissingCapability]] = []
    deferred_clarify_supports: list[float] = []

    for item in candidates_payload:
        support = item.get("support")
        if isinstance(support, bool) or not isinstance(support, (int, float)) or not 0 <= support <= 1:
            raise ValueError("MIA-v2 candidate support must be in [0,1]")
        support = float(support)
        evidence = item.get("evidence")
        if not isinstance(evidence, list) or any(not isinstance(x, str) for x in evidence):
            raise ValueError("MIA-v2 candidate evidence must be an array of strings")

        if item.get("semantic_decode_error"):
            deferred_clarify_supports.append(support)
            continue
        semantic_json = item.get("semantic_intent_json")
        if not isinstance(semantic_json, str):
            deferred_clarify_supports.append(support)
            continue
        semantic = json.loads(semantic_json)

        # Empty-metric partial parses are semantic incompleteness, not runtime
        # failures. If they are the leading interpretation, assurance should
        # clarify rather than silently substitute a weaker candidate.
        if not semantic.get("metrics"):
            deferred_clarify_supports.append(support)
            continue

        # The semantic provider must never silently drop a requested grouping or
        # filter value that it recognizes as unresolved. Such omissions are
        # incomplete interpretations, so preserve the candidate's support as a
        # fail-closed clarification signal instead of allowing a weaker partial
        # intent to Execute.
        if semantic.get("unresolved_dimension_mentions"):
            deferred_clarify_supports.append(support)
            continue
        if semantic.get("unresolved_filter_value_attributes"):
            deferred_clarify_supports.append(support)
            continue

        unknown_metrics = [
            metric_id for metric_id in semantic["metrics"]
            if registry.metric(metric_id) is None
        ]
        if unknown_metrics:
            deferred_gaps.append((
                support,
                MissingCapability(
                    "GAP_METRIC", unknown_metrics[0],
                    (f"unregistered metric id: {unknown_metrics[0]}",),
                ),
            ))
            continue

        unknown_dimensions = [
            dimension_id for dimension_id in semantic["dimensions"]
            if registry.dimension(dimension_id) is None
        ]
        if unknown_dimensions:
            deferred_gaps.append((
                support,
                MissingCapability(
                    "GAP_DIMENSION", unknown_dimensions[0],
                    (f"unregistered dimension id: {unknown_dimensions[0]}",),
                ),
            ))
            continue

        unknown_filters = [
            item["attribute"] for item in semantic["filters"]
            if registry.dimension(item["attribute"]) is None
        ]
        if unknown_filters:
            deferred_gaps.append((
                support,
                MissingCapability(
                    "GAP_FILTER_CONCEPT", unknown_filters[0],
                    (f"unregistered filter concept: {unknown_filters[0]}",),
                ),
            ))
            continue

        try:
            intent = canonicalize_model_intent_v2(
                semantic, registry=registry, context=context
            )
        except MixedEntityGrouping as exc:
            deferred_gaps.append((
                support,
                MissingCapability(
                    "GAP_COMPOSITION",
                    "mixed-entity grouping requires semantic-compiler capability",
                    (f"deferred_support={support:.6f}", str(exc)),
                ),
            ))
            continue
        except (ContractError, ValueError):
            # A semantically malformed leading candidate must not promote a
            # lower-support interpretation to Execute. Preserve fail-closed
            # behavior as clarification; unexpected programmer errors remain
            # visible in unit/preflight tests against valid fixtures.
            deferred_clarify_supports.append(support)
            continue
        candidates.append(Candidate(intent, support, tuple(evidence)))

    strongest_valid = max((item.support for item in candidates), default=-1.0)
    strongest_gap = max(deferred_gaps, key=lambda item: item[0], default=None)
    strongest_clarify = max(deferred_clarify_supports, default=-1.0)
    strongest_deferred = max(
        strongest_gap[0] if strongest_gap else -1.0,
        strongest_clarify,
    )

    # Preserve the frozen "leading semantic class is authoritative" principle.
    # A malformed/unsupported leading interpretation cannot be bypassed by a
    # lower-support valid candidate.
    if strongest_deferred >= strongest_valid and strongest_deferred >= 0:
        if strongest_gap and strongest_gap[0] >= strongest_clarify:
            return GenerationResult(
                (), strongest_gap[1], False,
                "mia-v2-provider", input_record["request_id"],
            )
        return GenerationResult(
            (), None, False, "mia-v2-provider", input_record["request_id"]
        )

    return GenerationResult(
        tuple(candidates), None, False,
        "mia-v2-provider", input_record["request_id"],
    )


def normalize_mia_v2_output(
    raw: dict[str, Any],
    input_record: dict[str, Any],
    registry: Registry,
    *,
    run_id: str,
    model_id: str,
    execute_threshold: float,
    ambiguity_margin: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    generation = parse_generation_v2(raw, input_record=input_record, registry=registry)
    context = Context.from_dict(input_record["context"])
    decision = Assurer(execute_threshold, ambiguity_margin).decide_generation(
        generation, registry, context, request_id=input_record["request_id"]
    )
    prediction = {
        "run_id": run_id,
        "system_id": "mia-v2",
        "model_id": model_id,
        "case_id": input_record["case_id"],
        "utterance_id": input_record["utterance_id"],
        "predicted_action": decision.action.value,
        "predicted_reason_code": decision.reason_code,
        "predicted_intent": decision.intent.canonical() if decision.intent else None,
        "confidence": decision.confidence,
        "execution_correct": None,
        "provenance_complete": bool(decision.trace.get("registry_hash")),
        "generated_query": None,
        "latency_ms": None,
        "input_tokens": None,
        "output_tokens": None,
        "cost_usd": None,
    }
    trace = {
        "generation": {
            "candidates": [
                {
                    "intent": candidate.intent.canonical(),
                    "support": candidate.support,
                    "evidence": list(candidate.evidence),
                }
                for candidate in generation.candidates
            ],
            "missing_capability": (
                asdict(generation.missing_capability) if generation.missing_capability else None
            ),
            "outside_contract": generation.outside_contract,
            "generator_id": generation.generator_id,
            "request_id": generation.request_id,
        },
        "decision": decision.to_dict(),
    }
    return prediction, trace
