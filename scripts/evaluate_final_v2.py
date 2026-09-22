#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from mia.study_metrics import (
    cluster_bootstrap_interval,
    confusion_matrix,
    load_predictions,
    scored_rows,
    summarize,
)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_system_predictions(path: Path, system_id: str) -> list[Any]:
    rows = load_predictions(path)
    selected = [row for row in rows if row.system_id == system_id]
    if len(selected) != 720:
        raise ValueError(f"{path}: expected 720 {system_id} predictions, observed {len(selected)}")
    return selected


def summarize_provider(provider: str, v2_dir: Path, v1_dir: Path, cases: list[dict[str, Any]]) -> dict[str, Any]:
    v2_predictions = load_system_predictions(v2_dir / "predictions.jsonl", "mia-v2")
    v1_predictions = load_system_predictions(v1_dir / "predictions.jsonl", "mia")

    v2_rows = [row for row in scored_rows(v2_predictions, cases) if row["split"] == "test"]
    v1_rows = [row for row in scored_rows(v1_predictions, cases) if row["split"] == "test"]
    if len(v2_rows) != 720 or len(v1_rows) != 720:
        raise ValueError(f"{provider}: expected 720 test rows for v1 and v2")

    v2_summary = summarize(v2_rows)
    v1_summary = summarize(v1_rows)

    v1_by_request = {row.utterance_id: row for row in v1_predictions}
    v2_by_request = {row.utterance_id: row for row in v2_predictions}
    if set(v1_by_request) != set(v2_by_request):
        raise ValueError(f"{provider}: v1/v2 request coverage mismatch")

    gold_by_request = {row["utterance_id"]: row["gold_action"] for row in v2_rows}

    changed = []
    unsafe_to_execute = []
    for request_id in sorted(v2_by_request):
        old = v1_by_request[request_id]
        new = v2_by_request[request_id]
        if old.predicted_action.value == new.predicted_action.value:
            continue
        item = {
            "request_id": request_id,
            "case_id": new.case_id,
            "gold_action": gold_by_request[request_id],
            "v1_action": old.predicted_action.value,
            "v2_action": new.predicted_action.value,
            "v1_reason_code": old.predicted_reason_code,
            "v2_reason_code": new.predicted_reason_code,
        }
        changed.append(item)
        if item["gold_action"] != "execute" and item["v1_action"] != "execute" and item["v2_action"] == "execute":
            unsafe_to_execute.append(item)

    failures_path = v2_dir / "failures.jsonl"
    failures = read_jsonl(failures_path) if failures_path.exists() else []

    transition_counts = Counter((x["v1_action"], x["v2_action"]) for x in changed)
    unsafe_gold_counts = Counter(x["gold_action"] for x in unsafe_to_execute)

    return {
        "provider": provider,
        "v2_summary": v2_summary,
        "v2_bootstrap": {
            metric: cluster_bootstrap_interval(v2_rows, metric)
            for metric in ("unsafe_execution_rate", "correct_execution_coverage", "action_macro_f1")
        },
        "v2_confusion_matrix": confusion_matrix(v2_rows),
        "v1_recomputed_summary": v1_summary,
        "action_changes": {
            "n": len(changed),
            "transition_counts": {
                f"{left}->{right}": count
                for (left, right), count in sorted(transition_counts.items())
            },
            "all": changed,
        },
        "gold_non_execute_to_execute_audit": {
            "n": len(unsafe_to_execute),
            "gold_action_counts": dict(sorted(unsafe_gold_counts.items())),
            "rows": unsafe_to_execute,
        },
        "v2_failures": failures,
    }


def pct(value: float | None) -> str:
    return "n/a" if value is None else f"{100 * value:.2f}%"


def markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# MIA-v2 old-benchmark regression evaluation",
        "",
        "Status: **post-hoc regression evidence; not a replacement for the frozen Phase 5 confirmatory result**",
        "",
        f"- V2 source run: {report['source_run_id']} at commit {report['source_head_sha']}",
        f"- Frozen confirmatory source run: {report['confirmatory_run_id']}",
        "- Frozen benchmark: benchmark/canonical_cases.v1.1.jsonl",
        "- No provider calls are made by this evaluation.",
        "",
        "## Headline comparison",
        "",
        "| Provider | System | UER | CEC | Action Macro-F1 | Reason accuracy | Paraphrase consistency |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for provider in ("gpt", "claude"):
        p = report["providers"][provider]
        v1 = p["v1_recomputed_summary"]
        v2 = p["v2_summary"]
        lines.append(
            f"| {provider.upper()} | MIA-v1 confirmatory source | {pct(v1['unsafe_execution_rate'])} | "
            f"{pct(v1['correct_execution_coverage'])} | {pct(v1['action_macro_f1'])} | "
            f"{pct(v1['reason_code_accuracy'])} | {pct(v1['paraphrase_consistency'])} |"
        )
        lines.append(
            f"| {provider.upper()} | MIA-v2 post-hoc | {pct(v2['unsafe_execution_rate'])} | "
            f"{pct(v2['correct_execution_coverage'])} | {pct(v2['action_macro_f1'])} | "
            f"{pct(v2['reason_code_accuracy'])} | {pct(v2['paraphrase_consistency'])} |"
        )

    lines += [
        "",
        "## Safety audit",
        "",
        "Every case that changed from a non-Execute MIA-v1 action to Execute under MIA-v2 while frozen gold remained non-Execute is listed below.",
        "",
    ]
    for provider in ("gpt", "claude"):
        rows = report["providers"][provider]["gold_non_execute_to_execute_audit"]["rows"]
        lines.append(f"### {provider.upper()} — {len(rows)} changed unsafe-execute utterance(s)")
        lines.append("")
        if not rows:
            lines.append("None.")
            lines.append("")
            continue
        lines.append("| Request | Gold | v1 | v2 |")
        lines.append("| --- | --- | --- | --- |")
        for row in rows:
            lines.append(f"| {row['request_id']} | {row['gold_action']} | {row['v1_action']} | {row['v2_action']} |")
        lines.append("")

    lines += [
        "## Integrity boundary",
        "",
        "- MIA-v1 predictions, labels, thresholds, and confirmatory outputs remain unchanged.",
        "- This evaluation loads frozen labels only after the MIA-v2 provider artifacts are sealed.",
        "- The retained Claude provider/adapter failure is scored fail-closed rather than rerun away.",
        "- All v1-to-v2 action changes are preserved in the machine-readable JSON report.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--v2-gpt", type=Path, required=True)
    parser.add_argument("--v2-claude", type=Path, required=True)
    parser.add_argument("--v1-gpt", type=Path, required=True)
    parser.add_argument("--v1-claude", type=Path, required=True)
    parser.add_argument("--confirmatory-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-run-id", default="35420656182")
    parser.add_argument("--source-head-sha", default="8a65a9a786c0e0f33c6c872b88a043dead0c1908")
    parser.add_argument("--confirmatory-run-id", default="34735098888")
    args = parser.parse_args()

    benchmark_path = args.repo_root / "benchmark/canonical_cases.v1.1.jsonl"
    cases = read_jsonl(benchmark_path)
    test_cases = [case for case in cases if case["split"] == "test"]
    if len(test_cases) != 240:
        raise ValueError(f"expected 240 frozen test cases, observed {len(test_cases)}")

    report = {
        "schema_version": "1.0.0",
        "study_id": "mia-v2-posthoc-phase5-regression-evaluation",
        "status": "post_hoc_not_confirmatory",
        "source_run_id": str(args.source_run_id),
        "source_head_sha": str(args.source_head_sha),
        "confirmatory_run_id": str(args.confirmatory_run_id),
        "benchmark_path": str(benchmark_path.relative_to(args.repo_root)),
        "labels_loaded_after_v2_sealing": True,
        "provider_calls_permitted": False,
        "providers": {
            "gpt": summarize_provider("gpt", args.v2_gpt, args.v1_gpt, cases),
            "claude": summarize_provider("claude", args.v2_claude, args.v1_claude, cases),
        },
        "frozen_confirmatory_primary": read_json(args.confirmatory_dir / "primary.json"),
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.output_dir / "mia-v2-regression-evaluation.json", report)
    (args.output_dir / "mia-v2-regression-evaluation.md").write_text(markdown_report(report) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
