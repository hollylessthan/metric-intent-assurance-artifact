#!/usr/bin/env python3
"""Create the versioned Phase 4 benchmark after the frozen human adjudication."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from mia.compilers import DuckDBCompiler, MetricFlowCompiler
from mia.models import Intent
from mia.registry import Registry


def sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def executable_intent(base: dict[str, Any], dimension: str, registry: Registry) -> dict[str, Any]:
    intent = copy.deepcopy(base)
    old_dimensions = set(intent.get("dimensions", []))
    intent["dimensions"] = [dimension]
    intent["output_grain"]["entity"] = registry.dimension(dimension)["entity"]
    intent["provenance"] = [x for x in intent["provenance"] if x not in old_dimensions]
    if dimension not in intent["provenance"]:
        intent["provenance"].append(dimension)
    return intent


def refund_v1_intent(registry: Registry) -> dict[str, Any]:
    return {
        "metrics": ["refund_rate"],
        "dimensions": ["loyalty_tier"],
        "filters": [],
        "time": {
            "calendar_id": "calendar", "completeness": "closed",
            "start": "2026-01-01", "end": "2026-03-31",
            "temporal_grain": "month", "timezone": "UTC"
        },
        "output_grain": {"entity": registry.dimension("loyalty_tier")["entity"], "temporal": "month"},
        "comparison": None,
        "ordering": [],
        "limit": None,
        "version_policy": "explicit",
        "metric_versions": {"refund_rate": "refund_rate.v1"},
        "subject_scope": {},
        "provenance": ["refund_rate", "refund_rate.v1", "loyalty_tier", "calendar"],
    }


def validate_intent(intent: dict[str, Any], registry: Registry) -> None:
    parsed = Intent.from_dict(intent)
    MetricFlowCompiler().compile(parsed, registry, explain=False)
    DuckDBCompiler().compile(parsed, registry)


def finalize(repo_root: Path, output_root: Path) -> dict[str, Any]:
    source = repo_root / "benchmarks/phase4/canonical_cases.jsonl"
    decisions_path = repo_root / "benchmarks/phase4/adjudication/human_validation_v1.json"
    decisions = json.loads(decisions_path.read_text(encoding="utf-8"))
    if sha256(source) != decisions["source_benchmark_sha256"]:
        raise RuntimeError("frozen benchmark hash does not match the adjudication manifest")

    cases = read_jsonl(source)
    by_id = {case["case_id"]: case for case in cases}
    if len(by_id) != len(cases):
        raise RuntimeError("duplicate canonical case id")
    registries = {
        domain: Registry.load(repo_root / f"registries/phase4/{domain}/v1.json")
        for domain in ("saas", "commerce", "support")
    }
    retired_groups: dict[str, dict[str, str]] = {}
    changes = []

    for correction in decisions["corrections"]:
        case = by_id.get(correction["case_id"])
        if case is None:
            raise RuntimeError(f"unknown adjudicated case: {correction['case_id']}")
        original_action = case["gold_action"]
        original_reason = case["primary_reason_code"]
        registry = registries[case["domain"]]
        group = case.get("contrastive_group")

        if correction["new_action"] == "execute":
            if case.get("candidate_intents"):
                intent = executable_intent(case["candidate_intents"][0], correction["dimension"], registry)
            elif correction["case_id"] == "commerce-coveragegap-020":
                intent = refund_v1_intent(registry)
            else:
                raise RuntimeError(f"cannot construct adjudicated intent for {case['case_id']}")
            validate_intent(intent, registry)
            for key in ("alternatives", "candidate_intents", "clarification_question", "distinguishing_slot", "missing_capability"):
                case.pop(key, None)
            case["gold_intents"] = [intent]
            case["execution_oracle"] = {
                "expected_status": "compile_and_execute_on_generated_phase4_fixtures",
                "targets": ["metricflow", "duckdb"],
            }
            case["template_family"] = f"{case['domain']}/execute/human_adjudicated"
        elif correction["new_action"] == "coverage_gap" and correction["new_reason_code"] == "GAP_METRIC":
            case["missing_capability"]["code"] = "GAP_METRIC"
            case["template_family"] = f"{case['domain']}/coverage_gap/missing_metric"
        else:
            raise RuntimeError(f"unsupported correction for {case['case_id']}")

        case["gold_action"] = correction["new_action"]
        case["primary_reason_code"] = correction["new_reason_code"]
        case["annotation_status"] = "human_adjudicated"
        case["adjudication"] = {
            "protocol_version": decisions["schema_version"],
            "request_id": correction["request_id"],
            "original_action": original_action,
            "original_reason_code": original_reason,
            "decision": correction["new_action"],
            "reason_code": correction["new_reason_code"],
            "note": correction["note"],
        }
        if group and original_action != correction["new_action"]:
            change = case.get("contrastive_change", {})
            retired_groups[group] = {
                "source_case_id": change.get("source_case_id", ""),
                "target_case_id": case["case_id"],
                "reason": "human adjudication removed the action contrast",
            }
        changes.append({
            "request_id": correction["request_id"], "case_id": case["case_id"],
            "from": {"action": original_action, "reason_code": original_reason},
            "to": {"action": case["gold_action"], "reason_code": case["primary_reason_code"]},
        })

    for group, retirement in retired_groups.items():
        members = [case for case in cases if case.get("contrastive_group") == group]
        if len(members) != 2:
            raise RuntimeError(f"cannot retire malformed contrastive group {group}")
        for case in members:
            case.pop("contrastive_group", None)
            case.pop("contrastive_change", None)
            case["contrastive_adjudication"] = {
                "status": "retired", "group": group, "reason": retirement["reason"]
            }

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        if case.get("contrastive_group"):
            groups[case["contrastive_group"]].append(case)
    for group, members in groups.items():
        if len(members) != 2 or Counter(x["gold_action"] for x in members)["execute"] != 1:
            raise RuntimeError(f"invalid final contrastive group: {group}")

    action_counts = Counter(case["gold_action"] for case in cases)
    if dict(action_counts) != {"execute": 125, "clarify": 56, "reject": 60, "coverage_gap": 59}:
        raise RuntimeError(f"unexpected adjudicated action counts: {dict(action_counts)}")
    if len(groups) != 116:
        raise RuntimeError(f"expected 116 valid contrastive groups, found {len(groups)}")

    target_actions: Counter[str] = Counter()
    target_reasons: Counter[str] = Counter()
    target_domains: Counter[str] = Counter()
    for members in groups.values():
        target = next(case for case in members if case["gold_action"] != "execute")
        target_actions[target["gold_action"]] += 1
        target_reasons[target["primary_reason_code"]] += 1
        target_domains[target["domain"]] += 1

    final_cases = output_root / "canonical_cases.v1.1.jsonl"
    write_jsonl(final_cases, cases)
    adjudication_report = {
        "schema_version": "1.0.0",
        "status": "pass",
        "source_benchmark_sha256": sha256(source),
        "adjudication_manifest_sha256": sha256(decisions_path),
        "final_benchmark_sha256": sha256(final_cases),
        "case_count": len(cases),
        "action_counts": dict(sorted(action_counts.items())),
        "human_audit": decisions["human_audit"],
        "corrections": changes,
        "retired_contrastive_groups": retired_groups,
        "stability_review": decisions["stability_review"],
    }
    distinctiveness_report = {
        "schema_version": "1.0.0",
        "status": "pass",
        "gate": "at_least_100_adjudicated_single-feature_contrastive_groups",
        "threshold": 100,
        "valid_groups": len(groups),
        "retired_groups": len(retired_groups),
        "target_action_counts": dict(sorted(target_actions.items())),
        "target_reason_counts": dict(sorted(target_reasons.items())),
        "target_domain_counts": dict(sorted(target_domains.items())),
        "finding": (
            "Each valid group pairs an executable intent with a single-feature mutation that requires "
            "Clarify or Reject. Successful execution of the anchor therefore cannot detect the paired "
            "semantic or governance failure; intent assurance supplies distinct failure information."
        ),
        "model_diagnostic_note": (
            "Provider interpretations of the execution_accuracy_insufficient review field diverged, so that "
            "field is retained as a diagnostic and is not used as the completion gate."
        ),
    }
    write_json(output_root / "adjudication_report.json", adjudication_report)
    write_json(output_root / "distinctiveness_report.json", distinctiveness_report)
    return {"adjudication": adjudication_report, "distinctiveness": distinctiveness_report}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--output-root", type=Path, default=Path("benchmarks/phase4/final"))
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    output_root = args.output_root if args.output_root.is_absolute() else repo_root / args.output_root
    try:
        result = finalize(repo_root, output_root)
    except RuntimeError as exc:
        print(f"phase4 finalization error: {exc}")
        return 2
    print(json.dumps({
        "status": result["adjudication"]["status"],
        "final_benchmark_sha256": result["adjudication"]["final_benchmark_sha256"],
        "valid_distinctiveness_groups": result["distinctiveness"]["valid_groups"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
