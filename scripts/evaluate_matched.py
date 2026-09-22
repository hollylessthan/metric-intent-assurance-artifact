#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from mia.benchmark import load_jsonl
from mia.models import Action, Intent
from mia.study_metrics import (
    Prediction,
    confusion_matrix,
    scored_rows,
    summarize,
    validate_prediction_coverage,
)
from repro_stats import fast_cluster_interval


def load_phase6c_predictions(path: Path) -> list[Prediction]:
    rows: list[Prediction] = []
    seen: set[tuple[str, str, str, str]] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value: dict[str, Any] = json.loads(line)
        required = ("run_id", "system_id", "model_id", "case_id", "utterance_id", "predicted_action", "confidence")
        missing = [key for key in required if key not in value]
        if missing:
            raise ValueError(f"prediction missing required fields: {missing}")
        if value["system_id"] not in {"b2-matched", "b4-matched"}:
            raise ValueError(f"unexpected matched-control system_id: {value['system_id']}")
        intent_payload = value.get("predicted_intent")
        intent = Intent.from_dict(intent_payload) if intent_payload is not None else None
        action = Action(value["predicted_action"])
        if action == Action.EXECUTE and intent is None:
            raise ValueError("matched-control Execute prediction requires predicted_intent")
        row = Prediction(
            run_id=str(value["run_id"]),
            system_id=str(value["system_id"]),
            model_id=str(value["model_id"]),
            case_id=str(value["case_id"]),
            utterance_id=str(value["utterance_id"]),
            predicted_action=action,
            confidence=float(value["confidence"]),
            predicted_reason_code=value.get("predicted_reason_code"),
            predicted_intent=intent,
            execution_correct=value.get("execution_correct"),
            provenance_complete=value.get("provenance_complete"),
            latency_ms=float(value["latency_ms"]) if value.get("latency_ms") is not None else None,
            input_tokens=value.get("input_tokens"),
            output_tokens=value.get("output_tokens"),
            cost_usd=float(value["cost_usd"]) if value.get("cost_usd") is not None else None,
            generated_query=value.get("generated_query"),
        )
        key = (row.run_id, row.system_id, row.case_id, row.utterance_id)
        if key in seen:
            raise ValueError(f"duplicate prediction: {key}")
        seen.add(key)
        rows.append(row)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate matched-control matched controls without provider access.")
    parser.add_argument("--benchmark", default="benchmark/canonical_cases.v1.1.jsonl")
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--split", choices=("development", "test"), default="test")
    parser.add_argument("--output", required=True)
    parser.add_argument("--bootstrap-samples", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=20260919)
    args = parser.parse_args()

    cases = load_jsonl(args.benchmark)
    predictions = load_phase6c_predictions(Path(args.predictions))
    validate_prediction_coverage(predictions, cases, split=args.split)
    rows = [row for row in scored_rows(predictions, cases) if row["split"] == args.split]

    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["run_id"], row["system_id"], row["model_id"])].append(row)

    report: dict[str, Any] = {
        "schema_version": "1.0.0",
        "study_id": "phase6c-representation-matched-controls",
        "evidence_class": "secondary_posthoc_mechanism_analysis",
        "scope": (
            "Assurer/decision-layer contribution conditional on the same final-MIA "
            "semantic parser and deterministic canonicalization."
        ),
        "split": args.split,
        "bootstrap_samples": args.bootstrap_samples,
        "seed": args.seed,
        "systems": {},
    }
    for key, group in sorted(grouped.items()):
        run_id, system_id, model_id = key
        identity = f"{run_id}/{system_id}/{model_id}"
        report["systems"][identity] = {
            "summary": summarize(group),
            "confusion_matrix": confusion_matrix(group),
            "confidence_intervals": {
                metric: fast_cluster_interval(group, metric, samples=args.bootstrap_samples, seed=args.seed)
                for metric in ("unsafe_execution_rate", "correct_execution_coverage")
            },
        }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
