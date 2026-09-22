#!/usr/bin/env python3
"""Anthropic Messages API adapter for the frozen Phase 4 review protocol."""

from __future__ import annotations

import json
import os
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import provider_transport_common as common


API_URL = "https://api.anthropic.com/v1/messages"
ADAPTER_VERSION = "phase4-anthropic-adapter-v1"
MODEL_ID = "claude-sonnet-5"
EFFORT = "low"
WORKSPACE_ID_PATTERN = re.compile(r"^wrkspc_[A-Za-z0-9]+$")
UNSUPPORTED_SCHEMA_CONSTRAINTS = {
    "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
    "multipleOf", "minLength", "maxLength", "minItems", "maxItems",
    "uniqueItems", "minProperties", "maxProperties",
}


def build_headers(api_key: str, workspace_id: str | None) -> dict[str, str]:
    headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
    if workspace_id:
        if not WORKSPACE_ID_PATTERN.fullmatch(workspace_id):
            raise RuntimeError(
                "ANTHROPIC_WORKSPACE_ID must be a wrkspc_-prefixed workspace ID")
        headers["anthropic-workspace-id"] = workspace_id
    return headers


def build_wire_schema() -> dict[str, Any]:
    """Transform the strict review schema to Anthropic's supported subset.

    The original constraints remain authoritative and are enforced by
    phase4_model_review.validate_review after every response.
    """
    schema = deepcopy(common.REVIEW_SCHEMA)

    def strip_unsupported(value: Any) -> None:
        if isinstance(value, dict):
            for key in tuple(value):
                if key in UNSUPPORTED_SCHEMA_CONSTRAINTS:
                    del value[key]
                else:
                    strip_unsupported(value[key])
        elif isinstance(value, list):
            for item in value:
                strip_unsupported(item)

    strip_unsupported(schema)
    properties = schema["properties"]
    properties["naturalness_score"]["description"] = "Integer from 1 through 5 inclusive."
    properties["confidence"]["description"] = "Number from 0 through 1 inclusive."
    properties["registry_evidence"]["description"] = (
        "Must contain at least one non-empty evidence string.")
    properties["rationale"]["description"] = (
        "Non-empty rationale containing no more than 80 words.")
    return schema


def build_payload(adapter_input: dict[str, Any]) -> dict[str, Any]:
    if adapter_input.get("provider") != "claude":
        raise ValueError("adapter accepts only provider=claude")
    if adapter_input.get("model_id") != MODEL_ID:
        raise ValueError(f"model_id must be the frozen active model {MODEL_ID!r}")
    decoding = adapter_input.get("decoding", {})
    if decoding.get("reasoning_effort") != EFFORT:
        raise ValueError(f"reasoning_effort must be {EFFORT!r}")
    if decoding.get("temperature") is not None:
        raise ValueError("temperature must be omitted for adaptive thinking")
    maximum = decoding.get("max_output_tokens")
    if type(maximum) is not int or maximum <= 0:
        raise ValueError("max_output_tokens must be a positive integer")
    user_content = common.canonical_json(adapter_input["case"])
    if adapter_input.get("format_repair"):
        user_content += "\n\nFORMAT_REPAIR\n" + common.canonical_json(adapter_input["format_repair"])
    return {"model": MODEL_ID, "max_tokens": maximum,
        "system": adapter_input["system_prompt"],
        "messages": [{"role": "user", "content": user_content}],
        "thinking": {"type": "adaptive"},
        "output_config": {"effort": EFFORT,
            "format": {"type": "json_schema", "schema": build_wire_schema()}}}


def normalize_usage(response: dict[str, Any]) -> dict[str, int]:
    usage = response.get("usage") or {}
    cache_write = (usage.get("cache_creation_input_tokens", 0) or 0)
    cached = (usage.get("cache_read_input_tokens", 0) or 0)
    return {"input_tokens": (usage.get("input_tokens", 0) or 0) + cache_write + cached,
        "cached_input_tokens": cached, "cache_write_input_tokens": cache_write,
        "output_tokens": usage.get("output_tokens", 0) or 0}


def extract_output(response: dict[str, Any]) -> str:
    if response.get("stop_reason") == "refusal":
        raise RuntimeError("Anthropic returned a refusal")
    if response.get("stop_reason") != "end_turn":
        raise RuntimeError(f"Anthropic response did not end normally: {response.get('stop_reason')!r}")
    texts = [block.get("text") for block in response.get("content", [])
        if block.get("type") == "text"
        and isinstance(block.get("text"), str)
        and block.get("text").strip()]
    if len(texts) != 1:
        raise RuntimeError("Anthropic response contained no unique text output")
    return texts[0]


def main() -> int:
    evidence_path = None
    base = None
    try:
        adapter_input = json.load(sys.stdin)
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        headers = build_headers(api_key, os.environ.get("ANTHROPIC_WORKSPACE_ID"))
        evidence_path = Path(os.environ["MIA_PROVIDER_EVIDENCE_LOG"])
        pricing, pricing_hash = common.load_pricing()
        if MODEL_ID not in pricing.get("models", {}):
            raise RuntimeError(f"pricing profile missing for {MODEL_ID}")
        payload = build_payload(adapter_input)
        base = common.evidence_base("claude", ADAPTER_VERSION, Path(__file__), API_URL,
            adapter_input, payload, pricing_hash)
        common.enforce_budget(evidence_path, pricing)
        try:
            response, raw = common.post_json("Anthropic", API_URL, payload,
                headers)
        except common.ApiCallError:
            raise
        except Exception as exc:
            common.append_jsonl(evidence_path, {**base, "outcome": "transport_error",
                "error_type": type(exc).__name__, "error_message": str(exc), "cost_usd": 0})
            raise
        usage = normalize_usage(response)
        response_fields = {"response_id": response.get("id"),
            "returned_model_id": response.get("model"), "status": response.get("stop_reason"),
            "usage": usage, "cost_usd": 0, "raw_response": response,
            "raw_response_text": raw, "raw_response_sha256": common.content_hash(raw)}
        try:
            common.validate_usage(usage)
            response_fields["cost_usd"] = common.price_usage(
                usage, pricing["models"][MODEL_ID])
            if not response.get("id"):
                raise RuntimeError("Anthropic response ID is missing")
            if response.get("model") != MODEL_ID:
                raise RuntimeError("returned Anthropic model does not match frozen model")
            parsed = json.loads(extract_output(response))
        except Exception as exc:
            common.append_jsonl(evidence_path, {**base, "outcome": "provider_response_error",
                **response_fields, "post_response_error_type": type(exc).__name__,
                "post_response_error_message": str(exc)})
            raise
        common.append_jsonl(evidence_path, {**base, "outcome": "success", **response_fields})
        sys.stdout.write(common.canonical_json(parsed))
        return 0
    except common.ApiCallError as exc:
        if evidence_path is not None and base is not None:
            common.append_jsonl(evidence_path, {**base, "outcome": "http_error",
                "http_status": exc.status, "raw_error_body": exc.body,
                "raw_error_body_sha256": common.content_hash(exc.body),
                "http_retry_after": exc.retry_after,
                "http_request_id": exc.request_id, "cost_usd": 0})
        print(f"anthropic phase4 adapter error: HTTP {exc.status}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"anthropic phase4 adapter error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
