#!/usr/bin/env python3
"""Shared integrity, evidence, and budget controls for non-OpenAI Phase 4 adapters."""

from __future__ import annotations

import hashlib
import json
import math
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REVIEW_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["predicted_action", "predicted_reason", "paraphrases_equivalent",
        "unintended_ambiguity", "naturalness_score", "execution_accuracy_insufficient",
        "confidence", "registry_evidence", "rationale"],
    "properties": {
        "predicted_action": {"type": "string", "enum": ["execute", "clarify", "reject", "coverage_gap"]},
        "predicted_reason": {"type": "string", "enum": [
            "EXE_UNIQUE_SUPPORTED", "CLR_METRIC_IDENTITY", "CLR_CALENDAR", "CLR_DIMENSION",
            "CLR_FILTER_VALUE", "CLR_VERSION_POLICY", "REJ_AUTHORIZATION",
            "REJ_DIMENSION_INCOMPATIBLE", "REJ_GRAIN_ADDITIVITY", "REJ_ENTITY_PATH",
            "REJ_VERSION_INVALID", "GAP_METRIC", "GAP_DIMENSION", "GAP_FILTER_CONCEPT",
            "GAP_COMPOSITION", "GAP_VERSION"]},
        "paraphrases_equivalent": {"type": "boolean"},
        "unintended_ambiguity": {"type": "boolean"},
        "naturalness_score": {"type": "integer", "minimum": 1, "maximum": 5},
        "execution_accuracy_insufficient": {"type": "boolean"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "registry_evidence": {"type": "array", "minItems": 1, "items": {"type": "string"}},
        "rationale": {"type": "string", "maxLength": 800},
    },
}


class ApiCallError(RuntimeError):
    def __init__(self, provider: str, status: int, body: str,
                 headers: dict[str, str] | None = None):
        super().__init__(f"{provider} API HTTP {status}")
        self.provider, self.status, self.body = provider, status, body
        normalized = {str(key).lower(): str(value)
            for key, value in (headers or {}).items()}
        self.retry_after = normalized.get("retry-after")
        self.request_id = normalized.get("request-id")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_hash(value: str | bytes) -> str:
    payload = value.encode("utf-8") if isinstance(value, str) else value
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def load_pricing() -> tuple[dict[str, Any], str]:
    path = os.environ.get("MIA_PROVIDER_PRICING_CONFIG")
    if not path:
        raise RuntimeError("MIA_PROVIDER_PRICING_CONFIG is not set")
    raw = Path(path).read_bytes()
    return json.loads(raw), content_hash(raw)


def price_usage(usage: dict[str, Any], profile: dict[str, Any]) -> float:
    cached = usage.get("cached_input_tokens", 0) or 0
    cache_write = usage.get("cache_write_input_tokens", 0) or 0
    total_input = usage.get("input_tokens", 0) or 0
    uncached = total_input - cached - cache_write
    if any(type(value) is not int or value < 0 for value in
            (cached, cache_write, total_input, usage.get("output_tokens", 0) or 0)):
        raise RuntimeError("provider usage contains invalid token counts")
    if uncached < 0:
        raise RuntimeError("provider cached token counts exceed total input")
    return (uncached * profile["input_usd_per_million"]
        + cached * profile.get("cached_input_usd_per_million", profile["input_usd_per_million"])
        + cache_write * profile.get("cache_write_usd_per_million", profile["input_usd_per_million"])
        + (usage.get("output_tokens", 0) or 0) * profile["output_usd_per_million"]) / 1_000_000


def validate_usage(usage: dict[str, Any]) -> None:
    required = {"input_tokens", "cached_input_tokens", "cache_write_input_tokens",
        "output_tokens"}
    if set(usage) != required:
        raise RuntimeError("provider usage fields differ from the frozen normalized schema")
    if any(type(usage[field]) is not int or usage[field] < 0 for field in required):
        raise RuntimeError("provider usage contains invalid token counts")
    if usage["input_tokens"] <= 0 or usage["output_tokens"] <= 0:
        raise RuntimeError("provider usage must include positive input and output token counts")
    if usage["cached_input_tokens"] + usage["cache_write_input_tokens"] > usage["input_tokens"]:
        raise RuntimeError("provider cached token counts exceed total input")


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(canonical_json(value) + "\n")


def existing_spend(path: Path, pricing: dict[str, Any]) -> float:
    if not path.exists():
        return 0.0
    spent = 0.0
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        cost = row.get("cost_usd", 0)
        if type(cost) not in (int, float) or not math.isfinite(cost) or cost < 0:
            raise RuntimeError(f"evidence line {line_number} has invalid cost")
        if row.get("outcome") in {"success", "provider_response_error"}:
            model_id = row.get("requested_model_id")
            if model_id not in pricing["models"]:
                raise RuntimeError(f"evidence line {line_number} has unknown pricing model")
            expected = price_usage(row.get("usage") or {}, pricing["models"][model_id])
            if abs(cost - expected) > 1e-9:
                raise RuntimeError(f"evidence line {line_number} cost does not match frozen pricing")
        elif cost != 0:
            raise RuntimeError(f"evidence line {line_number} non-provider outcome has nonzero cost")
        spent += float(cost)
    return spent


def enforce_budget(path: Path, pricing: dict[str, Any]) -> None:
    limit = os.environ.get("MIA_MAX_TOTAL_COST_USD")
    reserve = os.environ.get("MIA_MAX_CALL_COST_USD")
    if not limit or not reserve:
        raise RuntimeError("hard budget variables are required")
    spent = existing_spend(path, pricing)
    if spent + float(reserve) > float(limit):
        raise RuntimeError(
            f"hard budget blocks next call: spent={spent:.6f}, "
            f"reserved={float(reserve):.6f}, limit={float(limit):.6f}")


def evidence_base(provider: str, adapter_version: str, adapter_file: Path,
        api_url: str, adapter_input: dict[str, Any], payload: dict[str, Any],
        pricing_hash: str) -> dict[str, Any]:
    return {"schema_version": "1.0.0", "adapter_version": adapter_version,
        "adapter_commit_sha": os.environ.get("GITHUB_SHA", "local"),
        "adapter_sha256": content_hash(adapter_file.read_bytes()), "provider": provider,
        "run_label": os.environ.get("MIA_RUN_LABEL", "unspecified"),
        "requested_model_id": adapter_input["model_id"],
        "request_id": adapter_input.get("case", {}).get("request_id", "unknown"),
        "attempt": 2 if adapter_input.get("format_repair") else 1,
        "api_endpoint": api_url, "pricing_manifest_sha256": pricing_hash,
        "rendered_payload": payload,
        "rendered_payload_sha256": content_hash(canonical_json(payload)),
        "recorded_at": datetime.now(timezone.utc).isoformat()}


def post_json(provider: str, url: str, payload: dict[str, Any], headers: dict[str, str],
        timeout: int = 180) -> tuple[dict[str, Any], str]:
    request = urllib.request.Request(url, data=canonical_json(payload).encode(),
        headers={**headers, "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                raise RuntimeError(f"{provider} response is not a JSON object")
            return parsed, raw
    except urllib.error.HTTPError as exc:
        raise ApiCallError(provider, exc.code,
            exc.read().decode("utf-8", errors="replace"),
            dict(exc.headers.items()) if exc.headers else {}) from exc
