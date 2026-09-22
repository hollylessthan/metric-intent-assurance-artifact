from __future__ import annotations

import argparse
import json
from pathlib import Path

from .assurance import Assurer
from .compilers import DuckDBCompiler, MetricFlowCompiler
from .contracts import validate_candidate_payload, validate_context_payload
from .models import Candidate, Context, Intent, MissingCapability
from .registry import Registry


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("registry")
    parser.add_argument("request", help="JSON file containing context and frozen candidate outputs")
    parser.add_argument("--compile", choices=("metricflow", "duckdb"))
    args = parser.parse_args()
    registry = Registry.load(args.registry)
    payload = json.loads(Path(args.request).read_text())
    validate_context_payload(payload["context"])
    context = Context.from_dict(payload["context"])
    for item in payload.get("candidates", []):
        validate_candidate_payload(item)
    candidates = [
        Candidate(Intent.from_dict(x["intent"]), x["support"], tuple(x.get("evidence", [])))
        for x in payload.get("candidates", [])
    ]
    missing = payload.get("missing_capability")
    missing_capability = (
        MissingCapability(missing["code"], missing["concept"], tuple(missing.get("evidence", [])))
        if missing
        else None
    )
    decision = Assurer(**payload.get("thresholds", {})).decide(
        candidates,
        registry,
        context,
        missing_capability=missing_capability,
        outside_contract=payload.get("outside_contract", False),
        generator_id=payload.get("generator_id", "frozen-cli-input"),
        request_id=payload.get("request_id"),
    )
    result = decision.to_dict()
    if args.compile and decision.intent:
        compiler = MetricFlowCompiler() if args.compile == "metricflow" else DuckDBCompiler()
        compiled = compiler.compile(decision.intent, registry)
        result["compilation"] = {
            "backend": compiled.backend,
            "artifact": compiled.artifact,
            "intent_hash": compiled.intent_hash,
            "registry_hash": compiled.registry_hash,
            "capabilities": compiled.capabilities,
        }
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
