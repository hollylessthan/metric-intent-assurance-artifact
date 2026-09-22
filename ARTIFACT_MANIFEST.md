# Artifact Manifest

## Included

- `src/mia/`: final MIA-v2 implementation, assurance logic, canonicalization, grounding, normalization, matched baselines, evaluation, and compilers.
- `schemas/`: core action, intent, MIA-v2 model-intent, prediction, and registry contracts.
- `registries/`: frozen domain registry snapshots.
- `benchmark/`: frozen v1.1 benchmark, utterances, split metadata, adjudication/human-validation summaries, execution-readiness evidence, and construction provenance source under `benchmark/construction/`.
- `prompts/`: frozen callable-system and final-v2 prompts.
- `evaluation/`: frozen benchmark/evaluation/threshold configuration plus provider pricing manifests used by optional reruns.
- `backends/metricflow/`: synthetic MetricFlow fixture.
- `scripts/`: deterministic paper-evidence reproduction, matched-control regeneration, mechanism/sensitivity analyses, paper table/figure generation, verification, and optional provider rerun tooling.
- `tests/`: artifact-facing deterministic tests.
- `evidence/`: final-v2 summaries, historical controlled-study records, negative challenge evidence, independent action-contract evidence, policy/scaling analysis, challenge freezes/bindings, and top-N sensitivity.
- `SEALED_ARTIFACT_MANIFEST.json`: source bindings and hashes for the final-v2 sealed evidence bundle.
- `REPRODUCIBILITY_SUPPLEMENT_MANIFEST.json`: source bindings and hashes for the supplement containing exact requests, historical predictions, full H2 confirmatory records, and challenge-v2 scored outputs.

## Release assets

Release `artifact-v1.0` contains:

1. `mia-public-sealed-evidence-v1.zip` — final-v2 normalized outputs/predictions/traces and related deterministic-analysis evidence.
2. `mia-public-reproducibility-supplement-v1.zip` — exact request payloads, historical B0–B4/earlier-MIA predictions, full confirmatory H2 records, and challenge-v2 scored evidence.

Both assets are SHA-256 bound in their manifests.

## Intentionally excluded

- paper/manuscript and venue-formatting source;
- internal skeptical reviews, author checklists, and planning/status notes;
- secrets, API keys, credentials, and local environment files;
- files explicitly marked `RESTRICTED`;
- private participant workbooks and challenge-writer source materials;
- provider transport evidence logs that are not needed for paper-number reproduction;
- superseded internal orchestration machinery.

## Reviewer-facing audit files

- `EVIDENCE_INDEX.md`: maps material paper evidence layers to repository/release inputs.
- `PRESERVATION_AUDIT.json`: byte-preservation audit across 29 critical frozen files.
- `SEALED_ARTIFACT_MANIFEST.json`: final-v2 sealed evidence binding.
- `REPRODUCIBILITY_SUPPLEMENT_MANIFEST.json`: supplement binding.
- `REPRODUCIBILITY.md`: one-command reproduction and optional provider-rerun instructions.
