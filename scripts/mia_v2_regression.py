#!/usr/bin/env python3
"""Run the post-hoc MIA-v2 regression on the frozen Phase 5 held-out inputs.

This runner calls only MIA-v2. Frozen B0-B4 outputs are reused during later
analysis. It never loads test labels while provider calls are running.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import phase5_development as common
import phase5_prepare
from mia.phase5 import Prediction
from mia.registry import Registry
from mia.v2_system import build_adapter_input_v2, normalize_mia_v2_output


EXPECTED_CASES = 240
EXPECTED_CALLS = 720
CAPS = {"gpt": 4.0, "claude": 8.0}
COMBINED_CAP = 12.0
COMPLETION_POLICY = "fail_closed_invalid_output_v1"
SETTINGS = {
    "gpt": {
        "model_id": "gpt-5.4-mini-2026-03-17",
        "adapter": "mia_v2_openai_adapter.py",
        "secret": "OPENAI_API_KEY",
        "evidence_env": "MIA_V2_OPENAI_EVIDENCE_LOG",
        "pricing_env": "MIA_OPENAI_PRICING_CONFIG",
        "pricing": "config/openai-phase4-pricing.json",
        "next_call_reserve_usd": 0.05,
        "decoding": {
            "max_output_tokens": 1200,
            "reasoning_effort": "none",
            "temperature": 0,
        },
    },
    "claude": {
        "model_id": "claude-sonnet-5",
        "adapter": "mia_v2_anthropic_adapter.py",
        "secret": "ANTHROPIC_API_KEY",
        "evidence_env": "MIA_V2_ANTHROPIC_EVIDENCE_LOG",
        "pricing_env": "MIA_PROVIDER_PRICING_CONFIG",
        "pricing": "config/phase4-provider-pricing.json",
        "next_call_reserve_usd": 0.10,
        "decoding": {
            "max_output_tokens": 1200,
            "reasoning_effort": "low",
            "temperature": None,
        },
    },
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return common.read_jsonl(path)


def prepare_requests(root: Path, output: Path, provider: str) -> list[dict[str, Any]]:
    settings = SETTINGS[provider]
    with tempfile.TemporaryDirectory(prefix="mia-v2-regression-prepare-") as directory:
        prepared = Path(directory)
        manifest = phase5_prepare.prepare(
            root,
            root / "benchmarks/phase4/final/canonical_cases.v1.1.jsonl",
            prepared,
        )
        records = read_jsonl(prepared / "test.jsonl")

    if manifest["split_counts"]["test"] != {"cases": EXPECTED_CASES, "utterances": EXPECTED_CALLS}:
        raise RuntimeError("frozen held-out split size changed")

    registries = {
        domain: Registry.load(root / f"registries/phase4/{domain}/v1.json")
        for domain in sorted({record["domain"] for record in records})
    }
    requests = [
        build_adapter_input_v2(
            record,
            registries[record["domain"]],
            provider=provider,
            model_id=settings["model_id"],
            decoding=settings["decoding"],
            prompts_root=root / "prompts/v2",
        )
        for record in records
    ]
    if len(requests) != EXPECTED_CALLS:
        raise RuntimeError("MIA-v2 regression request count differs from 720")
    if len({row["case"]["request_id"] for row in requests}) != EXPECTED_CALLS:
        raise RuntimeError("MIA-v2 regression request IDs are not unique")

    output.mkdir(parents=True, exist_ok=True)
    request_path = output / "requests.jsonl"
    request_path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in requests),
        encoding="utf-8",
    )
    return requests


def threshold_config(root: Path, provider: str) -> dict[str, float]:
    lock = json.loads((root / "config/phase5-threshold-lock.json").read_text())
    model = lock["models"][provider]
    if model["model_id"] != SETTINGS[provider]["model_id"]:
        raise RuntimeError("v1 threshold lock model differs from v2 regression model")
    return {
        "execute_threshold": float(model["mia_execute_threshold"]),
        "ambiguity_margin": float(model["mia_ambiguity_margin"]),
    }


def prepare_only(root: Path, output: Path, provider: str) -> dict[str, Any]:
    requests = prepare_requests(root, output, provider)
    thresholds = threshold_config(root, provider)
    report = {
        "schema_version": "1.0.0",
        "status": "pass",
        "provider_calls_permitted": False,
        "study_id": "mia-v2-posthoc-phase5-regression",
        "provider": provider,
        "model_id": SETTINGS[provider]["model_id"],
        "cases": EXPECTED_CASES,
        "expected_provider_calls": EXPECTED_CALLS,
        "hard_cap_usd": CAPS[provider],
        "combined_hard_cap_usd": COMBINED_CAP,
        "decoding": SETTINGS[provider]["decoding"],
        "thresholds_reused_from_frozen_v1": thresholds,
        "request_manifest_sha256": common.file_hash(output / "requests.jsonl"),
        "notes": [
            "This is post-hoc MIA-v2 regression, not a replacement for Phase 5 confirmatory MIA-v1.",
            "Only MIA-v2 is called; frozen B0-B4 outputs are reused later.",
            "No provider credentials are required for prepare-only mode.",
        ],
    }
    (output / "preflight.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def failure_prediction(
    provider: str,
    adapter_input: dict[str, Any],
    evidence: dict[str, Any],
    latency_ms: float,
    failure: dict[str, Any],
) -> dict[str, Any]:
    case = adapter_input["case"]
    value = {
        "run_id": f"mia-v2-regression-{provider}",
        "system_id": "mia-v2",
        "model_id": adapter_input["model_id"],
        "case_id": case["case_id"],
        "utterance_id": case["utterance_id"],
        "predicted_action": "clarify",
        "predicted_reason_code": "SYS_INVALID_OUTPUT",
        "predicted_intent": None,
        "confidence": 0.0,
        "execution_correct": None,
        "provenance_complete": False,
        "generated_query": None,
        **common.usage_fields(evidence, latency_ms),
        "request_id": case["request_id"],
        "split": "test",
        "completion_policy": COMPLETION_POLICY,
        "failure_stage": failure.get("stage"),
        "failure_error_class": failure.get("error_class"),
    }
    Prediction.from_dict(value)
    return value


def normalize_success(
    provider: str,
    adapter_input: dict[str, Any],
    raw: dict[str, Any],
    evidence: dict[str, Any],
    latency_ms: float,
    root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    case = adapter_input["case"]
    registry = Registry.load(root / f"registries/phase4/{case['domain']}/v1.json")
    thresholds = threshold_config(root, provider)
    prediction, trace = normalize_mia_v2_output(
        raw,
        case,
        registry,
        run_id=f"mia-v2-regression-{provider}",
        model_id=adapter_input["model_id"],
        execute_threshold=thresholds["execute_threshold"],
        ambiguity_margin=thresholds["ambiguity_margin"],
    )
    prediction.update(common.usage_fields(evidence, latency_ms))
    prediction.update({"request_id": case["request_id"], "split": "test"})
    Prediction.from_dict(prediction)
    trace = {
        "run_id": prediction["run_id"],
        "system_id": "mia-v2",
        "model_id": prediction["model_id"],
        "request_id": case["request_id"],
        "case_id": case["case_id"],
        "utterance_id": case["utterance_id"],
        "threshold_source": "frozen_phase5_v1_lock",
        **common.usage_fields(evidence, latency_ms),
        **trace,
    }
    return prediction, trace


def run(
    root: Path,
    output: Path,
    provider: str,
    maximum_spend_usd: float,
    max_runtime_minutes: float,
) -> dict[str, Any]:
    settings = SETTINGS[provider]
    if maximum_spend_usd != CAPS[provider]:
        raise ValueError("MIA-v2 regression cap must equal the precommitted provider cap")
    if max_runtime_minutes <= 0:
        raise ValueError("max runtime must be positive")
    if not os.environ.get(settings["secret"]):
        raise RuntimeError(f"{settings['secret']} is not set")

    requests = prepare_requests(root, output, provider)
    output.mkdir(parents=True, exist_ok=True)
    evidence_path = output / f"{provider}_evidence.jsonl"
    raw_path = output / "raw_outputs.jsonl"
    prediction_path = output / "predictions.jsonl"
    trace_path = output / "traces.jsonl"
    failure_path = output / "failures.jsonl"

    evidence = common.group_evidence(read_jsonl(evidence_path))
    raw_index = common.unique_index(read_jsonl(raw_path), "MIA-v2 raw outputs")
    predictions = common.unique_index(read_jsonl(prediction_path), "MIA-v2 predictions")
    traces = common.unique_index(read_jsonl(trace_path), "MIA-v2 traces")
    failures = common.unique_index(read_jsonl(failure_path), "MIA-v2 failures")

    expected = {("mia-v2", row["case"]["request_id"]) for row in requests}
    for label, observed in {
        "evidence": set(evidence),
        "raw": set(raw_index),
        "predictions": set(predictions),
        "traces": set(traces),
        "failures": set(failures),
    }.items():
        if observed - expected:
            raise RuntimeError(f"MIA-v2 {label} checkpoint has unexpected identities")

    env = dict(os.environ)
    env.update({
        settings["evidence_env"]: str(evidence_path),
        settings["pricing_env"]: str(root / settings["pricing"]),
        "MIA_MAX_TOTAL_COST_USD": str(maximum_spend_usd),
        "MIA_MAX_CALL_COST_USD": str(settings["next_call_reserve_usd"]),
        "MIA_RUN_LABEL": f"mia-v2-phase5-regression-{provider}",
    })

    started = time.monotonic()
    budget_exhausted = runtime_exhausted = False

    for adapter_input in requests:
        request_id = adapter_input["case"]["request_id"]
        key = ("mia-v2", request_id)
        if key in predictions:
            continue

        attempts = evidence.get(key, [])
        successful = [row for row in attempts if row.get("outcome") == "success"]
        if successful:
            evidence_row = successful[0]
            raw_record = raw_index.get(key)
            if raw_record is None:
                raise RuntimeError(f"{key}: successful evidence exists without stored normalized raw output")
            if key in failures:
                prediction = failure_prediction(
                    provider, adapter_input, evidence_row, 0.0, failures[key]
                )
                trace = {**prediction, "generation": None, "decision": None}
            else:
                try:
                    prediction, trace = normalize_success(
                        provider,
                        adapter_input,
                        raw_record["raw"],
                        evidence_row,
                        0.0,
                        root,
                    )
                except Exception as exc:
                    failure = {
                        "system_id": "mia-v2",
                        "request_id": request_id,
                        "stage": "normalization",
                        "error_class": type(exc).__name__,
                        "error": str(exc),
                    }
                    common.append_jsonl(failure_path, failure)
                    failures[key] = failure
                    prediction = failure_prediction(
                        provider, adapter_input, evidence_row, 0.0, failure
                    )
                    trace = {**prediction, "generation": None, "decision": None}
            common.append_jsonl(prediction_path, prediction)
            common.append_jsonl(trace_path, {"system_id": "mia-v2", "request_id": request_id, **trace})
            predictions[key] = prediction
            traces[key] = trace
            continue

        if time.monotonic() - started >= max_runtime_minutes * 60:
            runtime_exhausted = True
            break

        if attempts and (
            not common.retryable_zero_cost_failure(attempts[-1])
            or len(attempts) >= common.MAX_TRANSPORT_ATTEMPTS
        ):
            evidence_row = attempts[-1]
            failure = failures.get(key) or {
                "system_id": "mia-v2",
                "request_id": request_id,
                "stage": "adapter",
                "outcome": evidence_row.get("outcome"),
                "attempts": len(attempts),
                "error": str(
                    evidence_row.get("error_message")
                    or evidence_row.get("raw_error_body")
                    or "provider failure"
                )[-2000:],
            }
            if key not in failures:
                common.append_jsonl(failure_path, failure)
                failures[key] = failure
            prediction = failure_prediction(provider, adapter_input, evidence_row, 0.0, failure)
            trace = {**prediction, "generation": None, "decision": None}
            common.append_jsonl(prediction_path, prediction)
            common.append_jsonl(trace_path, {"system_id": "mia-v2", "request_id": request_id, **trace})
            predictions[key] = prediction
            traces[key] = trace
            continue

        while True:
            before = len(read_jsonl(evidence_path))
            call_started = time.monotonic()
            completed = subprocess.run(
                [sys.executable, str(root / "scripts" / settings["adapter"])],
                input=json.dumps(adapter_input, sort_keys=True),
                text=True,
                capture_output=True,
                env=env,
                check=False,
            )
            latency_ms = (time.monotonic() - call_started) * 1000
            current = read_jsonl(evidence_path)
            if len(current) != before + 1:
                raise RuntimeError(f"{key}: adapter did not append exactly one evidence row")
            evidence_row = current[-1]
            if (evidence_row.get("system_id"), evidence_row.get("request_id")) != key:
                raise RuntimeError(f"{key}: provider evidence identity mismatch")
            attempts.append(evidence_row)
            evidence[key] = attempts
            if (
                completed.returncode
                and common.retryable_zero_cost_failure(evidence_row)
                and len(attempts) < common.MAX_TRANSPORT_ATTEMPTS
            ):
                time.sleep(min(2 ** (len(attempts) - 1), 4))
                continue
            break

        if completed.returncode:
            failure = {
                "system_id": "mia-v2",
                "request_id": request_id,
                "stage": "adapter",
                "outcome": evidence_row.get("outcome"),
                "attempts": len(attempts),
                "error": completed.stderr.strip()[-2000:],
            }
            common.append_jsonl(failure_path, failure)
            failures[key] = failure
            prediction = failure_prediction(
                provider, adapter_input, evidence_row, latency_ms, failure
            )
            trace = {**prediction, "generation": None, "decision": None}
            common.append_jsonl(prediction_path, prediction)
            common.append_jsonl(trace_path, {"system_id": "mia-v2", "request_id": request_id, **trace})
            predictions[key] = prediction
            traces[key] = trace
            if "hard budget blocks next call" in failure["error"]:
                budget_exhausted = True
                break
            continue

        try:
            raw = json.loads(completed.stdout)
            raw_record = {
                "system_id": "mia-v2",
                "request_id": request_id,
                "raw": raw,
            }
            common.append_jsonl(raw_path, raw_record)
            raw_index[key] = raw_record
            prediction, trace = normalize_success(
                provider, adapter_input, raw, evidence_row, latency_ms, root
            )
        except Exception as exc:
            failure = {
                "system_id": "mia-v2",
                "request_id": request_id,
                "stage": "normalization",
                "error_class": type(exc).__name__,
                "error": str(exc),
            }
            common.append_jsonl(failure_path, failure)
            failures[key] = failure
            prediction = failure_prediction(
                provider, adapter_input, evidence_row, latency_ms, failure
            )
            trace = {**prediction, "generation": None, "decision": None}

        common.append_jsonl(prediction_path, prediction)
        common.append_jsonl(trace_path, {"system_id": "mia-v2", "request_id": request_id, **trace})
        predictions[key] = prediction
        traces[key] = trace

    evidence_rows = [row for rows in evidence.values() for row in rows]
    complete = (
        set(predictions) == expected
        and set(traces) == expected
        and set(evidence) == expected
        and not budget_exhausted
        and not runtime_exhausted
    )
    report = {
        "schema_version": "1.0.0",
        "status": (
            "completed_with_failures" if complete and failures else
            "pass" if complete else
            "fail"
        ),
        "study_id": "mia-v2-posthoc-phase5-regression",
        "provider": provider,
        "model_id": settings["model_id"],
        "expected_provider_calls": EXPECTED_CALLS,
        "provider_evidence_identities": len(evidence),
        "provider_evidence_rows": len(evidence_rows),
        "predictions": len(predictions),
        "traces": len(traces),
        "failures": len(failures),
        "budget_exhausted": budget_exhausted,
        "runtime_exhausted": runtime_exhausted,
        "hard_cap_usd": maximum_spend_usd,
        "observed_cost_usd": round(
            sum(float(row.get("cost_usd", 0) or 0) for row in evidence_rows), 6
        ),
        "predictions_sha256": common.file_hash(prediction_path) if prediction_path.exists() else None,
        "traces_sha256": common.file_hash(trace_path) if trace_path.exists() else None,
        "recorded_at": now(),
    }
    report["report_sha256"] = common.self_hash(report, "report_sha256")
    (output / "run_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=sorted(SETTINGS), required=True)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--maximum-spend-usd", type=float)
    parser.add_argument("--max-runtime-minutes", type=float, default=180.0)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()

    root = args.repo_root.resolve()
    output = args.output_root.resolve()
    if args.prepare_only:
        report = prepare_only(root, output, args.provider)
    else:
        cap = CAPS[args.provider] if args.maximum_spend_usd is None else args.maximum_spend_usd
        report = run(root, output, args.provider, cap, args.max_runtime_minutes)

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] in {"pass", "completed_with_failures"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
