from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from .models import Action
from .phase5_systems import BENCHMARK_GOLD_KEYS, gold_key_paths
from .registry import Registry
from .v2_system import build_model_case_v2, parse_generation_v2


B2_MATCHED_SYSTEM_ID = "b2-matched"
B4_MATCHED_SYSTEM_ID = "b4-matched"
B4_MATCHED_PROMPT_VERSION = "phase6c-b4-matched-v1"


def _generation_packet(raw: dict[str, Any], input_record: dict[str, Any], registry: Registry) -> dict[str, Any]:
    """Canonicalize the exact final-MIA semantic generation without invoking Assurer."""
    generation = parse_generation_v2(raw, input_record=input_record, registry=registry)
    return {
        "candidates": [
            {
                "intent": candidate.intent.canonical(),
                "support": candidate.support,
                "evidence": list(candidate.evidence),
            }
            for candidate in generation.candidates
        ],
        "missing_capability": (
            {
                "code": generation.missing_capability.code,
                "concept": generation.missing_capability.concept,
                "evidence": list(generation.missing_capability.evidence),
            }
            if generation.missing_capability
            else None
        ),
        "outside_contract": generation.outside_contract,
    }


def normalize_b2_matched(
    raw_mia_v2: dict[str, Any],
    input_record: dict[str, Any],
    registry: Registry,
    *,
    run_id: str,
    model_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Representation-matched structured baseline.

    This control reuses the exact final-MIA semantic generation and deterministic
    canonicalization, but it does not call Assurer or any metric-specific
    validator/decision policy. It executes the highest-support canonicalized
    candidate whenever one exists.
    """
    packet = _generation_packet(raw_mia_v2, input_record, registry)

    if packet["outside_contract"]:
        action = Action.REJECT
        reason = "OUTSIDE_CONTRACT"
        intent = None
        confidence = 1.0
    elif packet["missing_capability"] is not None:
        action = Action.COVERAGE_GAP
        reason = packet["missing_capability"]["code"]
        intent = None
        confidence = 1.0
    elif not packet["candidates"]:
        action = Action.CLARIFY
        reason = "UNRESOLVED_SEMANTICS"
        intent = None
        confidence = 0.0
    else:
        leading = max(packet["candidates"], key=lambda item: item["support"])
        action = Action.EXECUTE
        reason = None
        intent = leading["intent"]
        confidence = float(leading["support"])

    prediction = {
        "run_id": run_id,
        "system_id": B2_MATCHED_SYSTEM_ID,
        "model_id": model_id,
        "case_id": input_record["case_id"],
        "utterance_id": input_record["utterance_id"],
        "predicted_action": action.value,
        "predicted_reason_code": reason,
        "predicted_intent": intent,
        "confidence": confidence,
        "execution_correct": None,
        "provenance_complete": intent is not None,
        "generated_query": None,
        "latency_ms": 0.0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0.0,
    }
    return prediction, {"representation": packet, "decision_rule": "leading_candidate_no_assurer"}


def b4_matched_output_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["action", "selected_candidate_index", "reason_code", "confidence", "evidence"],
        "properties": {
            "action": {"enum": [a.value for a in Action]},
            "selected_candidate_index": {"type": ["integer", "null"], "minimum": 0},
            "reason_code": {"type": ["string", "null"]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "evidence": {"type": "array", "items": {"type": "string"}},
        },
    }


def build_b4_matched_adapter_input(
    raw_mia_v2: dict[str, Any],
    input_record: dict[str, Any],
    registry: Registry,
    *,
    provider: str,
    model_id: str,
    decoding: dict[str, Any],
    prompts_root: str | Path,
) -> dict[str, Any]:
    """Give a generic router the same reduced/canonicalized representation as MIA.

    Validator results, MIA thresholds, and Assurer traces are deliberately absent.
    """
    if leaked := gold_key_paths(input_record, keys=BENCHMARK_GOLD_KEYS):
        raise ValueError(f"gold-bearing input cannot enter B4-matched: {leaked[:5]}")
    model_case = build_model_case_v2(input_record, registry)
    packet = _generation_packet(raw_mia_v2, input_record, registry)
    # build_model_case_v2 has already rejected any benchmark-gold fields in
    # request/context/registry. The shared semantic packet is derived from the
    # sealed provider output, and may legitimately use names such as
    # "missing_capability" that overlap with benchmark bookkeeping keys. Do not
    # re-run the name-based gold scanner over model-generated semantics.
    case = {
        **model_case,
        "semantic_representation": deepcopy(packet),
    }
    return {
        "provider": provider,
        "model_id": model_id,
        "system_id": B4_MATCHED_SYSTEM_ID,
        "prompt_version": B4_MATCHED_PROMPT_VERSION,
        "system_prompt": (Path(prompts_root) / "b4_matched.txt").read_text(encoding="utf-8"),
        "output_schema": b4_matched_output_schema(),
        "decoding": deepcopy(decoding),
        "case": case,
    }


def normalize_b4_matched(
    raw_router: dict[str, Any],
    raw_mia_v2: dict[str, Any],
    input_record: dict[str, Any],
    registry: Registry,
    *,
    run_id: str,
    model_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    packet = _generation_packet(raw_mia_v2, input_record, registry)
    action = Action(raw_router["action"])
    confidence = float(raw_router["confidence"])
    selected = raw_router.get("selected_candidate_index")

    if action == Action.EXECUTE:
        if not isinstance(selected, int) or selected < 0 or selected >= len(packet["candidates"]):
            raise ValueError("B4-matched Execute requires a valid selected_candidate_index")
        intent = packet["candidates"][selected]["intent"]
    else:
        if selected is not None:
            raise ValueError("B4-matched non-Execute action must use null selected_candidate_index")
        intent = None

    prediction = {
        "run_id": run_id,
        "system_id": B4_MATCHED_SYSTEM_ID,
        "model_id": model_id,
        "case_id": input_record["case_id"],
        "utterance_id": input_record["utterance_id"],
        "predicted_action": action.value,
        "predicted_reason_code": raw_router.get("reason_code"),
        "predicted_intent": intent,
        "confidence": confidence,
        "execution_correct": None,
        "provenance_complete": intent is not None,
        "generated_query": None,
        "latency_ms": None,
        "input_tokens": None,
        "output_tokens": None,
        "cost_usd": None,
    }
    trace = {
        "representation": packet,
        "router": deepcopy(raw_router),
        "validator_results_exposed": False,
        "assurer_trace_exposed": False,
    }
    return prediction, trace
