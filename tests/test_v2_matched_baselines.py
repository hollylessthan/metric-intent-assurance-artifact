from pathlib import Path

from mia.registry import Registry
from mia.v2_matched_baselines import (
    B2_MATCHED_SYSTEM_ID,
    B4_MATCHED_SYSTEM_ID,
    build_b4_matched_adapter_input,
    normalize_b2_matched,
    normalize_b4_matched,
)
from mia.v2_system import decode_provider_output_v2


ROOT = Path(__file__).resolve().parents[1]


def _record(registry):
    return {
        "request_id": "phase6c-test#u0",
        "case_id": "phase6c-test",
        "utterance_id": "u0",
        "domain": "saas",
        "request": "Show monthly recurring revenue by region for Q1 2026.",
        "context": {
            "role": "finance",
            "calendar_default": "calendar",
            "timezone": "UTC",
        },
        "registry_hash": registry.snapshot_hash,
    }


def _decoded():
    return decode_provider_output_v2({
        "candidates": [{
            "semantic_intent": {
                "metrics": ["mrr"],
                "dimensions": ["region"],
                "filters": [],
                "time": {
                    "start": "2026-01-01",
                    "end": "2026-03-31",
                    "temporal_grain": "month",
                    "calendar_id": None,
                },
                "explicit_metric_versions": [],
                "unresolved_explicit_version_metrics": [],
                "unresolved_dimension_mentions": [],
                "unresolved_filter_value_attributes": [],
                "ordering": [],
                "limit": None,
            },
            "support": 0.92,
            "evidence": ["request names mrr and region"],
        }],
        "missing_capability": None,
        "outside_contract": False,
    })


def test_b2_matched_executes_leading_canonicalized_candidate_without_assurer():
    registry = Registry.load(ROOT / "registries/saas/v1.json")
    pred, trace = normalize_b2_matched(
        _decoded(), _record(registry), registry,
        run_id="test", model_id="test-model",
    )
    assert pred["system_id"] == B2_MATCHED_SYSTEM_ID
    assert pred["predicted_action"] == "execute"
    assert pred["predicted_intent"]["output_grain"]["entity"] == "account"
    assert trace["decision_rule"] == "leading_candidate_no_assurer"


def test_b4_matched_request_reuses_same_canonicalized_representation_without_validator_trace():
    registry = Registry.load(ROOT / "registries/saas/v1.json")
    adapter = build_b4_matched_adapter_input(
        _decoded(), _record(registry), registry,
        provider="gpt",
        model_id="gpt-5.4-mini-2026-03-17",
        decoding={"max_output_tokens": 300, "reasoning_effort": "none", "temperature": 0},
        prompts_root=ROOT / "prompts/v2",
    )
    assert adapter["system_id"] == B4_MATCHED_SYSTEM_ID
    packet = adapter["case"]["semantic_representation"]
    assert packet["candidates"][0]["intent"]["output_grain"]["entity"] == "account"
    case_text = str(adapter["case"]).lower()
    assert "validator_results" not in case_text
    assert "assurer_trace" not in case_text


def test_b4_matched_execute_selects_only_supplied_candidate():
    registry = Registry.load(ROOT / "registries/saas/v1.json")
    raw_router = {
        "action": "execute",
        "selected_candidate_index": 0,
        "reason_code": None,
        "confidence": 0.8,
        "evidence": ["one supplied interpretation appears usable"],
    }
    pred, trace = normalize_b4_matched(
        raw_router, _decoded(), _record(registry), registry,
        run_id="test", model_id="test-model",
    )
    assert pred["system_id"] == B4_MATCHED_SYSTEM_ID
    assert pred["predicted_action"] == "execute"
    assert pred["predicted_intent"]["metrics"] == ["mrr"]
    assert trace["validator_results_exposed"] is False
    assert trace["assurer_trace_exposed"] is False

