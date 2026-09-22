from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .models import Intent
from .registry import Registry


def load_jsonl(path: str | Path) -> list[dict]:
    rows = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    ids = [x["case_id"] for x in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("case_id must be unique")
    return rows


def assert_grouped_splits(rows: list[dict]) -> None:
    for field in ("paraphrase_group", "counterfactual_group", "template_family"):
        groups: dict[str, set[str]] = {}
        for row in rows:
            if row.get(field):
                groups.setdefault(row[field], set()).add(row["split"])
        leaking = [group for group, splits in groups.items() if len(splits) > 1]
        if leaking:
            raise ValueError(f"{field} leakage across splits: {leaking}")


def compile_gold_executes(rows: list[dict], registry: Registry, compilers: Iterable[object]) -> dict[str, dict]:
    """Phase 3 exit gate: every gold Execute intent compiles on both targets."""
    results: dict[str, dict] = {}
    for row in rows:
        if row["gold_action"] != "execute" or not row.get("gold_intents"):
            continue
        results[row["case_id"]] = {}
        for intent_payload in row["gold_intents"]:
            intent = Intent.from_dict(intent_payload)
            for compiler in compilers:
                compiled = compiler.compile(intent, registry)
                results[row["case_id"]].setdefault(compiled.backend, []).append({
                    "intent_hash": compiled.intent_hash,
                    "registry_hash": compiled.registry_hash,
                    "capabilities": compiled.capabilities,
                })
    return results
