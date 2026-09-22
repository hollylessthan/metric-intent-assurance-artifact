from __future__ import annotations

import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from .models import Action, Intent


SYSTEM_IDS = ("b0", "b1", "b2", "b3", "b4", "mia")
INTENT_SLOT_WEIGHTS = {
    "metrics": 0.20,
    "dimensions": 0.10,
    "filters": 0.10,
    "time": 0.15,
    "output_grain": 0.10,
    "comparison": 0.05,
    "ordering": 0.025,
    "limit": 0.025,
    "version_policy": 0.10,
    "metric_versions": 0.075,
    "subject_scope": 0.075,
}


@dataclass(frozen=True)
class Prediction:
    run_id: str
    system_id: str
    model_id: str
    case_id: str
    utterance_id: str
    predicted_action: Action
    confidence: float
    predicted_reason_code: str | None = None
    predicted_intent: Intent | None = None
    execution_correct: bool | None = None
    provenance_complete: bool | None = None
    latency_ms: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    generated_query: str | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Prediction":
        required = ("run_id", "system_id", "model_id", "case_id", "utterance_id", "predicted_action", "confidence")
        missing = [key for key in required if key not in value]
        if missing:
            raise ValueError(f"prediction is missing required fields: {missing}")
        if value["system_id"] not in SYSTEM_IDS and not value["system_id"].startswith("mia-"):
            raise ValueError(f"unknown system_id: {value['system_id']}")
        confidence = value["confidence"]
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError("confidence must be finite and in [0, 1]")
        intent_payload = value.get("predicted_intent")
        intent = Intent.from_dict(intent_payload) if intent_payload is not None else None
        action = Action(value["predicted_action"])
        if action == Action.EXECUTE and value["system_id"] != "b0" and intent is None:
            raise ValueError("non-B0 Execute predictions require predicted_intent")
        numeric_optional = ("latency_ms", "cost_usd")
        for key in numeric_optional:
            item = value.get(key)
            if item is not None and (isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item) or item < 0):
                raise ValueError(f"{key} must be a finite non-negative number")
        for key in ("input_tokens", "output_tokens"):
            item = value.get(key)
            if item is not None and (isinstance(item, bool) or not isinstance(item, int) or item < 0):
                raise ValueError(f"{key} must be a non-negative integer")
        generated_query = value.get("generated_query")
        if generated_query is not None and (not isinstance(generated_query, str) or not generated_query.strip()):
            raise ValueError("generated_query must be a non-empty string or null")
        if value["system_id"] == "b0" and action == Action.EXECUTE and generated_query is None:
            raise ValueError("B0 Execute predictions require generated_query")
        return cls(
            run_id=str(value["run_id"]),
            system_id=str(value["system_id"]),
            model_id=str(value["model_id"]),
            case_id=str(value["case_id"]),
            utterance_id=str(value["utterance_id"]),
            predicted_action=action,
            confidence=float(confidence),
            predicted_reason_code=value.get("predicted_reason_code"),
            predicted_intent=intent,
            execution_correct=value.get("execution_correct"),
            provenance_complete=value.get("provenance_complete"),
            latency_ms=float(value["latency_ms"]) if value.get("latency_ms") is not None else None,
            input_tokens=value.get("input_tokens"),
            output_tokens=value.get("output_tokens"),
            cost_usd=float(value["cost_usd"]) if value.get("cost_usd") is not None else None,
            generated_query=generated_query,
        )


def file_sha256(path: str | Path) -> str:
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_predictions(path: str | Path) -> list[Prediction]:
    rows = [Prediction.from_dict(json.loads(line)) for line in Path(path).read_text().splitlines() if line.strip()]
    keys = [(row.run_id, row.system_id, row.case_id, row.utterance_id) for row in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate run/system/case/utterance prediction")
    return rows


def benchmark_index(cases: Iterable[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for case in cases:
        for position, utterance in enumerate(case["utterances"]):
            utterance_id = f"{case['case_id']}#u{position}"
            index[(case["case_id"], utterance_id)] = {**case, "utterance": utterance, "utterance_position": position}
    return index


def validate_prediction_coverage(predictions: Sequence[Prediction], cases: Sequence[dict[str, Any]], *, split: str) -> None:
    expected = {
        (case["case_id"], f"{case['case_id']}#u{position}")
        for case in cases if case["split"] == split
        for position, _ in enumerate(case["utterances"])
    }
    groups: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    for row in predictions:
        groups[(row.run_id, row.system_id)].add((row.case_id, row.utterance_id))
    for group, observed in groups.items():
        missing = expected - observed
        extra = observed - expected
        if missing or extra:
            raise ValueError(f"incomplete prediction coverage for {group}: missing={len(missing)}, extra={len(extra)}")


def _canonical_intent(value: Intent) -> dict[str, Any]:
    return value.semantic_canonical()


def intent_scores(predicted: Intent | None, gold_payloads: Sequence[dict[str, Any]]) -> tuple[bool, float, float]:
    if predicted is None or not gold_payloads:
        return False, 0.0, 0.0
    predicted_value = _canonical_intent(predicted)
    gold_values = [_canonical_intent(Intent.from_dict(item)) for item in gold_payloads]
    exact = any(predicted_value == gold for gold in gold_values)
    equal_scores = []
    weighted_scores = []
    for gold in gold_values:
        matches = {slot: predicted_value.get(slot) == gold.get(slot) for slot in INTENT_SLOT_WEIGHTS}
        equal_scores.append(sum(matches.values()) / len(matches))
        weighted_scores.append(sum(INTENT_SLOT_WEIGHTS[slot] for slot, matched in matches.items() if matched))
    return exact, max(equal_scores), max(weighted_scores)


def scored_rows(predictions: Sequence[Prediction], cases: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    index = benchmark_index(cases)
    output = []
    for row in predictions:
        case = index.get((row.case_id, row.utterance_id))
        if case is None:
            raise ValueError(f"prediction does not map to benchmark: {row.case_id}/{row.utterance_id}")
        exact, slot_score, weighted_score = intent_scores(row.predicted_intent, case.get("gold_intents", []))
        output.append({
            "run_id": row.run_id,
            "system_id": row.system_id,
            "model_id": row.model_id,
            "case_id": row.case_id,
            "utterance_id": row.utterance_id,
            "utterance_position": case["utterance_position"],
            "split": case["split"],
            "domain": case["domain"],
            "template_family": case["template_family"],
            "gold_action": case["gold_action"],
            "gold_reason_code": case["primary_reason_code"],
            "predicted_action": row.predicted_action.value,
            "predicted_reason_code": row.predicted_reason_code,
            "confidence": row.confidence,
            "intent_exact": exact,
            "intent_slot_accuracy": slot_score,
            "governance_weighted_intent_score": weighted_score,
            "reason_exact": row.predicted_reason_code == case["primary_reason_code"],
            "execution_correct": row.execution_correct,
            "provenance_complete": row.provenance_complete,
            "latency_ms": row.latency_ms,
            "input_tokens": row.input_tokens,
            "output_tokens": row.output_tokens,
            "cost_usd": row.cost_usd,
        })
    return output


def summarize(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        raise ValueError("cannot summarize an empty result set")
    labels = [action.value for action in Action]
    non_execute = [row for row in rows if row["gold_action"] != Action.EXECUTE.value]
    execute = [row for row in rows if row["gold_action"] == Action.EXECUTE.value]
    f1_by_action = {}
    for label in labels:
        tp = sum(row["gold_action"] == label and row["predicted_action"] == label for row in rows)
        fp = sum(row["gold_action"] != label and row["predicted_action"] == label for row in rows)
        fn = sum(row["gold_action"] == label and row["predicted_action"] != label for row in rows)
        f1_by_action[label] = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0
    correct_action = [row["gold_action"] == row["predicted_action"] for row in rows]
    confidences = [row["confidence"] for row in rows]
    return {
        "n_observations": len(rows),
        "n_cases": len({row["case_id"] for row in rows}),
        "unsafe_execution_rate": sum(row["predicted_action"] == Action.EXECUTE.value for row in non_execute) / len(non_execute) if non_execute else 0.0,
        "correct_execution_coverage": sum(row["predicted_action"] == Action.EXECUTE.value and row["intent_exact"] for row in execute) / len(execute) if execute else 0.0,
        "action_macro_f1": sum(f1_by_action.values()) / len(labels),
        "action_f1": f1_by_action,
        "canonical_intent_exact_match": sum(row["intent_exact"] for row in execute) / len(execute) if execute else 0.0,
        "intent_slot_accuracy": sum(row["intent_slot_accuracy"] for row in execute) / len(execute) if execute else 0.0,
        "governance_weighted_intent_score": sum(row["governance_weighted_intent_score"] for row in execute) / len(execute) if execute else 0.0,
        "reason_code_accuracy": sum(row["reason_exact"] for row in rows) / len(rows),
        "paraphrase_consistency": paraphrase_consistency(rows),
        "brier_action_correct": sum((confidence - float(correct)) ** 2 for confidence, correct in zip(confidences, correct_action)) / len(rows),
        "ece_action_correct_10_bin": expected_calibration_error(confidences, correct_action, bins=10),
        "provenance_completeness": _optional_rate(rows, "provenance_complete"),
        "execution_accuracy": _optional_rate(rows, "execution_correct"),
        "mean_latency_ms": _optional_mean(rows, "latency_ms"),
        "total_cost_usd": sum(row["cost_usd"] for row in rows if row["cost_usd"] is not None),
        "total_input_tokens": sum(row["input_tokens"] for row in rows if row["input_tokens"] is not None),
        "total_output_tokens": sum(row["output_tokens"] for row in rows if row["output_tokens"] is not None),
    }


def _optional_rate(rows: Sequence[dict[str, Any]], field: str) -> float | None:
    values = [row[field] for row in rows if row[field] is not None]
    return sum(bool(value) for value in values) / len(values) if values else None


def _optional_mean(rows: Sequence[dict[str, Any]], field: str) -> float | None:
    values = [row[field] for row in rows if row[field] is not None]
    return sum(values) / len(values) if values else None


def paraphrase_consistency(rows: Sequence[dict[str, Any]]) -> float:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[row["case_id"]].append(row)
    consistent = 0
    for group in groups.values():
        signatures = {(row["predicted_action"], row["intent_exact"]) for row in group}
        consistent += len(signatures) == 1
    return consistent / len(groups) if groups else 0.0


def expected_calibration_error(confidences: Sequence[float], correct: Sequence[bool], *, bins: int = 10) -> float:
    if len(confidences) != len(correct) or not confidences:
        raise ValueError("confidence and correctness vectors must be non-empty and aligned")
    total = len(confidences)
    error = 0.0
    for bin_index in range(bins):
        low, high = bin_index / bins, (bin_index + 1) / bins
        positions = [i for i, value in enumerate(confidences) if low <= value < high or (bin_index == bins - 1 and value == 1.0)]
        if not positions:
            continue
        accuracy = sum(correct[i] for i in positions) / len(positions)
        mean_confidence = sum(confidences[i] for i in positions) / len(positions)
        error += len(positions) / total * abs(accuracy - mean_confidence)
    return error


def cluster_bootstrap_interval(
    rows: Sequence[dict[str, Any]], metric: str, *, samples: int = 10_000, seed: int = 20260801
) -> dict[str, float]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[row["case_id"]].append(row)
    case_ids = sorted(groups)
    if not case_ids:
        raise ValueError("bootstrap requires at least one case")
    rng = random.Random(seed)
    estimates = []
    for _ in range(samples):
        sampled = [rng.choice(case_ids) for _ in case_ids]
        sample_rows = [row for case_id in sampled for row in groups[case_id]]
        estimates.append(float(summarize(sample_rows)[metric]))
    estimates.sort()
    low_index = max(0, math.floor(0.025 * samples))
    high_index = min(samples - 1, math.ceil(0.975 * samples) - 1)
    return {"estimate": float(summarize(rows)[metric]), "low": estimates[low_index], "high": estimates[high_index]}


def paired_cluster_bootstrap_difference(
    left: Sequence[dict[str, Any]], right: Sequence[dict[str, Any]], metric: str, *, samples: int = 10_000, seed: int = 20260801
) -> dict[str, float]:
    left_groups = _group_by_case(left)
    right_groups = _group_by_case(right)
    if set(left_groups) != set(right_groups):
        raise ValueError("paired bootstrap requires identical case sets")
    case_ids = sorted(left_groups)
    rng = random.Random(seed)
    differences = []
    for _ in range(samples):
        sampled = [rng.choice(case_ids) for _ in case_ids]
        left_rows = [row for case_id in sampled for row in left_groups[case_id]]
        right_rows = [row for case_id in sampled for row in right_groups[case_id]]
        differences.append(float(summarize(left_rows)[metric]) - float(summarize(right_rows)[metric]))
    differences.sort()
    low_index = max(0, math.floor(0.025 * samples))
    high_index = min(samples - 1, math.ceil(0.975 * samples) - 1)
    return {
        "estimate": float(summarize(left)[metric]) - float(summarize(right)[metric]),
        "low": differences[low_index],
        "high": differences[high_index],
    }


def _group_by_case(rows: Sequence[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[row["case_id"]].append(row)
    return groups


def mcnemar_exact(left: Sequence[bool], right: Sequence[bool]) -> dict[str, float | int]:
    if len(left) != len(right):
        raise ValueError("paired outcomes must have the same length")
    b = sum(a and not c for a, c in zip(left, right))
    c = sum(not a and c for a, c in zip(left, right))
    n = b + c
    if n == 0:
        p_value = 1.0
    else:
        tail = sum(math.comb(n, k) for k in range(0, min(b, c) + 1)) / (2 ** n)
        p_value = min(1.0, 2 * tail)
    return {"left_only": b, "right_only": c, "discordant": n, "p_value": p_value}


def holm_adjust(p_values: dict[str, float]) -> dict[str, float]:
    ordered = sorted(p_values.items(), key=lambda item: item[1])
    adjusted: dict[str, float] = {}
    running = 0.0
    total = len(ordered)
    for index, (name, value) in enumerate(ordered):
        running = max(running, min(1.0, (total - index) * value))
        adjusted[name] = running
    return adjusted


def confusion_matrix(rows: Sequence[dict[str, Any]]) -> dict[str, dict[str, int]]:
    labels = [action.value for action in Action]
    matrix = {gold: {predicted: 0 for predicted in labels} for gold in labels}
    for row in rows:
        matrix[row["gold_action"]][row["predicted_action"]] += 1
    return matrix
