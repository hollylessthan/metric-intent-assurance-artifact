from __future__ import annotations

import json
import math
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .assurance import Assurer
from .generation import GAP_CODES, GenerationResult
from .models import Action, Candidate, Context, Intent, MissingCapability
from .registry import Registry


CALLABLE_SYSTEMS = ("b0", "b1", "b2", "b4", "mia")
GOLD_KEYS = {
    "gold_action", "gold_intents", "primary_reason_code", "adjudication",
    "contrastive_adjudication", "contrastive_change", "candidate_intent",
    "candidate_intents", "alternatives", "violated_constraint",
    "machine_checkable_evidence",
}
# These names are annotations in benchmark records but legitimate vocabulary in
# an output contract. They are therefore blocked inside source model cases, not
# in the provider-facing schema itself.
BENCHMARK_GOLD_KEYS = GOLD_KEYS | {"clarification_question", "missing_capability"}
PROMPT_VERSIONS = {
    "b0": "phase5-b0-v1",
    "b1": "phase5-b1-v4",
    "b2": "phase5-b2-v4",
    "b4": "phase5-b4-v4",
    "mia": "phase5-mia-v5",
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def gold_key_paths(value: Any, prefix: str = "$", *, keys: set[str] | None = None) -> list[str]:
    blocked = GOLD_KEYS if keys is None else keys
    paths: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}"
            if key in blocked:
                paths.append(path)
            paths.extend(gold_key_paths(item, path, keys=blocked))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            paths.extend(gold_key_paths(item, f"{prefix}[{index}]", keys=blocked))
    return paths


def _intent_wire_schema(*, nullable: bool = True) -> dict[str, Any]:
    """Portable closed representation of the canonical intent contract.

    Dynamic maps and unconstrained JSON values are encoded as ordered key/value
    arrays or canonical JSON strings so both providers receive the same strict
    schema. The adapters deterministically decode this transport form before
    the authoritative local intent validator runs.
    """
    closed = {"type": "object", "additionalProperties": False}
    pair = {**closed, "required": ["key", "value_json"], "properties": {
        "key": {"type": "string"}, "value_json": {"type": "string"},
    }}
    version = {**closed, "required": ["metric_id", "version_id"], "properties": {
        "metric_id": {"type": "string"}, "version_id": {"type": "string"},
    }}
    filter_item = {**closed,
        "required": ["attribute", "operator", "value_json", "value_type", "scope"],
        "properties": {
            "attribute": {"type": "string"},
            "operator": {"enum": ["eq", "neq", "gt", "gte", "lt", "lte", "in", "not_in"]},
            "value_json": {"type": "string"},
            "value_type": {"enum": ["string", "number", "integer", "boolean", "date"]},
            "scope": {"type": "string"},
        }}
    time = {**closed,
        "required": ["start", "end", "calendar_id", "temporal_grain", "completeness", "timezone"],
        "properties": {
            "start": {"type": "string"}, "end": {"type": "string"},
            "calendar_id": {"type": "string"},
            "temporal_grain": {"enum": ["day", "week", "month", "quarter", "year"]},
            "completeness": {"type": "string"}, "timezone": {"type": "string"},
        }}
    grain = {**closed, "required": ["entity", "temporal"], "properties": {
        "entity": {"type": "string"},
        "temporal": {"enum": ["day", "week", "month", "quarter", "year"]},
    }}
    ordering = {**closed, "required": ["key", "direction"], "properties": {
        "key": {"type": "string"}, "direction": {"enum": ["asc", "desc"]},
    }}
    schema = {**closed, "required": [
        "metrics", "dimensions", "filters", "time", "output_grain", "comparison_json",
        "ordering", "limit", "version_policy", "metric_versions", "subject_scope",
        "provenance",
    ], "properties": {
        "metrics": {"type": "array", "items": {"type": "string"}},
        "dimensions": {"type": "array", "items": {"type": "string"}},
        "filters": {"type": "array", "items": filter_item},
        "time": time, "output_grain": grain,
        "comparison_json": {"type": ["string", "null"]},
        "ordering": {"type": "array", "items": ordering},
        "limit": {"type": ["integer", "null"]},
        "version_policy": {"enum": ["effective_time", "restated", "explicit"]},
        "metric_versions": {"type": "array", "items": version},
        "subject_scope": {"type": "array", "items": pair},
        "provenance": {"type": "array", "items": {"type": "string"}},
    }}
    if nullable:
        schema["type"] = ["object", "null"]
    return schema


def output_schema(system_id: str) -> dict[str, Any]:
    if system_id not in CALLABLE_SYSTEMS:
        raise ValueError(f"no provider output schema for {system_id}")
    common = {"type": "object", "additionalProperties": False}
    evidence = {"type": "array", "items": {"type": "string"}}
    if system_id == "b0":
        return {**common, "required": ["decision", "sql", "confidence", "evidence"], "properties": {
            "decision": {"enum": ["execute", "abstain"]}, "sql": {"type": ["string", "null"]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1}, "evidence": evidence,
        }}
    if system_id in {"b1", "b2"}:
        return {**common, "required": ["decision", "intent", "confidence", "evidence"], "properties": {
            "decision": {"enum": ["execute", "abstain"]}, "intent": _intent_wire_schema(),
            "confidence": {"type": "number", "minimum": 0, "maximum": 1}, "evidence": evidence,
        }}
    if system_id == "b4":
        return {**common, "required": ["action", "reason_code", "intent", "clarification_question", "missing_concept", "confidence", "evidence"], "properties": {
            "action": {"enum": [item.value for item in Action]}, "reason_code": {"type": "string"},
            "intent": _intent_wire_schema(), "clarification_question": {"type": ["string", "null"]},
            "missing_concept": {"type": ["string", "null"]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1}, "evidence": evidence,
        }}
    candidate = {"type": "object", "additionalProperties": False,
        "required": ["intent", "support", "evidence"], "properties": {
            "intent": _intent_wire_schema(nullable=False), "support": {"type": "number", "minimum": 0, "maximum": 1},
            "evidence": evidence,
        }}
    missing = {"type": ["object", "null"], "additionalProperties": False,
        "required": ["code", "concept", "evidence"], "properties": {
            "code": {"enum": sorted(GAP_CODES)}, "concept": {"type": "string"}, "evidence": evidence,
        }}
    return {**common, "required": ["candidates", "missing_capability", "outside_contract"], "properties": {
        "candidates": {"type": "array", "maxItems": 3, "items": candidate},
        "missing_capability": missing, "outside_contract": {"type": "boolean"},
    }}


def prompt_text(system_id: str, prompts_root: str | Path) -> str:
    if system_id not in CALLABLE_SYSTEMS:
        raise ValueError(f"no provider prompt for {system_id}")
    return (Path(prompts_root) / f"{system_id}.txt").read_text(encoding="utf-8")


def physical_registry_view(registry: Registry) -> dict[str, Any]:
    data = registry.data
    return {
        "snapshot_id": data.get("snapshot_id"),
        "metrics": [{
            key: deepcopy(metric.get(key)) for key in
            ("id", "name", "description", "entity", "aggregation", "allowed_dimensions", "allowed_calendars", "versions", "backends")
        } for metric in data.get("metrics", [])],
        "dimensions": [{
            key: deepcopy(dimension.get(key)) for key in
            ("id", "name", "type", "entity", "allowed_values", "backends")
        } for dimension in data.get("dimensions", [])],
        "calendars": deepcopy(data.get("calendars", [])),
        "entity_paths": deepcopy(data.get("entity_paths", [])),
        "policies": deepcopy(data.get("policies", [])),
    }


def build_model_case(system_id: str, input_record: dict[str, Any], registry: Registry) -> dict[str, Any]:
    if system_id not in CALLABLE_SYSTEMS:
        raise ValueError(f"unsupported callable system: {system_id}")
    if leaked := gold_key_paths(input_record, keys=BENCHMARK_GOLD_KEYS):
        raise ValueError(f"gold-bearing input cannot enter a provider request: {leaked[:5]}")
    required = {"request_id", "case_id", "utterance_id", "domain", "request", "context", "registry_hash"}
    if missing := required - set(input_record):
        raise ValueError(f"model input is missing fields: {sorted(missing)}")
    if input_record["registry_hash"] != registry.snapshot_hash:
        raise ValueError("model input and registry snapshot hashes differ")
    registry_payload = physical_registry_view(registry) if system_id == "b0" else registry.data
    result = {
        "request_id": input_record["request_id"],
        "case_id": input_record["case_id"],
        "utterance_id": input_record["utterance_id"],
        "domain": input_record["domain"],
        "request": input_record["request"],
        "context": input_record["context"],
        "registry_hash": registry.snapshot_hash,
        "registry": registry_payload,
    }
    if leaked := gold_key_paths(result, keys=BENCHMARK_GOLD_KEYS):
        raise AssertionError(f"provider request contains a forbidden gold field: {leaked[:5]}")
    return result


def build_adapter_input(
    system_id: str, input_record: dict[str, Any], registry: Registry, *, provider: str,
    model_id: str, decoding: dict[str, Any], prompts_root: str | Path,
) -> dict[str, Any]:
    case = build_model_case(system_id, input_record, registry)
    return {
        "provider": provider,
        "model_id": model_id,
        "system_id": system_id,
        "prompt_version": PROMPT_VERSIONS[system_id],
        "system_prompt": prompt_text(system_id, prompts_root),
        "output_schema": output_schema(system_id),
        "decoding": deepcopy(decoding),
        "case": case,
    }


def split_cached_case(case: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Separate stable governed context from the per-utterance suffix.

    This is a transport-only transformation: combining the two objects exactly
    reconstructs the model-visible case. Keeping the registry first enables
    provider prefix caching without changing information access.
    """
    required = {"domain", "registry_hash", "registry"}
    if missing := required - set(case):
        raise ValueError(f"cacheable case is missing fields: {sorted(missing)}")
    stable = {key: deepcopy(case[key]) for key in ("domain", "registry_hash", "registry")}
    dynamic = {key: deepcopy(value) for key, value in case.items() if key not in stable}
    if set(stable) & set(dynamic) or {**stable, **dynamic} != case:
        raise AssertionError("cached case split does not preserve the provider-visible case")
    return stable, dynamic


def _decode_json_string(value: Any, path: str) -> Any:
    if not isinstance(value, str):
        raise ValueError(f"{path} must be a JSON string")
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON") from exc


def decode_wire_intent(value: Any) -> dict[str, Any] | None:
    """Decode the provider-neutral transport object without changing meaning."""
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("wire intent must be an object or null")
    expected = {
        "metrics", "dimensions", "filters", "time", "output_grain", "comparison_json",
        "ordering", "limit", "version_policy", "metric_versions", "subject_scope",
        "provenance",
    }
    if set(value) != expected:
        raise ValueError("wire intent fields differ from the portable contract")
    filters = []
    for index, item in enumerate(value["filters"]):
        if not isinstance(item, dict) or set(item) != {
                "attribute", "operator", "value_json", "value_type", "scope"}:
            raise ValueError(f"wire intent filter {index} is malformed")
        filters.append({key: deepcopy(item[key]) for key in
            ("attribute", "operator", "value_type", "scope")})
        filters[-1]["value"] = _decode_json_string(
            item["value_json"], f"wire intent filters[{index}].value_json")
    versions: dict[str, str] = {}
    for item in value["metric_versions"]:
        metric_id, version_id = item["metric_id"], item["version_id"]
        if metric_id in versions:
            raise ValueError("wire intent contains duplicate metric-version keys")
        versions[metric_id] = version_id
    scope: dict[str, Any] = {}
    for item in value["subject_scope"]:
        key = item["key"]
        if key in scope:
            raise ValueError("wire intent contains duplicate subject-scope keys")
        scope[key] = _decode_json_string(item["value_json"], f"wire intent subject_scope.{key}")
    result = {
        "metrics": deepcopy(value["metrics"]), "dimensions": deepcopy(value["dimensions"]),
        "filters": filters, "time": deepcopy(value["time"]),
        "output_grain": deepcopy(value["output_grain"]),
        "comparison": (None if value["comparison_json"] is None else
            _decode_json_string(value["comparison_json"], "wire intent comparison_json")),
        "ordering": deepcopy(value["ordering"]), "limit": value["limit"],
        "version_policy": value["version_policy"], "metric_versions": versions,
        "subject_scope": scope, "provenance": deepcopy(value["provenance"]),
    }
    Intent.from_dict(result)
    return result


def decode_provider_output(system_id: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Convert a strict wire response to the unchanged internal raw contract."""
    value = deepcopy(raw)
    if system_id in {"b1", "b2", "b4"}:
        intent = decode_wire_intent(value.pop("intent", None))
        value["intent_json"] = canonical_json(intent) if intent is not None else None
    elif system_id == "mia":
        candidates = value.get("candidates")
        if not isinstance(candidates, list):
            raise ValueError("MIA wire candidates must be an array")
        for item in candidates:
            intent = decode_wire_intent(item.pop("intent", None))
            if intent is None:
                raise ValueError("MIA wire candidate intent cannot be null")
            item["intent_json"] = canonical_json(intent)
    elif system_id != "b0":
        raise ValueError(f"unsupported provider output system: {system_id}")
    return value


def _confidence(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("model confidence must be finite and in [0, 1]")
    return float(value)


def _intent(value: str | None) -> Intent | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("intent_json must be a JSON string or null")
    return Intent.from_dict(json.loads(value))


def normalize_baseline_output(
    system_id: str, raw: dict[str, Any], input_record: dict[str, Any], *, run_id: str, model_id: str,
) -> dict[str, Any]:
    if system_id not in {"b0", "b1", "b2", "b4"}:
        raise ValueError("baseline normalizer accepts B0, B1, B2, or B4")
    confidence = _confidence(raw.get("confidence"))
    base = {
        "run_id": run_id, "system_id": system_id, "model_id": model_id,
        "case_id": input_record["case_id"], "utterance_id": input_record["utterance_id"],
        "confidence": confidence, "input_tokens": None, "output_tokens": None,
        "latency_ms": None, "cost_usd": None, "execution_correct": None,
        "provenance_complete": None,
    }
    if system_id == "b0":
        decision = raw.get("decision")
        if decision not in {"execute", "abstain"}:
            raise ValueError("B0 decision must be execute or abstain")
        sql = raw.get("sql")
        if decision == "execute" and (not isinstance(sql, str) or not sql.strip()):
            raise ValueError("B0 Execute requires non-empty SQL")
        return {**base, "predicted_action": "execute" if decision == "execute" else "clarify",
            "predicted_reason_code": "BASELINE_DIRECT" if decision == "execute" else "BASELINE_ABSTAIN",
            "predicted_intent": None, "generated_query": sql}
    if system_id in {"b1", "b2"}:
        decision = raw.get("decision")
        if decision not in {"execute", "abstain"}:
            raise ValueError(f"{system_id.upper()} decision must be execute or abstain")
        intent = _intent(raw.get("intent_json"))
        if decision == "execute" and intent is None:
            raise ValueError(f"{system_id.upper()} Execute requires intent_json")
        return {**base, "predicted_action": "execute" if decision == "execute" else "clarify",
            "predicted_reason_code": "BASELINE_DIRECT" if decision == "execute" else "BASELINE_ABSTAIN",
            "predicted_intent": intent.canonical() if intent else None, "generated_query": None}
    action = Action(raw.get("action"))
    intent = _intent(raw.get("intent_json"))
    if action == Action.EXECUTE and intent is None:
        raise ValueError("B4 Execute requires intent_json")
    if action != Action.EXECUTE and intent is not None:
        raise ValueError("B4 non-Execute outputs must not carry an executable intent")
    return {**base, "predicted_action": action.value,
        "predicted_reason_code": str(raw.get("reason_code") or "B4_UNSPECIFIED"),
        "predicted_intent": intent.canonical() if intent else None, "generated_query": None}


def derive_b3(b2_prediction: dict[str, Any], *, threshold: float, run_id: str | None = None) -> dict[str, Any]:
    if b2_prediction.get("system_id") != "b2":
        raise ValueError("B3 must be derived from a B2 prediction")
    if not 0 <= threshold <= 1:
        raise ValueError("B3 threshold must be in [0, 1]")
    execute = b2_prediction["predicted_action"] == "execute" and b2_prediction["confidence"] >= threshold
    return {**b2_prediction, "run_id": run_id or b2_prediction["run_id"], "system_id": "b3",
        "predicted_action": "execute" if execute else "clarify",
        "predicted_reason_code": "BINARY_ANSWER" if execute else "BINARY_ABSTAIN",
        "predicted_intent": b2_prediction["predicted_intent"] if execute else None}


def parse_generation(raw: dict[str, Any], *, request_id: str) -> GenerationResult:
    candidates_payload = raw.get("candidates")
    if not isinstance(candidates_payload, list) or len(candidates_payload) > 3:
        raise ValueError("MIA candidates must be an array with at most three entries")
    candidates = []
    for item in candidates_payload:
        if not isinstance(item, dict):
            raise ValueError("MIA candidate must be an object")
        intent = _intent(item.get("intent_json"))
        if intent is None:
            raise ValueError("MIA candidate requires intent_json")
        evidence = item.get("evidence")
        if not isinstance(evidence, list) or any(not isinstance(value, str) for value in evidence):
            raise ValueError("MIA candidate evidence must be an array of strings")
        candidates.append(Candidate(intent, _confidence(item.get("support")), tuple(evidence)))
    missing_payload = raw.get("missing_capability")
    missing = None
    if missing_payload is not None:
        if not isinstance(missing_payload, dict) or missing_payload.get("code") not in GAP_CODES:
            raise ValueError("MIA missing capability uses an invalid code")
        concept, evidence = missing_payload.get("concept"), missing_payload.get("evidence")
        if not isinstance(concept, str) or not concept or not isinstance(evidence, list) or any(not isinstance(value, str) for value in evidence):
            raise ValueError("MIA missing capability is malformed")
        missing = MissingCapability(missing_payload["code"], concept, tuple(evidence))
    outside = raw.get("outside_contract")
    if not isinstance(outside, bool):
        raise ValueError("MIA outside_contract must be boolean")
    if (missing or outside) and candidates:
        raise ValueError("MIA missing/outside result must not invent candidate intents")
    return GenerationResult(tuple(candidates), missing, outside, "phase5-provider", request_id)


def normalize_mia_output(
    raw: dict[str, Any], input_record: dict[str, Any], registry: Registry, *, run_id: str,
    model_id: str, execute_threshold: float, ambiguity_margin: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    context = Context.from_dict(input_record["context"])
    generation = parse_generation(raw, request_id=input_record["request_id"])
    decision = Assurer(execute_threshold, ambiguity_margin).decide_generation(
        generation, registry, context, request_id=input_record["request_id"])
    prediction = {
        "run_id": run_id, "system_id": "mia", "model_id": model_id,
        "case_id": input_record["case_id"], "utterance_id": input_record["utterance_id"],
        "predicted_action": decision.action.value, "predicted_reason_code": decision.reason_code,
        "predicted_intent": decision.intent.canonical() if decision.intent else None,
        "confidence": decision.confidence, "execution_correct": None,
        "provenance_complete": bool(decision.trace.get("registry_hash")),
        "generated_query": None, "latency_ms": None, "input_tokens": None,
        "output_tokens": None, "cost_usd": None,
    }
    return prediction, {"generation": _generation_dict(generation), "decision": decision.to_dict()}


def _generation_dict(generation: GenerationResult) -> dict[str, Any]:
    return {
        "candidates": [{"intent": candidate.intent.canonical(), "support": candidate.support,
            "evidence": list(candidate.evidence)} for candidate in generation.candidates],
        "missing_capability": asdict(generation.missing_capability) if generation.missing_capability else None,
        "outside_contract": generation.outside_contract,
        "generator_id": generation.generator_id,
        "request_id": generation.request_id,
    }
