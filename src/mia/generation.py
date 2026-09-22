from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .contracts import ContractError, validate_candidate_payload
from .models import Candidate, Context, Intent, MissingCapability
from .registry import Registry


GAP_CODES = {
    "GAP_METRIC", "GAP_FILTER_CONCEPT", "GAP_DIMENSION", "GAP_ENTITY_RELATION",
    "GAP_CALENDAR_RULE", "GAP_VERSION_HISTORY", "GAP_COMPOSITION", "GAP_POLICY_METADATA",
}


@dataclass(frozen=True)
class GenerationResult:
    candidates: tuple[Candidate, ...]
    missing_capability: MissingCapability | None = None
    outside_contract: bool = False
    generator_id: str = "unknown"
    request_id: str | None = None


class CandidateGenerator(Protocol):
    """Replaceable model boundary used by B1/B2/B4 and the proposed system."""

    def generate(self, request: str, registry: Registry, context: Context) -> GenerationResult: ...


class RecordedCandidateGenerator:
    """Replays frozen model outputs without paid or nondeterministic calls."""

    def __init__(self, records: dict[str, dict], *, generator_id: str = "recorded"):
        self.records = records
        self.generator_id = generator_id

    @classmethod
    def load(cls, path: str | Path, *, generator_id: str = "recorded") -> "RecordedCandidateGenerator":
        rows = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
        request_ids = [row.get("request_id") for row in rows]
        if any(not isinstance(request_id, str) or not request_id for request_id in request_ids):
            raise ContractError("every generation record requires a non-empty request_id")
        if len(request_ids) != len(set(request_ids)):
            raise ContractError("generation record request_id values must be unique")
        return cls({x["request_id"]: x for x in rows}, generator_id=generator_id)

    def generate(self, request: str, registry: Registry, context: Context) -> GenerationResult:
        record = self.records[request]
        expected_hash = record.get("registry_hash")
        if expected_hash and expected_hash != registry.snapshot_hash:
            raise ValueError("recorded candidates were generated against a different registry snapshot")
        raw_candidates = record.get("candidates", [])
        if not isinstance(raw_candidates, list):
            raise ContractError("generation record candidates must be an array")
        for item in raw_candidates:
            validate_candidate_payload(item)
        candidates = tuple(
            Candidate(Intent.from_dict(x["intent"]), x["support"], tuple(x.get("evidence", [])))
            for x in raw_candidates
        )
        missing = record.get("missing_capability")
        if missing is not None:
            if not isinstance(missing, dict) or not isinstance(missing.get("code"), str) or not isinstance(missing.get("concept"), str):
                raise ContractError("generation record missing_capability is malformed")
            if missing["code"] not in GAP_CODES or not missing["concept"]:
                raise ContractError("generation record missing_capability must use a frozen GAP code and concept")
        if not isinstance(record.get("outside_contract", False), bool):
            raise ContractError("generation record outside_contract must be boolean")
        return GenerationResult(
            candidates,
            MissingCapability(missing["code"], missing["concept"], tuple(missing.get("evidence", []))) if missing else None,
            bool(record.get("outside_contract", False)),
            self.generator_id,
            request,
        )
