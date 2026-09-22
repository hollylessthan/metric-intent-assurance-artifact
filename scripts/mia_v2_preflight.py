#!/usr/bin/env python3
"""Credential-free preflight for the packaged MIA-v2 held-out evaluation."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from mia.registry import Registry
from mia.v2_system import build_adapter_input_v2


PROVIDERS = {
    "gpt": {
        "model_id": "gpt-5.4-mini-2026-03-17",
        "decoding": {
            "max_output_tokens": 1200,
            "reasoning_effort": "none",
            "temperature": 0,
        },
    },
    "claude": {
        "model_id": "claude-sonnet-5",
        "decoding": {
            "max_output_tokens": 1200,
            "reasoning_effort": "low",
            "temperature": None,
        },
    },
}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def heldout_records(cases: list[dict]) -> list[dict]:
    records = []
    for case in cases:
        if case["split"] != "test":
            continue
        registry_hash = case["provenance"]["registry_hash"]
        for position, request in enumerate(case["utterances"]):
            utterance_id = f"{case['case_id']}#u{position}"
            records.append({
                "request_id": utterance_id,
                "case_id": case["case_id"],
                "utterance_id": utterance_id,
                "domain": case["domain"],
                "request": request,
                "context": case["context"],
                "registry_hash": registry_hash,
            })
    return records


def preflight(repo_root: Path) -> dict:
    benchmark = repo_root / "benchmark/canonical_cases.v1.1.jsonl"
    cases = read_jsonl(benchmark)
    records = heldout_records(cases)

    if len(records) != 720:
        raise AssertionError(f"expected 720 held-out utterances, observed {len(records)}")
    if len({row["case_id"] for row in records}) != 240:
        raise AssertionError("held-out preflight must contain 240 canonical cases")

    registries = {
        domain: Registry.load(repo_root / f"registries/{domain}.json")
        for domain in sorted({row["domain"] for row in records})
    }

    provider_stats = {}
    for provider, settings in PROVIDERS.items():
        input_chars = []
        for record in records:
            registry = registries[record["domain"]]
            adapter = build_adapter_input_v2(
                record,
                registry,
                provider=provider,
                model_id=settings["model_id"],
                decoding=settings["decoding"],
                prompts_root=repo_root / "prompts/v2",
            )
            input_chars.append(len(json.dumps(adapter, sort_keys=True, separators=(",", ":"))))
        provider_stats[provider] = {
            "model_id": settings["model_id"],
            "calls": len(records),
            "max_output_tokens_per_call": settings["decoding"]["max_output_tokens"],
            "adapter_input_chars": {
                "min": min(input_chars),
                "max": max(input_chars),
                "mean": sum(input_chars) / len(input_chars),
            },
        }

    return {
        "schema_version": "1.0.0",
        "status": "pass",
        "provider_calls_permitted": False,
        "benchmark_sha256": sha256(benchmark),
        "cases": 240,
        "utterances": 720,
        "domain_utterances": dict(sorted(Counter(row["domain"] for row in records).items())),
        "providers": provider_stats,
        "total_future_provider_calls": sum(item["calls"] for item in provider_stats.values()),
        "notes": [
            "No provider API is called by this preflight.",
            "Historical baseline outputs are frozen; this check validates the packaged MIA-v2 held-out request surface.",
            "Character counts are payload diagnostics only and must not be reported as token or dollar estimates.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = preflight(args.repo_root.resolve())
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
