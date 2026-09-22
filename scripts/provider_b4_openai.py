#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import provider_transport_openai as transport
from mia.systems import gold_key_paths

def forbidden_paths(value, prefix="$"):
    return gold_key_paths(value, prefix)
from mia.systems import canonical_json, split_cached_case


API_URL = "https://api.openai.com/v1/responses"
ADAPTER_VERSION = "phase6c-matched-router-openai-v1"


def build_payload(adapter_input: dict) -> dict:
    if adapter_input.get("provider") != "gpt":
        raise ValueError("adapter accepts only provider=gpt")
    if adapter_input.get("system_id") != "b4-matched":
        raise ValueError("adapter accepts only system_id=b4-matched")
    model_id = adapter_input.get("model_id")
    if model_id not in transport.ALLOWED_MODELS:
        raise ValueError("model_id is not an approved immutable OpenAI snapshot")
    gold_scan = dict(adapter_input)
    gold_case = dict(adapter_input.get("case") or {})
    gold_case.pop("semantic_representation", None)
    gold_scan["case"] = gold_case
    if forbidden_paths(gold_scan):
        raise ValueError("adapter input contains forbidden benchmark-gold fields outside the sealed semantic packet")
    decoding = adapter_input.get("decoding") or {}
    maximum = decoding.get("max_output_tokens")
    if type(maximum) is not int or maximum <= 0:
        raise ValueError("max_output_tokens must be a positive integer")
    effort = transport.MODEL_REASONING_EFFORT.get(model_id)
    if decoding.get("reasoning_effort") != effort:
        raise ValueError("reasoning effort differs from the approved model setting")
    temperature = decoding.get("temperature")
    if effort not in (None, "none") and temperature is not None:
        raise ValueError("temperature must be omitted for reasoning-enabled models")
    if effort in (None, "none") and temperature != 0:
        raise ValueError("non-reasoning requests require temperature=0")

    stable, dynamic = split_cached_case(adapter_input["case"])
    cache_identity = canonical_json({
        "system_id": adapter_input["system_id"],
        "domain": stable["domain"],
        "registry_hash": stable["registry_hash"],
        "prompt_version": adapter_input["prompt_version"],
    })
    cache_key = "p6c:" + hashlib.sha256(cache_identity.encode("utf-8")).hexdigest()[:32]
    payload = {
        "model": model_id,
        "store": False,
        "max_output_tokens": maximum,
        "instructions": adapter_input["system_prompt"],
        "input": [
            {"role": "developer", "content": [{"type": "input_text",
                "text": "GOVERNED_REGISTRY\n" + canonical_json(stable)}]},
            {"role": "user", "content": [{"type": "input_text",
                "text": "REQUEST_AND_SHARED_REPRESENTATION\n" + canonical_json(dynamic)}]},
        ],
        "prompt_cache_key": cache_key,
        "text": {"format": {"type": "json_schema", "name": "phase6c_b4_matched",
            "strict": True, "schema": adapter_input["output_schema"]}},
    }
    if effort is not None:
        payload["reasoning"] = {"effort": effort}
    if temperature is not None:
        payload["temperature"] = temperature
    return payload


def main() -> int:
    evidence_path = None
    base = None
    response_fields = None
    try:
        adapter_input = json.load(sys.stdin)
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        evidence_path = Path(os.environ["MIA_OPENAI_EVIDENCE_LOG"])
        pricing, pricing_hash = transport.load_pricing()
        model_id = adapter_input["model_id"]
        payload = build_payload(adapter_input)
        base = {
            "schema_version": "1.0.0",
            "adapter_version": ADAPTER_VERSION,
            "adapter_commit_sha": os.environ.get("GITHUB_SHA", "local"),
            "adapter_sha256": transport.content_hash(Path(__file__).read_bytes()),
            "provider": "gpt",
            "system_id": "b4-matched",
            "prompt_version": adapter_input["prompt_version"],
            "run_label": os.environ.get("MIA_RUN_LABEL", "unspecified"),
            "requested_model_id": model_id,
            "request_id": adapter_input["case"]["request_id"],
            "api_endpoint": API_URL,
            "pricing_manifest_sha256": pricing_hash,
            "rendered_payload": payload,
            "rendered_payload_sha256": transport.content_hash(transport.canonical_json(payload)),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        transport.enforce_budget(evidence_path, pricing)
        response, raw = transport.call_openai(payload, api_key)
        usage = response.get("usage") or {}
        response_fields = {
            "response_id": response.get("id"),
            "returned_model_id": response.get("model"),
            "status": response.get("status"),
            "usage": usage,
            "cost_usd": transport.price_usage(usage, pricing["models"][model_id]),
            "raw_response": response,
            "raw_response_text": raw,
            "raw_response_sha256": transport.content_hash(raw),
        }
        if response.get("model") != model_id:
            raise RuntimeError("returned OpenAI model does not match requested snapshot")
        parsed = json.loads(transport.extract_output(response))
        transport.append_jsonl(evidence_path, {**base, "outcome": "success", **response_fields})
        sys.stdout.write(transport.canonical_json(parsed))
        return 0
    except transport.ApiCallError as exc:
        if evidence_path is not None and base is not None:
            transport.append_jsonl(evidence_path, {**base, "outcome": "http_error",
                "http_status": exc.status, "raw_error_body": exc.body,
                "raw_error_body_sha256": transport.content_hash(exc.body), "cost_usd": 0})
        print(f"Phase 6C OpenAI adapter error: HTTP {exc.status}", file=sys.stderr)
        return 2
    except Exception as exc:
        if evidence_path is not None and base is not None:
            if response_fields is None:
                transport.append_jsonl(evidence_path, {**base, "outcome": "transport_error",
                    "error_class": type(exc).__name__, "error_message": str(exc), "cost_usd": 0})
            else:
                transport.append_jsonl(evidence_path, {**base, "outcome": "provider_response_error",
                    **response_fields, "error_class": type(exc).__name__, "error_message": str(exc)})
        print(f"Phase 6C OpenAI adapter error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
