# Metric Intent Assurance (MIA) Artifact

This repository is the curated reproducibility artifact for the Metric Intent Assurance research project.

MIA evaluates whether a natural-language enterprise metric request should **Execute**, **Clarify**, **Reject**, or be labeled a **Coverage Gap** before governed execution. The reader-facing system in the paper is **MIA-v2**. Historical MIA-v1 implementation code remains in the private research repository for protocol provenance; its held-out predictions and result records needed for paper reproduction are included in the public reproducibility supplement and are recomputed by the artifact workflow.

## Source snapshot

This artifact was curated from:

- source repository: `hollylessthan/metric-intent-assurance`
- frozen source commit: `58d753aa16dbd8e2372475f9002950f4aff7a498`
- artifact packaging branch: `artifact/publication-package-v1`

See `SOURCE_SNAPSHOT.json` and `ARTIFACT_MANIFEST.md` for the inclusion/exclusion policy. See `EVIDENCE_INDEX.md` for the reviewer-facing evidence map and `PRESERVATION_AUDIT.json` for the frozen-file integrity check.

## What is included

- final MIA-v2 implementation and canonical intent contracts;
- deterministic assurance, validation, clarification, and compilation code;
- MetricFlow and DuckDB backend fixtures;
- frozen SaaS, commerce, and support registries;
- the frozen Phase 4 v1.1 benchmark, 900 utterances, split metadata, adjudication summary, and human-validation record;
- B0, B1, B2, B4, and MIA prompts plus the final-v2 matched/sensitivity prompts;
- B3 logic in the local evaluation code (B3 is derived locally and therefore has no provider prompt);
- frozen reader-facing result summaries and challenge summaries;
- a provenance map from public artifact paths to the original internal research paths;
- deterministic paper-evidence reproduction scripts, a one-command entry point, and tests.

## Quick start

Python 3.11 is recommended.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev,duckdb]"

python -m unittest \
  tests.test_evaluation \
  tests.test_mia_v2_preflight \
  tests.test_mia_v2_readiness_audit \
  tests.test_v2_matched_baselines
```

Optional MetricFlow dependencies:

```bash
python -m pip install -r requirements-metricflow.txt
```

## Benchmark

The frozen benchmark contains 300 canonical cases and 900 utterances across SaaS, commerce, and customer support. The development split contains 60 cases; the held-out test split contains 240 cases / 720 utterances. The canonical gold source is:

`benchmark/canonical_cases.v1.1.jsonl`

Frozen registry snapshots are under `registries/`.

## Evaluation systems

The confirmatory system family is:

| ID | System |
|---|---|
| B0 | Direct Text-to-SQL |
| B1 | Unconstrained semantic-layer agent |
| B2 | Structured Text-to-Metrics |
| B3 | Binary selective baseline, derived locally from confidence/self-consistency |
| B4 | Generic four-action router without deterministic metric-specific predicates |
| MIA | Interpretation → fail-closed parsing → canonicalization → deterministic Assurer → four-action decision |

Because B3 is derived locally, `src/mia/study_metrics.py` contains its evaluation logic rather than a provider prompt.

## Reproducibility status

The deterministic code, benchmark, registries, prompts, sealed final-v2 evidence, and the paper-reproducibility supplement are packaged through this repository and release `artifact-v1.0`.

Run `bash scripts/reproduce_paper.sh` to recompute the paper's quantitative evidence, regenerate the reviewer-facing tables/Figures 2–3, and verify the regenerated values against the frozen evidence records. See `REPRODUCIBILITY.md` for details.

## Artifact hygiene

This repository intentionally excludes manuscript source, internal skeptical-review/planning documents, credentials, personal data, superseded experiment machinery, and files explicitly marked `RESTRICTED`.

## License

See `LICENSE`.
