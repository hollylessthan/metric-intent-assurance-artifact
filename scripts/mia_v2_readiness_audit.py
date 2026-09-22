#!/usr/bin/env python3
"""Credential-free MIA-v2 representability/readiness audit over frozen Phase 5 gold intents."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from mia.models import Context, Intent
from mia.registry import Registry
from mia.v2_canonicalization import MixedEntityGrouping, canonicalize_model_intent_v2


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def semantic_payload_from_gold(intent: dict[str, Any]) -> dict[str, Any]:
    """Project a frozen gold intent into the smaller v2 model-facing contract.

    This is an offline representability audit only. Gold is never exposed to a provider.
    """
    return {
        "metrics": list(intent["metrics"]),
        "dimensions": list(intent["dimensions"]),
        "filters": list(intent["filters"]),
        "time": {
            "start": intent["time"]["start"],
            "end": intent["time"]["end"],
            "temporal_grain": intent["time"]["temporal_grain"],
            # Preserve the adjudicated calendar for this structural audit.
            # The provider-facing prompt still omits the default unless explicit.
            "calendar_id": intent["time"]["calendar_id"],
        },
        "explicit_metric_versions": (
            {key: value for key, value in intent["metric_versions"].items() if value}
            if intent["version_policy"] == "explicit"
            else {}
        ),
        "unresolved_explicit_version_metrics": (
            sorted(key for key, value in intent["metric_versions"].items() if not value)
            if intent["version_policy"] == "explicit"
            else []
        ),
        "ordering": list(intent["ordering"]),
        "limit": intent["limit"],
    }


def _semantic_projection(intent: dict[str, Any]) -> dict[str, Any]:
    """Fields v2 is expected to preserve/derive exactly for representable intents."""
    return {
        "metrics": intent["metrics"],
        "dimensions": intent["dimensions"],
        "filters": intent["filters"],
        "time": intent["time"],
        "output_grain": intent["output_grain"],
        "comparison": intent["comparison"],
        "ordering": intent["ordering"],
        "limit": intent["limit"],
        "version_policy": intent["version_policy"],
        "metric_versions": intent["metric_versions"],
        "subject_scope": intent["subject_scope"],
        "provenance": sorted(set(intent["provenance"])),
    }


def audit(repo_root: Path) -> dict[str, Any]:
    benchmark_path = repo_root / "benchmark/canonical_cases.v1.1.jsonl"
    cases = [row for row in read_jsonl(benchmark_path) if row["split"] == "test"]
    if len(cases) != 240:
        raise AssertionError(f"expected 240 held-out cases, observed {len(cases)}")

    registries = {
        domain: Registry.load(repo_root / f"registries/{domain}.json")
        for domain in sorted({row["domain"] for row in cases})
    }

    rows: list[dict[str, Any]] = []
    action_counts = Counter()
    mixed_counts = Counter()
    unexpected_errors: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    audited_gold_intents = 0

    for case in cases:
        action_counts[case["gold_action"]] += 1
        registry = registries[case["domain"]]
        context = Context.from_dict(case["context"])

        for index, gold in enumerate(case.get("gold_intents", [])):
            audited_gold_intents += 1
            record = {
                "case_id": case["case_id"],
                "domain": case["domain"],
                "gold_action": case["gold_action"],
                "gold_intent_index": index,
            }
            payload = semantic_payload_from_gold(gold)
            try:
                reconstructed = canonicalize_model_intent_v2(
                    payload, registry=registry, context=context
                ).canonical()
            except MixedEntityGrouping as exc:
                mixed_counts[case["gold_action"]] += 1
                rows.append({
                    **record,
                    "status": "mixed_entity_deferred",
                    "detail": str(exc),
                    "dimensions": list(gold["dimensions"]),
                })
                continue
            except Exception as exc:
                error = {
                    **record,
                    "status": "unexpected_error",
                    "error_class": type(exc).__name__,
                    "detail": str(exc),
                }
                unexpected_errors.append(error)
                rows.append(error)
                continue

            # Compare canonical representations on both sides. Frozen gold
            # dimensions are semantically unordered, while Intent.canonical()
            # sorts them; comparing canonical output to raw gold would create
            # false mismatches based only on list order.
            expected = _semantic_projection(Intent.from_dict(gold).canonical())
            actual = _semantic_projection(reconstructed)
            if actual != expected:
                differing = sorted(
                    key for key in expected if expected.get(key) != actual.get(key)
                )
                mismatch = {
                    **record,
                    "status": "mismatch",
                    "differing_fields": differing,
                }
                mismatches.append(mismatch)
                rows.append(mismatch)
            else:
                rows.append({**record, "status": "exact_reconstruction"})

    status_counts = Counter(row["status"] for row in rows)
    blockers = len(unexpected_errors) + len(mismatches)
    return {
        "schema_version": "1.0.0",
        "status": "pass" if blockers == 0 else "fail",
        "provider_calls_permitted": False,
        "heldout_cases": len(cases),
        "heldout_utterances": sum(len(case["utterances"]) for case in cases),
        "case_action_counts": dict(sorted(action_counts.items())),
        "audited_gold_intents": audited_gold_intents,
        "status_counts": dict(sorted(status_counts.items())),
        "mixed_entity_deferred_by_gold_action": dict(sorted(mixed_counts.items())),
        "unexpected_error_count": len(unexpected_errors),
        "mismatch_count": len(mismatches),
        "blocker_count": blockers,
        "rows": rows,
        "notes": [
            "This audit projects frozen gold intents offline; gold is never sent to a model.",
            "mixed_entity_deferred is expected fail-closed behavior until semantic-compiler capability is proven.",
            "Only unexpected canonicalization errors or representable-intent mismatches are readiness blockers.",
            "This audit does not estimate provider quality and does not authorize paid inference.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    report = audit(args.repo_root.resolve())
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
