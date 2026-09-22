# Artifact Manifest

## Included

- `src/mia/`: final implementation, assurance logic, canonicalization, grounding, normalization, matched baselines, evaluation, and compilers.
- `schemas/`: core action, intent, MIA-v2 model-intent, prediction, and registry contracts.
- `registries/`: frozen domain registry snapshots.
- `benchmark/`: frozen v1.1 benchmark, utterances, split metadata, adjudication/human-validation summaries, and execution-readiness evidence.
- `prompts/`: frozen callable-system and final-v2 prompts.
- `evaluation/`: frozen benchmark/evaluation/threshold configuration needed to interpret the packaged study.
- `backends/metricflow/`: synthetic MetricFlow fixture.
- `scripts/`: selected deterministic final-v2 reproduction and sensitivity scripts.
- `tests/`: selected artifact-facing deterministic tests.
- `evidence/`: final-v2 summaries, historical controlled-study records, negative challenge evidence, independent action-contract evidence, policy/scaling analysis, challenge freezes/bindings, and top-N sensitivity.

## Intentionally excluded

- paper/manuscript and venue-formatting source;
- internal skeptical reviews, author checklists, and planning/status notes;
- secrets, API keys, credentials, and local environment files;
- files explicitly marked `RESTRICTED`;
- superseded provider orchestration/workflow machinery that is not needed to understand or reproduce the final reader-facing method;
- historical MIA-v1 implementation material except where required by a frozen shared contract;
- raw provider-output ZIPs until they are migrated as immutable public assets.

## Release blocker

Raw sealed provider outputs for the final-v2 evaluation are not yet physically present in this repository. Their immutable source run IDs are documented in `REPRODUCIBILITY.md`. Public release should wait until those archives are migrated and hash-bound here.

## Reviewer audit files

- `EVIDENCE_INDEX.md`: maps material paper evidence layers to public artifact files and remaining raw-payload blockers.
- `PRESERVATION_AUDIT.json`: byte-preservation audit across 29 critical frozen files.
- `SKEPTICAL_ARTIFACT_REVIEW.md`: skeptical completeness and reproducibility review.
