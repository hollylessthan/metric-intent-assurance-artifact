from __future__ import annotations

import json

from .models import Intent


SLOT_QUESTIONS = {
    "metrics": "Which governed metric did you mean: {choices}?",
    "filters": "Which filter condition did you mean: {choices}?",
    "time.calendar_id": "Should this use the {choices} calendar?",
    "time.interval": "Which time interval did you mean: {choices}?",
    "time.temporal_grain": "Which time grain did you mean: {choices}?",
    "time.completeness": "Which data-completeness rule did you mean: {choices}?",
    "time.timezone": "Which timezone should define the interval: {choices}?",
    "subject_scope": "Which subject scope did you mean: {choices}?",
    "dimensions": "Which grouping did you mean: {choices}?",
    "output_grain": "Which output grain did you mean: {choices}?",
    "comparison": "Which comparison did you mean: {choices}?",
    "version_policy": "Should this use {choices} metric definitions?",
    "metric_versions": "Which named metric version did you mean: {choices}?",
    "ordering": "Which result ordering did you mean: {choices}?",
    "limit": "How many result rows did you mean: {choices}?",
}

SLOT_REASON_CODES = {
    "metrics": "CLR_METRIC_IDENTITY",
    "filters": "CLR_FILTER_VALUE",
    "time.calendar_id": "CLR_CALENDAR",
    "time.interval": "CLR_TIME_RANGE",
    "time.temporal_grain": "CLR_GRAIN",
    "time.completeness": "CLR_TIME_RANGE",
    "time.timezone": "CLR_CALENDAR",
    "subject_scope": "CLR_ENTITY_SCOPE",
    "dimensions": "CLR_DIMENSION",
    "output_grain": "CLR_GRAIN",
    "comparison": "CLR_COMPARISON",
    "version_policy": "CLR_VERSION_POLICY",
    "metric_versions": "CLR_VERSION_POLICY",
    "ordering": "CLR_GRAIN",
    "limit": "CLR_GRAIN",
}


def reason_for_slot(slot: str) -> str:
    if slot not in SLOT_REASON_CODES:
        raise ValueError(f"unmapped clarification slot: {slot}")
    return SLOT_REASON_CODES[slot]


def _render(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def targeted_question(intents: list[Intent]) -> tuple[str, str]:
    """Ask about the first differing semantic slot in a fixed, preregisterable order."""
    canonical = [item.semantic_canonical() for item in intents]
    probes = {
        "metrics": [item["metrics"] for item in canonical],
        "filters": [item["filters"] for item in canonical],
        "time.calendar_id": [item["time"].get("calendar_id") for item in canonical],
        "time.interval": [[item["time"].get("start"), item["time"].get("end")] for item in canonical],
        "time.temporal_grain": [item["time"].get("temporal_grain") for item in canonical],
        "time.completeness": [item["time"].get("completeness") for item in canonical],
        "time.timezone": [item["time"].get("timezone") for item in canonical],
        "subject_scope": [item["subject_scope"] for item in canonical],
        "dimensions": [item["dimensions"] for item in canonical],
        "output_grain": [item["output_grain"] for item in canonical],
        "comparison": [item["comparison"] for item in canonical],
        "version_policy": [item["version_policy"] for item in canonical],
        "metric_versions": [item["metric_versions"] for item in canonical],
        "ordering": [item["ordering"] for item in canonical],
        "limit": [item["limit"] for item in canonical],
    }
    for slot, values in probes.items():
        choices = sorted({_render(value) for value in values})
        if len(choices) > 1:
            return slot, SLOT_QUESTIONS[slot].format(choices=" or ".join(choices))
    raise ValueError("targeted clarification requires semantically distinct intents")
