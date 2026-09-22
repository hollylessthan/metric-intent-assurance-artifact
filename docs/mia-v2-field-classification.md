# MIA v2 field classification

Status: **design input before provider regression**

The goal is to reduce what the language model must invent while preserving the frozen MIA-v1 canonical intent and validator for reproducibility.

## Principle

A field belongs in the model-facing v2 output only when it represents meaning that must be interpreted from the user's words.

If the value already exists in context, registry metadata, or can be derived mechanically, it should not be generated independently by the model.

## Current v1 fields

| v1 field | v2 responsibility | Reason |
| --- | --- | --- |
| `metrics` | model-interpreted | Which governed metric the user means is semantic interpretation. |
| `dimensions` | model-interpreted | Which requested breakdown(s) the user means is semantic interpretation. |
| `filters` | model-interpreted | Filter attribute/operator/value comes from the request. |
| `time.start/end` | model-interpreted | Requested period comes from the request. |
| `time.temporal_grain` | model-interpreted when explicit; otherwise existing default behavior | Do not infer a redesign from v2. |
| `time.calendar_id` | system/context default unless user explicitly specifies calendar | The benchmark already has `context.calendar_default`; preserve it. |
| `time.timezone` | system/context | Already provided by requester context. |
| `time.completeness` | system/default | Structural governance metadata, not normal user language. |
| `output_grain.entity` | **remove from model output** | Registry already knows the entity of selected dimensions/metrics; Phase 5 shows model generation of this field causes false non-execution. |
| `output_grain.temporal` | derive from time grain | Duplicate structural field. |
| `comparison` | omit from initial v2 model contract | The 240 held-out Phase 5 cases contain 0 non-null gold comparisons. No evidence-driven reason to redesign it now. |
| `ordering` | model-interpreted when requested | 12 held-out gold intents use ordering. |
| `limit` | model-interpreted when requested | 12 held-out gold intents use a limit. |
| `version_policy` | system-derived | Default remains `effective_time`; use explicit only when the request contains an explicit version/definition request. |
| `metric_versions` | model supplies explicit version wording/selection only when requested; otherwise system resolves | 41 held-out gold intents use explicit versions, so version requests remain in scope. |
| `subject_scope` | omit from initial v2 model contract | The 240 held-out Phase 5 cases contain 0 non-empty gold subject scopes. |
| `provenance` | system-derived | Exact registry references are deterministic evidence, not natural-language interpretation. |

## Minimal v2 model-facing shape

Conceptually:

```json
{
  "metrics": ["..."],
  "dimensions": ["..."],
  "filters": [],
  "time": {
    "start": "YYYY-MM-DD",
    "end": "YYYY-MM-DD",
    "temporal_grain": "month",
    "calendar_id": null
  },
  "explicit_metric_versions": {},
  "ordering": [],
  "limit": null
}
```

`calendar_id` is null unless the request explicitly specifies a calendar such as fiscal. The canonicalizer uses `Context.calendar_default` otherwise.

The exact schema will be versioned separately from `schemas/intent.schema.json`; the v1 schema is not modified.

## Compatibility strategy

MIA-v2 should convert this smaller model-facing representation into a canonical/auditable internal intent before deterministic assurance.

This allows:
- MIA-v1 artifacts to remain reproducible;
- v2 to remove unnecessary model-generated structure;
- v1 and v2 results to be compared without rewriting the old benchmark.
