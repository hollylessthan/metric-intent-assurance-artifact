from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any

from .contracts import validate_context_payload, validate_intent_payload


class Action(StrEnum):
    EXECUTE = "execute"
    CLARIFY = "clarify"
    REJECT = "reject"
    COVERAGE_GAP = "coverage_gap"


@dataclass(frozen=True)
class Context:
    role: str
    org_scope: tuple[str, ...] = ()
    calendar_default: str | None = None
    timezone: str = "UTC"

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Context":
        validate_context_payload(value)
        copied = dict(value)
        copied["org_scope"] = tuple(copied.get("org_scope", ()))
        return cls(**copied)


@dataclass(frozen=True)
class Intent:
    """Backend-independent identity of a governed metric request."""

    metrics: tuple[str, ...]
    dimensions: tuple[str, ...] = ()
    filters: tuple[dict[str, Any], ...] = ()
    time: dict[str, Any] = field(default_factory=dict)
    output_grain: dict[str, str] = field(default_factory=dict)
    comparison: dict[str, Any] | None = None
    ordering: tuple[dict[str, str], ...] = ()
    limit: int | None = None
    version_policy: str = "effective_time"
    metric_versions: dict[str, str] = field(default_factory=dict)
    subject_scope: dict[str, Any] = field(default_factory=dict)
    provenance: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Intent":
        validate_intent_payload(value)
        copied = dict(value)
        for key in ("metrics", "dimensions", "filters", "ordering", "provenance"):
            copied[key] = tuple(copied.get(key, ()))
        return cls(**copied)

    def canonical(self) -> dict[str, Any]:
        """Canonical audit representation, including lineage/provenance evidence."""
        value = asdict(self)
        value["metrics"] = sorted(value["metrics"])
        value["dimensions"] = sorted(value["dimensions"])
        # Repeated identical row predicates are idempotent. Collapse them so a
        # duplicate parse cannot manufacture a distinct semantic class.
        filters = {
            json.dumps(item, sort_keys=True, separators=(",", ":"), default=str): item
            for item in value["filters"]
        }
        value["filters"] = [filters[key] for key in sorted(filters)]
        value["ordering"] = list(value["ordering"])
        value["metric_versions"] = dict(sorted(value["metric_versions"].items()))
        value["subject_scope"] = dict(sorted(value["subject_scope"].items()))
        value["provenance"] = sorted(set(value["provenance"]))
        return value

    def semantic_canonical(self) -> dict[str, Any]:
        """Canonical meaning used to collapse candidate interpretations.

        Provenance is evidence about how an interpretation was produced, not part
        of the interpretation itself. Keeping it out of this representation avoids
        false ambiguity when two generators reach the same meaning by different
        valid evidence paths.
        """
        value = self.canonical()
        value.pop("provenance", None)
        return value

    @staticmethod
    def _hash(value: dict[str, Any]) -> str:
        payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
        return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()

    @property
    def equivalence_key(self) -> str:
        return self._hash(self.semantic_canonical())

    @property
    def audit_hash(self) -> str:
        return self._hash(self.canonical())


@dataclass(frozen=True)
class Candidate:
    intent: Intent
    support: float
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if isinstance(self.support, bool) or not isinstance(self.support, (int, float)):
            raise ValueError("candidate support must be numeric")
        if not math.isfinite(self.support) or not 0 <= self.support <= 1:
            raise ValueError("candidate support must be finite and between 0 and 1")


@dataclass(frozen=True)
class MissingCapability:
    code: str
    concept: str
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class Violation:
    family: str
    code: str
    message: str
    action: Action
    object_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class Decision:
    action: Action
    reason_code: str
    intent: Intent | None = None
    question: str | None = None
    missing_concept: str | None = None
    violations: tuple[Violation, ...] = ()
    confidence: float = 0.0
    trace: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
