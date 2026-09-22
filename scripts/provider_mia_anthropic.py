#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from copy import deepcopy
from pathlib import Path

import provider_transport_anthropic as transport
import provider_transport_common as common
from mia.systems import gold_key_paths

def forbidden_paths(value, prefix="$"):
    return gold_key_paths(value, prefix)
from mia.systems import canonical_json, split_cached_case
from mia.v2_system import decode_provider_output_v2


ADAPTER_VERSION = "mia-v2-anthropic-adapter-v1"


def build_wire_schema(schema: dict) -> dict:
    value = deepcopy(schema)

    def strip(item):
        if isinstance(item, dict):
            for key in tuple(item):
                if key in transport.UNSUPPORTED_SCHEMA_CONSTRAINTS:
                    del item[key]
                else:
                    strip(item[key])
        elif isinstance(item, list):
            for child in item:
                strip(child)

    strip(value)
    return value


def build_payload(adapter_input: dict) -> dict:
    if adapter_input.get("provider") != "claude":
        raise ValueError("adapter accepts only provider=claude")
    if adapter_input.get("system_id") != "mia-v2":
        raise ValueError("adapter accepts only system_id=mia-v2")
    if adapter_input.get("model_id") != transport.MODEL_ID:
        raise ValueError("model_id differs from the frozen Anthropic model")
    if forbidden_paths(adapter_input):
        raise ValueError("adapter input contains forbidden gold fields")

    decoding = adapter_input.get("decoding") or {}
    if (
        decoding.get("reasoning_effort") != transport.EFFORT
        or decoding.get("temperature") is not None
    ):
        raise ValueError("Anthropic decoding differs from the frozen setting")
    maximum = decoding.get("max_output_tokens")
    if type(maximum) is not int or maximum <= 0:
        raise ValueError("max_output_tokens must be a positive integer")

    stable, dynamic = split_cached_case(adapter_input["case"])
    return {
        "model": transport.MODEL_ID,
        "max_tokens": maximum,
        "system": [
            {"type": "text", "text": adapter_input["system_prompt"]},
            {
                "type": "text",
                "text": "GOVERNED_REGISTRY\n" + canonical_json(stable),
                "cache_control": {"type": "ephemeral"},
            },
        ],
        "messages": [
            {
                "role": "user",
                "content": "REQUEST\n" + canonical_json(dynamic),
            }
        ],
        "thinking": {"type": "adaptive"},
        "output_config": {
            "effort": transport.EFFORT,
            "format": {
                "type": "json_schema",
                "schema": build_wire_schema(adapter_input["output_schema"]),
            },
        },
    }


def main() -> int:
    evidence_path = None
    base = None
    response_fields = None
    try:
        adapter_input = json.load(sys.stdin)
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        headers = transport.build_headers(
            api_key, os.environ.get("ANTHROPIC_WORKSPACE_ID")
        )
        evidence_path = Path(os.environ["MIA_V2_ANTHROPIC_EVIDENCE_LOG"])
        pricing, pricing_hash = common.load_pricing()
        if transport.MODEL_ID not in pricing["models"]:
            raise RuntimeError("pricing profile is missing the frozen Anthropic model")

        payload = build_payload(adapter_input)
        base = common.evidence_base(
            "claude",
            ADAPTER_VERSION,
            Path(__file__),
            transport.API_URL,
            adapter_input,
            payload,
            pricing_hash,
        )
        base.update({
            "system_id": "mia-v2",
            "prompt_version": adapter_input["prompt_version"],
        })
        common.enforce_budget(evidence_path, pricing)
        response, raw = common.post_json(
            "Anthropic", transport.API_URL, payload, headers
        )
        usage = transport.normalize_usage(response)
        common.validate_usage(usage)
        response_fields = {
            "response_id": response.get("id"),
            "returned_model_id": response.get("model"),
            "status": response.get("stop_reason"),
            "usage": usage,
            "cost_usd": common.price_usage(
                usage, pricing["models"][transport.MODEL_ID]
            ),
            "raw_response": response,
            "raw_response_text": raw,
            "raw_response_sha256": common.content_hash(raw),
        }
        if response.get("model") != transport.MODEL_ID:
            raise RuntimeError("returned Anthropic model does not match requested snapshot")
        parsed = decode_provider_output_v2(
            json.loads(transport.extract_output(response))
        )
        common.append_jsonl(
            evidence_path, {**base, "outcome": "success", **response_fields}
        )
        sys.stdout.write(common.canonical_json(parsed))
        return 0
    except common.ApiCallError as exc:
        if evidence_path is not None and base is not None:
            common.append_jsonl(
                evidence_path,
                {
                    **base,
                    "outcome": "http_error",
                    "http_status": exc.status,
                    "raw_error_body": exc.body,
                    "raw_error_body_sha256": common.content_hash(exc.body),
                    "cost_usd": 0,
                },
            )
        print(f"MIA-v2 Anthropic adapter error: HTTP {exc.status}", file=sys.stderr)
        return 2
    except Exception as exc:
        if evidence_path is not None and base is not None:
            if response_fields is None:
                common.append_jsonl(
                    evidence_path,
                    {
                        **base,
                        "outcome": "transport_error",
                        "error_class": type(exc).__name__,
                        "error_message": str(exc),
                        "cost_usd": 0,
                    },
                )
            else:
                common.append_jsonl(
                    evidence_path,
                    {
                        **base,
                        "outcome": "provider_response_error",
                        **response_fields,
                        "error_class": type(exc).__name__,
                        "error_message": str(exc),
                    },
                )
        print(f"MIA-v2 Anthropic adapter error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
