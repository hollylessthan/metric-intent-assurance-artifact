#!/usr/bin/env python3
"""OpenAI Responses API adapter for the frozen Phase 4 review runner."""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


API_URL = "https://api.openai.com/v1/responses"
ADAPTER_VERSION = "phase4-openai-adapter-v5"
MODEL_REASONING_EFFORT = {
    "gpt-5.4-mini-2026-03-17": "none",
    "gpt-5.4-2026-03-05": "low",
}
ALLOWED_MODELS = {"gpt-4.1-mini-2025-04-14", *MODEL_REASONING_EFFORT}

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
    def __init__(self, status: int, body: str):
        super().__init__(f"OpenAI API HTTP {status}")
        self.status, self.body = status, body


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_hash(value: str | bytes) -> str:
    payload = value.encode("utf-8") if isinstance(value, str) else value
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def load_pricing() -> tuple[dict[str, Any], str]:
    path = os.environ.get("MIA_OPENAI_PRICING_CONFIG")
    if not path:
        raise RuntimeError("MIA_OPENAI_PRICING_CONFIG is not set")
    raw = Path(path).read_bytes()
    return json.loads(raw), content_hash(raw)


def price_usage(usage: dict[str, Any], profile: dict[str, Any]) -> float:
    cached = ((usage.get("input_tokens_details") or {}).get("cached_tokens", 0) or 0)
    total_input = usage.get("input_tokens", 0) or 0
    return ((total_input - cached) * profile["input_usd_per_million"]
        + cached * profile["cached_input_usd_per_million"]
        + (usage.get("output_tokens", 0) or 0) * profile["output_usd_per_million"]) / 1_000_000


def existing_spend(path: Path, pricing: dict[str, Any] | None = None) -> float:
    if not path.exists():
        return 0.0
    spent = 0.0
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        cost = float(row.get("cost_usd", 0))
        if not math.isfinite(cost) or cost < 0:
            raise RuntimeError(f"evidence line {line_number} has invalid cost")
        if pricing is not None:
            if row.get("outcome") in {"success", "provider_response_error"}:
                model_id = row.get("requested_model_id")
                if model_id not in pricing["models"]:
                    raise RuntimeError(f"evidence line {line_number} has unknown pricing model")
                expected = price_usage(row.get("usage") or {}, pricing["models"][model_id])
                if abs(cost - expected) > 1e-9:
                    raise RuntimeError(f"evidence line {line_number} cost does not match frozen pricing")
            elif cost != 0:
                raise RuntimeError(f"evidence line {line_number} non-provider outcome has nonzero cost")
        spent += cost
    return spent


def enforce_budget(path: Path, pricing: dict[str, Any] | None = None) -> None:
    limit, reserve = os.environ.get("MIA_MAX_TOTAL_COST_USD"), os.environ.get("MIA_MAX_CALL_COST_USD")
    if not limit or not reserve:
        raise RuntimeError("hard budget variables are required")
    spent = existing_spend(path, pricing)
    if spent + float(reserve) > float(limit):
        raise RuntimeError(f"hard budget blocks next call: spent={spent:.6f}, reserved={float(reserve):.6f}, limit={float(limit):.6f}")


def build_payload(adapter_input: dict[str, Any]) -> dict[str, Any]:
    if adapter_input.get("provider") != "gpt":
        raise ValueError("adapter accepts only provider=gpt")
    model_id = adapter_input.get("model_id")
    if model_id not in ALLOWED_MODELS:
        raise ValueError(f"model_id is not an approved immutable snapshot: {model_id!r}")
    decoding = adapter_input.get("decoding", {})
    maximum = decoding.get("max_output_tokens")
    if type(maximum) is not int or maximum <= 0:
        raise ValueError("max_output_tokens must be a positive integer")
    approved_effort = MODEL_REASONING_EFFORT.get(model_id)
    requested_effort = decoding.get("reasoning_effort")
    if approved_effort is not None and requested_effort != approved_effort:
        raise ValueError(
            f"reasoning_effort must be {approved_effort!r} for immutable model {model_id}")
    if approved_effort is None and requested_effort is not None:
        raise ValueError(f"reasoning_effort is not approved for immutable model {model_id}")
    temperature = decoding.get("temperature")
    if approved_effort not in (None, "none"):
        if temperature is not None:
            raise ValueError("temperature must be omitted for a reasoning-enabled request")
    elif temperature != 0:
        raise ValueError("frozen non-reasoning protocol requires temperature=0")
    user_content = canonical_json(adapter_input["case"])
    if adapter_input.get("format_repair"):
        user_content += "\n\nFORMAT_REPAIR\n" + canonical_json(adapter_input["format_repair"])
    payload = {"model": model_id, "store": False,
        "max_output_tokens": maximum, "instructions": adapter_input["system_prompt"],
        "input": user_content, "text": {"format": {"type": "json_schema",
        "name": "phase4_mia_review", "strict": True, "schema": REVIEW_SCHEMA}}}
    if approved_effort is not None:
        payload["reasoning"] = {"effort": approved_effort}
    if temperature is not None:
        payload["temperature"] = temperature
    return payload


def extract_output(response: dict[str, Any]) -> str:
    if response.get("status") != "completed":
        raise RuntimeError(f"OpenAI response incomplete: {response.get('incomplete_details')!r}")
    for item in response.get("output", []):
        for part in item.get("content", []) if item.get("type") == "message" else []:
            if part.get("type") == "refusal":
                raise RuntimeError("OpenAI returned a refusal")
            if part.get("type") == "output_text":
                return part["text"]
    raise RuntimeError("OpenAI response contained no output_text")


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(canonical_json(value) + "\n")


def evidence_base(adapter_input: dict[str, Any], payload: dict[str, Any], pricing_hash: str) -> dict[str, Any]:
    return {"schema_version": "1.0.0", "adapter_version": ADAPTER_VERSION,
        "adapter_commit_sha": os.environ.get("GITHUB_SHA", "local"),
        "adapter_sha256": content_hash(Path(__file__).read_bytes()), "provider": "gpt",
        "run_label": os.environ.get("MIA_RUN_LABEL", "unspecified"),
        "requested_model_id": adapter_input["model_id"],
        "request_id": adapter_input.get("case", {}).get("request_id", "unknown"),
        "attempt": 2 if adapter_input.get("format_repair") else 1, "api_endpoint": API_URL,
        "pricing_manifest_sha256": pricing_hash, "rendered_payload": payload,
        "rendered_payload_sha256": content_hash(canonical_json(payload)),
        "recorded_at": datetime.now(timezone.utc).isoformat()}


def call_openai(payload: dict[str, Any], api_key: str) -> tuple[dict[str, Any], str]:
    request = urllib.request.Request(API_URL, data=canonical_json(payload).encode(),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw), raw
    except urllib.error.HTTPError as exc:
        raise ApiCallError(exc.code, exc.read().decode("utf-8", errors="replace")) from exc


def main() -> int:
    evidence_path, base = None, None
    try:
        adapter_input = json.load(sys.stdin)
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        evidence_path = Path(os.environ["MIA_OPENAI_EVIDENCE_LOG"])
        pricing, pricing_hash = load_pricing()
        model_id = adapter_input["model_id"]
        if model_id not in pricing["models"]:
            raise RuntimeError(f"pricing profile missing for {model_id}")
        payload = build_payload(adapter_input)
        base = evidence_base(adapter_input, payload, pricing_hash)
        enforce_budget(evidence_path, pricing)
        try:
            response, raw = call_openai(payload, api_key)
        except ApiCallError:
            raise
        except Exception as exc:
            append_jsonl(evidence_path, {**base, "outcome": "transport_error",
                "error_type": type(exc).__name__, "error_message": str(exc), "cost_usd": 0})
            raise
        response_fields = {"raw_response": response, "raw_response_text": raw,
            "raw_response_sha256": content_hash(raw)}
        try:
            if not isinstance(response, dict):
                raise RuntimeError("OpenAI response is not a JSON object")
            usage = response.get("usage") or {}
            response_fields.update({
                "response_id": response.get("id"), "returned_model_id": response.get("model"),
                "status": response.get("status"),
                "incomplete_details": response.get("incomplete_details"),
                "usage": usage,
                "cost_usd": price_usage(usage, pricing["models"][model_id]),
            })
            if response.get("model") != model_id:
                raise RuntimeError(
                    f"returned model mismatch: requested={model_id}, returned={response.get('model')}")
            parsed_output = json.loads(extract_output(response))
        except Exception as exc:
            response_fields.setdefault("cost_usd", 0)
            response_fields.update({"post_response_error_type": type(exc).__name__,
                "post_response_error_message": str(exc)})
            append_jsonl(evidence_path, {**base, "outcome": "provider_response_error",
                **response_fields})
            raise
        append_jsonl(evidence_path, {**base, "outcome": "success", **response_fields})
        sys.stdout.write(canonical_json(parsed_output))
        return 0
    except ApiCallError as exc:
        if evidence_path is not None and base is not None:
            append_jsonl(evidence_path, {**base, "outcome": "http_error", "http_status": exc.status,
                "raw_error_body": exc.body, "raw_error_body_sha256": content_hash(exc.body), "cost_usd": 0})
        print(f"openai phase4 adapter error: HTTP {exc.status}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"openai phase4 adapter error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
