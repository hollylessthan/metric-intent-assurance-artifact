#!/usr/bin/env python3
"""Credential-free Phase 6C round-2 mechanism replay and paired analysis.

Replays the sealed final-MIA v2 semantic generations under altered deterministic
Assurer policies. No provider calls are made. Also compares sealed final MIA
against B4-Matched using paired case-cluster resampling and case-level McNemar
unsafe-execution events.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

from mia.assurance import Assurer
from mia.benchmark import load_jsonl
from mia.models import Action, Context
from mia.study_metrics import Prediction, scored_rows, summarize
from mia.registry import Registry
from mia.validation import Validator
from mia.v2_system import parse_generation_v2


DISPUTED_SOURCE_CASES = {
    "support-clarify-012",
    "commerce-clarify-009",
    "saas-clarify-011",
    "support-execute-013",
    "saas-execute-013",
}

VALIDATOR_FAMILIES = (
    "metric_identity",
    "time",
    "grain",
    "dimension",
    "compatibility",
    "entity_path",
    "version",
    "policy",
    "provenance",
    "backend_capability",
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def prediction_from_value(value: dict[str, Any]) -> Prediction:
    intent = value.get("predicted_intent")
    return Prediction.from_dict({
        **value,
        "system_id": value["system_id"] if str(value["system_id"]).startswith("mia-") else "mia-" + str(value["system_id"]),
    })


class FamilyFilteredValidator:
    def __init__(self, dropped_family: str | None):
        self.base = Validator()
        self.dropped_family = dropped_family

    def validate(self, intent, registry, context):
        violations = self.base.validate(intent, registry, context)
        if self.dropped_family is None:
            return violations
        return tuple(v for v in violations if v.family != self.dropped_family)


class ReplayAssurer(Assurer):
    def __init__(self, execute_threshold: float, ambiguity_margin: float, dropped_family: str | None = None):
        super().__init__(execute_threshold, ambiguity_margin)
        self.validator = FamilyFilteredValidator(dropped_family)
        self.dropped_family = dropped_family

    def _capability_violations(self, intent, registry):
        if self.dropped_family == "backend_capability":
            return ()
        return super()._capability_violations(intent, registry)


def threshold_config(root: Path, provider: str) -> tuple[float, float]:
    lock = json.loads((root / "evaluation/threshold_lock.json").read_text(encoding="utf-8"))
    model = lock["models"][provider]
    return float(model["mia_execute_threshold"]), float(model["mia_ambiguity_margin"])


def index_requests(path: Path) -> dict[str, dict[str, Any]]:
    rows = read_jsonl(path)
    out = {}
    for row in rows:
        case = row["case"]
        rid = case["request_id"]
        if rid in out:
            raise RuntimeError(f"duplicate request_id: {rid}")
        out[rid] = row
    if len(out) != 720:
        raise RuntimeError(f"expected 720 requests, observed {len(out)}")
    return out


def index_raw(path: Path) -> dict[str, dict[str, Any]]:
    rows = read_jsonl(path)
    out = {}
    for row in rows:
        if row.get("system_id") != "mia-v2":
            continue
        rid = row["request_id"]
        if rid in out:
            raise RuntimeError(f"duplicate raw output: {rid}")
        out[rid] = row["raw"]
    if len(out) != 720:
        raise RuntimeError(f"expected 720 sealed MIA raw outputs, observed {len(out)}")
    return out


def replay_variant(
    *,
    root: Path,
    provider: str,
    requests: dict[str, dict[str, Any]],
    raw: dict[str, dict[str, Any]],
    variant: str,
    execute_threshold: float,
    ambiguity_margin: float,
    dropped_family: str | None,
) -> list[dict[str, Any]]:
    rows = []
    for request_id, adapter in requests.items():
        case = adapter["case"]
        registry = Registry.load(root / f"registries/{case['domain']}.json")
        generation = parse_generation_v2(raw[request_id], input_record=case, registry=registry)
        context = Context.from_dict(case["context"])
        decision = ReplayAssurer(
            execute_threshold=execute_threshold,
            ambiguity_margin=ambiguity_margin,
            dropped_family=dropped_family,
        ).decide_generation(generation, registry, context, request_id=request_id)
        rows.append({
            "run_id": f"v2-replay-{provider}",
            "system_id": f"mia-v2-{variant}",
            "model_id": adapter["model_id"],
            "case_id": case["case_id"],
            "utterance_id": case["utterance_id"],
            "predicted_action": decision.action.value,
            "predicted_reason_code": decision.reason_code,
            "predicted_intent": decision.intent.canonical() if decision.intent else None,
            "confidence": float(decision.confidence or 0.0),
            "execution_correct": None,
            "provenance_complete": bool(decision.trace.get("registry_hash")),
            "generated_query": None,
            "latency_ms": 0.0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
        })
    return rows


def metric_from_rows(rows: list[dict[str, Any]], metric: str) -> float:
    if metric == "unsafe_execution_rate":
        subset = [r for r in rows if r["gold_action"] != Action.EXECUTE.value]
        return sum(r["predicted_action"] == Action.EXECUTE.value for r in subset) / len(subset)
    if metric == "correct_execution_coverage":
        subset = [r for r in rows if r["gold_action"] == Action.EXECUTE.value]
        return sum(
            r["predicted_action"] == Action.EXECUTE.value and bool(r["intent_exact"])
            for r in subset
        ) / len(subset)
    raise ValueError(metric)


def paired_cluster_delta(
    a_rows: list[dict[str, Any]],
    b_rows: list[dict[str, Any]],
    metric: str,
    *,
    samples: int = 10_000,
    seed: int = 20260919,
) -> dict[str, float]:
    a = {(r["case_id"], r["utterance_id"]): r for r in a_rows}
    b = {(r["case_id"], r["utterance_id"]): r for r in b_rows}
    if set(a) != set(b):
        raise RuntimeError("paired systems do not cover identical utterances")
    by_case_a = defaultdict(list)
    by_case_b = defaultdict(list)
    for key in sorted(a):
        by_case_a[key[0]].append(a[key])
        by_case_b[key[0]].append(b[key])
    case_ids = sorted(by_case_a)
    estimate = metric_from_rows(a_rows, metric) - metric_from_rows(b_rows, metric)
    rng = random.Random(seed)
    values = []
    for _ in range(samples):
        sample_ids = [rng.choice(case_ids) for _ in case_ids]
        sa = [row for cid in sample_ids for row in by_case_a[cid]]
        sb = [row for cid in sample_ids for row in by_case_b[cid]]
        values.append(metric_from_rows(sa, metric) - metric_from_rows(sb, metric))
    values.sort()
    lo = values[int(0.025 * (samples - 1))]
    hi = values[int(0.975 * (samples - 1))]
    return {"estimate": estimate, "low": lo, "high": hi}


def exact_two_sided_binomial_p(k: int, n: int) -> float:
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(0, min(k, n-k) + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def unsafe_case_mcnemar(a_rows: list[dict[str, Any]], b_rows: list[dict[str, Any]]) -> dict[str, Any]:
    def events(rows):
        grouped = defaultdict(list)
        for r in rows:
            grouped[r["case_id"]].append(r)
        return {
            cid: any(x["predicted_action"] == Action.EXECUTE.value for x in group)
            for cid, group in grouped.items()
            if group and group[0]["gold_action"] != Action.EXECUTE.value
        }
    a, b = events(a_rows), events(b_rows)
    if set(a) != set(b):
        raise RuntimeError("unsafe case sets differ")
    a_only = sum(a[c] and not b[c] for c in a)
    b_only = sum(b[c] and not a[c] for c in a)
    return {
        "cases": len(a),
        "a_only_unsafe": a_only,
        "b_only_unsafe": b_only,
        "discordant": a_only + b_only,
        "exact_two_sided_p": exact_two_sided_binomial_p(a_only, a_only + b_only),
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--provider", choices=("gpt", "claude"), required=True)
    p.add_argument("--mia-artifact", type=Path, required=True)
    p.add_argument("--b4-artifact", type=Path, required=True)
    p.add_argument("--repo-root", type=Path, default=Path("."))
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()

    root = args.repo_root.resolve()
    benchmark = load_jsonl(root / "benchmark/canonical_cases.v1.1.jsonl")
    requests = index_requests(args.mia_artifact / "requests.jsonl")
    raw = index_raw(args.mia_artifact / "raw_outputs.jsonl")
    if set(requests) != set(raw):
        raise RuntimeError("sealed request/raw identities differ")

    tau_e, tau_a = threshold_config(root, args.provider)
    variants: dict[str, tuple[float, float, str | None]] = {
        "full": (tau_e, tau_a, None),
        "no-margin": (tau_e, 0.0, None),
        "no-tau-e": (0.0, tau_a, None),
        "no-thresholds": (0.0, 0.0, None),
    }
    for family in VALIDATOR_FAMILIES:
        variants[f"drop-{family}"] = (tau_e, tau_a, family)

    replay_predictions: dict[str, list[dict[str, Any]]] = {}
    summaries = {}
    scored_by_variant = {}
    for name, (te, ta, family) in variants.items():
        rows = replay_variant(
            root=root, provider=args.provider, requests=requests, raw=raw,
            variant=name, execute_threshold=te, ambiguity_margin=ta, dropped_family=family,
        )
        replay_predictions[name] = rows
        predictions = [Prediction.from_dict(x) for x in rows]
        scored = [r for r in scored_rows(predictions, benchmark) if r["split"] == "test"]
        scored_by_variant[name] = scored
        summaries[name] = summarize(scored)

    sealed_final = [Prediction.from_dict(x) for x in read_jsonl(args.mia_artifact / "predictions.jsonl")]
    sealed_final_scored = [r for r in scored_rows(sealed_final, benchmark) if r["split"] == "test"]

    b4_values = read_jsonl(args.b4_artifact / "predictions.jsonl")
    b4_predictions = [prediction_from_value(x) for x in b4_values]
    b4_scored = [r for r in scored_rows(b4_predictions, benchmark) if r["split"] == "test"]

    full = scored_by_variant["full"]
    full_action_mismatches = sum(
        a["predicted_action"] != b["predicted_action"]
        for a, b in zip(
            sorted(full, key=lambda r: (r["case_id"], r["utterance_id"])),
            sorted(sealed_final_scored, key=lambda r: (r["case_id"], r["utterance_id"])),
        )
    )
    if full_action_mismatches:
        raise RuntimeError(f"full replay differs from sealed final MIA on {full_action_mismatches} actions")

    paired = {
        "mia_minus_b4_matched": {
            "unsafe_execution_rate": paired_cluster_delta(sealed_final_scored, b4_scored, "unsafe_execution_rate"),
            "correct_execution_coverage": paired_cluster_delta(sealed_final_scored, b4_scored, "correct_execution_coverage"),
            "unsafe_case_mcnemar": unsafe_case_mcnemar(sealed_final_scored, b4_scored),
        }
    }

    final_without_disputed = [r for r in sealed_final_scored if r["case_id"] not in DISPUTED_SOURCE_CASES]
    b4_without_disputed = [r for r in b4_scored if r["case_id"] not in DISPUTED_SOURCE_CASES]
    disputed_label_sensitivity = {
        "excluded_case_ids": sorted(DISPUTED_SOURCE_CASES),
        "final_mia": summarize(final_without_disputed),
        "b4_matched": summarize(b4_without_disputed),
        "paired_after_exclusion": {
            "unsafe_execution_rate": paired_cluster_delta(
                final_without_disputed, b4_without_disputed, "unsafe_execution_rate"
            ),
            "correct_execution_coverage": paired_cluster_delta(
                final_without_disputed, b4_without_disputed, "correct_execution_coverage"
            ),
            "unsafe_case_mcnemar": unsafe_case_mcnemar(
                final_without_disputed, b4_without_disputed
            ),
        },
    }

    report = {
        "schema_version": "1.0.0",
        "study_id": "v2-fixed-generation-mechanism-replay",
        "evidence_class": "secondary_posthoc_fixed_generation_mechanism_analysis",
        "provider": args.provider,
        "thresholds": {"execute": tau_e, "ambiguity_margin": tau_a},
        "provider_calls": 0,
        "full_replay_action_mismatches_vs_sealed_final": full_action_mismatches,
        "summaries": summaries,
        "paired": paired,
        "disputed_label_sensitivity": disputed_label_sensitivity,
        "interpretation_scope": (
            "All variants reuse the exact sealed final-MIA semantic generations and v2 parser/canonicalizer. "
            "Effects therefore describe deterministic Assurer-policy interventions conditional on those generations."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    pred_dir = args.output.parent / f"{args.provider}-predictions"
    pred_dir.mkdir(parents=True, exist_ok=True)
    for name, rows in replay_predictions.items():
        (pred_dir / f"{name}.jsonl").write_text(
            "".join(json.dumps(x, sort_keys=True) + "\n" for x in rows), encoding="utf-8"
        )

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
