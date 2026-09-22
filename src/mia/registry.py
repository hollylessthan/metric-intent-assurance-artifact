from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .contracts import validate_registry_payload


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class Registry:
    data: dict[str, Any]
    snapshot_hash: str

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Registry":
        validate_registry_payload(value)
        data = deepcopy(value)
        claimed = data.pop("snapshot_hash", None)
        cls._validate_integrity(data)
        actual = canonical_hash(data)
        if claimed and claimed != actual:
            raise ValueError(f"registry hash mismatch: expected {claimed}, found {actual}")
        return cls(data=data, snapshot_hash=actual)

    @staticmethod
    def _validate_integrity(data: dict[str, Any]) -> None:
        """Fail closed on references and ACL representations the schema cannot prove alone."""
        families = ("metrics", "dimensions", "calendars", "entity_paths", "policies")
        for family in families:
            objects = data.get(family, [])
            ids = [item.get("id") for item in objects]
            if len(ids) != len(set(ids)):
                raise ValueError(f"duplicate {family} id in registry snapshot")

        metrics = {item["id"]: item for item in data.get("metrics", [])}
        dimensions = {item["id"]: item for item in data.get("dimensions", [])}
        calendars = {item["id"]: item for item in data.get("calendars", [])}
        version_ids: set[str] = set()
        for metric in metrics.values():
            unknown_dimensions = set(metric["allowed_dimensions"]) - set(dimensions)
            unknown_calendars = set(metric["allowed_calendars"]) - set(calendars)
            if unknown_dimensions or unknown_calendars:
                raise ValueError(
                    f'{metric["id"]} references unknown dimensions/calendars: '
                    f'{sorted(unknown_dimensions | unknown_calendars)}'
                )
            versions = sorted(metric["versions"], key=lambda item: item["effective_from"])
            if sum(bool(item.get("restated")) for item in versions) > 1:
                raise ValueError(f'{metric["id"]} has multiple restated versions')
            default_versions = [item for item in versions if item.get("default")]
            if len(default_versions) > 1:
                raise ValueError(f'{metric["id"]} has multiple default versions')
            for version in versions:
                if version["id"] in version_ids:
                    raise ValueError(f'duplicate metric version id: {version["id"]}')
                version_ids.add(version["id"])
                effective_from, effective_to = version["effective_from"], version.get("effective_to")
                if effective_to and effective_to < effective_from:
                    raise ValueError(f'{version["id"]} has an inverted effective interval')
            for left_index, left in enumerate(versions):
                for right in versions[left_index + 1:]:
                    left_end = left.get("effective_to")
                    right_end = right.get("effective_to")
                    overlaps = (
                        (left_end is None or right["effective_from"] <= left_end)
                        and (right_end is None or left["effective_from"] <= right_end)
                    )
                    if not overlaps:
                        continue
                    is_explicit_restatement_pair = (
                        (bool(left.get("restated")) != bool(right.get("restated")))
                        and (bool(left.get("default")) != bool(right.get("default")))
                    )
                    if not is_explicit_restatement_pair:
                        raise ValueError(f'{metric["id"]} has overlapping version intervals')

        entity_pairs: set[tuple[str, str]] = set()
        known_entities = {item["entity"] for item in metrics.values()} | {
            item["entity"] for item in dimensions.values()
        }
        for path in data.get("entity_paths", []):
            pair = (path["from"], path["to"])
            if not set(pair).issubset(known_entities):
                raise ValueError(f"entity path references unknown entity: {pair}")
            if pair in entity_pairs:
                raise ValueError(f"duplicate entity path: {pair}")
            entity_pairs.add(pair)

        governed_ids = {
            item["id"]
            for family in ("metrics", "dimensions")
            for item in data.get(family, [])
        }
        for policy in data.get("policies", []):
            if policy.get("object_id") not in governed_ids:
                raise ValueError(f'policy {policy.get("id")} references unknown object {policy.get("object_id")}')

        forbidden_acl_fields = {"allowed_roles", "denied_roles", "roles", "org_scopes"}
        for family in ("metrics", "dimensions"):
            for item in data.get(family, []):
                duplicated = forbidden_acl_fields.intersection(item)
                if duplicated:
                    raise ValueError(
                        f'{item.get("id")} declares object-level ACL fields; registry policies are authoritative'
                    )

    @classmethod
    def load(cls, path: str | Path) -> "Registry":
        return cls.from_dict(json.loads(Path(path).read_text()))

    def objects(self, family: str) -> dict[str, dict[str, Any]]:
        return {x["id"]: x for x in self.data.get(family, [])}

    def metric(self, metric_id: str) -> dict[str, Any] | None:
        return self.objects("metrics").get(metric_id)

    def dimension(self, dimension_id: str) -> dict[str, Any] | None:
        return self.objects("dimensions").get(dimension_id)

    def calendar(self, calendar_id: str) -> dict[str, Any] | None:
        return self.objects("calendars").get(calendar_id)

    def entity_path(self, source: str, target: str) -> dict[str, Any] | None:
        if source == target:
            return {"from": source, "to": target, "allowed": True}
        return next(
            (x for x in self.data.get("entity_paths", []) if x["from"] == source and x["to"] == target),
            None,
        )

    def version(self, metric: dict[str, Any], version_id: str) -> dict[str, Any] | None:
        return next((x for x in metric.get("versions", []) if x["id"] == version_id), None)

    def backend_mapping(self, obj: dict[str, Any], backend: str) -> dict[str, Any]:
        mapping = obj.get("backends", {}).get(backend)
        if not mapping:
            raise ValueError(f'{obj.get("id", "object")} has no {backend} mapping')
        return mapping
