from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from .models import Intent
from .registry import Registry


@dataclass(frozen=True)
class OutputGrainDerivation:
    entities: tuple[str, ...]
    representable_as_v1_single_entity: bool
    v1_entity: str | None
    source: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "entities": list(self.entities),
            "representable_as_v1_single_entity": self.representable_as_v1_single_entity,
            "v1_entity": self.v1_entity,
            "source": self.source,
        }


def derive_grouping_entities(intent: Intent, registry: Registry) -> OutputGrainDerivation:
    """Derive output entity context from governed objects, never model assertion.

    For grouped requests the output entities come from selected dimensions.
    For ungrouped requests they come from selected metrics. A v1-compatible
    single entity exists only when the derived set contains exactly one entity.
    """
    if intent.dimensions:
        objects = [registry.dimension(dimension_id) for dimension_id in intent.dimensions]
        if any(item is None for item in objects):
            raise ValueError("cannot derive grouping entities from unknown dimensions")
        entities = tuple(sorted({item["entity"] for item in objects if item}))
        source = "dimensions"
    else:
        objects = [registry.metric(metric_id) for metric_id in intent.metrics]
        if any(item is None for item in objects):
            raise ValueError("cannot derive output entity from unknown metrics")
        entities = tuple(sorted({item["entity"] for item in objects if item}))
        source = "metrics"

    single = len(entities) == 1
    return OutputGrainDerivation(
        entities=entities,
        representable_as_v1_single_entity=single,
        v1_entity=entities[0] if single else None,
        source=source,
    )


def normalize_v1_output_entity(intent: Intent, registry: Registry) -> Intent:
    """Return a v1 Intent with mechanically derived single output entity.

    This helper is for credential-free v2 replay/compatibility analysis. It does
    not make mixed-entity grouping executable. If dimensions imply multiple
    entities, callers must use the v2 relationship/cardinality contract instead
    of collapsing them into one entity.
    """
    derived = derive_grouping_entities(intent, registry)
    if not derived.representable_as_v1_single_entity:
        raise ValueError(
            "mixed-entity grouping cannot be normalized into the v1 single-entity output_grain"
        )
    value = intent.canonical()
    value["output_grain"] = {
        **deepcopy(value["output_grain"]),
        "entity": derived.v1_entity,
    }
    return Intent.from_dict(value)
