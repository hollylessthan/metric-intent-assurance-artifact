from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from .registry import Registry


_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _normalize(text: str) -> str:
    return " ".join(_TOKEN_RE.findall(text.lower().replace("_", " ")))


def _tokens(text: str) -> set[str]:
    return set(_normalize(text).split())


@dataclass(frozen=True)
class DiscoveryHit:
    object_id: str
    family: str
    score: float
    matched_on: tuple[str, ...]
    object: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "object_id": self.object_id,
            "family": self.family,
            "score": self.score,
            "matched_on": list(self.matched_on),
            "object": deepcopy(self.object),
        }


class RegistryDiscovery:
    """Deterministic discovery layer for MIA v2.

    The discovery layer does not decide the governed action and does not invent
    registry IDs. It only exposes canonical objects already present in the
    immutable registry snapshot.
    """

    def __init__(self, registry: Registry):
        self.registry = registry

    def list_metrics(self) -> list[dict[str, Any]]:
        return [
            {
                "id": item["id"],
                "name": item["name"],
                "aliases": list(item.get("aliases", [])),
                "description": item.get("description"),
                "entity": item["entity"],
                "allowed_dimensions": list(item.get("allowed_dimensions", [])),
                "allowed_grains": list(item.get("allowed_grains", [])),
                "allowed_calendars": list(item.get("allowed_calendars", [])),
                "versions": deepcopy(item.get("versions", [])),
            }
            for item in self.registry.data.get("metrics", [])
            if item.get("active", True)
        ]

    def search_metrics(self, request: str, *, limit: int = 8) -> list[DiscoveryHit]:
        return self._search("metrics", request, limit=limit)

    def list_dimensions(
        self,
        metric_ids: tuple[str, ...] | list[str] | None = None,
        *,
        common_only: bool = True,
    ) -> list[dict[str, Any]]:
        dimensions = self.registry.data.get("dimensions", [])
        if not metric_ids:
            return [deepcopy(item) for item in dimensions]

        metrics = [self.registry.metric(metric_id) for metric_id in metric_ids]
        if any(metric is None for metric in metrics):
            unknown = [metric_id for metric_id, metric in zip(metric_ids, metrics) if metric is None]
            raise ValueError(f"unknown metric ids for discovery: {unknown}")

        allowed_sets = [set(metric.get("allowed_dimensions", [])) for metric in metrics if metric]
        if common_only:
            allowed = set.intersection(*allowed_sets) if allowed_sets else set()
        else:
            allowed = set.union(*allowed_sets) if allowed_sets else set()
        return [deepcopy(item) for item in dimensions if item["id"] in allowed]

    def search_dimensions(
        self,
        request: str,
        *,
        metric_ids: tuple[str, ...] | list[str] | None = None,
        common_only: bool = True,
        limit: int = 12,
    ) -> list[DiscoveryHit]:
        allowed = {
            item["id"] for item in self.list_dimensions(metric_ids, common_only=common_only)
        }
        return [
            hit for hit in self._search("dimensions", request, limit=None)
            if hit.object_id in allowed
        ][:limit]

    def relevant_entity_paths(
        self,
        metric_ids: tuple[str, ...] | list[str],
        dimension_ids: tuple[str, ...] | list[str],
    ) -> list[dict[str, Any]]:
        metrics = [self.registry.metric(metric_id) for metric_id in metric_ids]
        dimensions = [self.registry.dimension(dimension_id) for dimension_id in dimension_ids]
        if any(item is None for item in metrics):
            raise ValueError("entity-path discovery received an unknown metric id")
        if any(item is None for item in dimensions):
            raise ValueError("entity-path discovery received an unknown dimension id")

        result: dict[str, dict[str, Any]] = {}
        for metric in metrics:
            assert metric is not None
            for dimension in dimensions:
                assert dimension is not None
                if metric["entity"] == dimension["entity"]:
                    synthetic = {
                        "id": f"identity:{metric['entity']}",
                        "from": metric["entity"],
                        "to": dimension["entity"],
                        "allowed": True,
                        "identity": True,
                    }
                    result[synthetic["id"]] = synthetic
                    continue
                path = self.registry.entity_path(metric["entity"], dimension["entity"])
                if path:
                    result[path["id"]] = deepcopy(path)
        return [result[key] for key in sorted(result)]

    def _search(
        self, family: str, request: str, *, limit: int | None
    ) -> list[DiscoveryHit]:
        normalized_request = _normalize(request)
        request_tokens = _tokens(request)
        hits: list[DiscoveryHit] = []
        for item in self.registry.data.get(family, []):
            if family == "metrics" and not item.get("active", True):
                continue
            fields = {
                "id": item["id"],
                "name": item.get("name", ""),
                "description": item.get("description", ""),
            }
            for index, alias in enumerate(item.get("aliases", [])):
                fields[f"alias[{index}]"] = alias

            best = 0.0
            matched: list[str] = []
            for label, raw in fields.items():
                if not raw:
                    continue
                normalized = _normalize(str(raw))
                label_tokens = _tokens(str(raw))
                score = 0.0
                if normalized and normalized == normalized_request:
                    score = 1.0
                elif normalized and re.search(rf"(?<![a-z0-9]){re.escape(normalized)}(?![a-z0-9])", normalized_request):
                    score = 0.95
                elif label_tokens:
                    overlap = len(label_tokens & request_tokens) / len(label_tokens)
                    if overlap == 1.0:
                        score = 0.85
                    elif overlap >= 0.5:
                        score = 0.55 + 0.20 * overlap
                if score > best:
                    best = score
                    matched = [label]
                elif score and score == best:
                    matched.append(label)
            if best > 0:
                hits.append(
                    DiscoveryHit(
                        object_id=item["id"],
                        family=family,
                        score=best,
                        matched_on=tuple(sorted(matched)),
                        object=deepcopy(item),
                    )
                )
        hits.sort(key=lambda hit: (-hit.score, hit.object_id))
        return hits if limit is None else hits[:limit]

