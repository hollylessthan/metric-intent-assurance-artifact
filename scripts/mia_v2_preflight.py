#!/usr/bin/env python3
"""Credential-free preflight for the full MIA-v2 Phase 5 regression."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections import Counter
from pathlib import Path

from mia.registry import Registry
from mia.v2_system import build_adapter_input_v2


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import phase5_prepare


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
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def preflight(repo_root: Path) -> dict:
    benchmark = repo_root / "benchmarks/phase4/final/canonical_cases.v1.1.jsonl"
    with tempfile.TemporaryDirectory(prefix="mia-v2-preflight-") as directory:
        output = Path(directory)
        manifest = phase5_prepare.prepare(repo_root, benchmark, output)
        records = read_jsonl(output / "test.jsonl")

    if len(records) != 720:
        raise AssertionError(f"expected 720 held-out utterances, observed {len(records)}")
    if len({row["case_id"] for row in records}) != 240:
        raise AssertionError("held-out preflight must contain 240 canonical cases")

    registries = {
        domain: Registry.load(repo_root / f"registries/phase4/{domain}/v1.json")
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
            # This is a deterministic payload-size diagnostic, not a token/cost estimate.
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
        "benchmark_sha256": manifest["benchmark_sha256"],
        "cases": 240,
        "utterances": 720,
        "domain_utterances": dict(sorted(Counter(row["domain"] for row in records).items())),
        "providers": provider_stats,
        "total_future_provider_calls": sum(item["calls"] for item in provider_stats.values()),
        "notes": [
            "No provider API is called by this preflight.",
            "Frozen B0-B4 outputs will be reused; only MIA-v2 requires new provider calls.",
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
