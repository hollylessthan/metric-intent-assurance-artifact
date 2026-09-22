# Metric Intent Assurance (MIA) Artifact

This repository is the curated reproducibility artifact for the Metric Intent Assurance research project.

MIA evaluates whether a natural-language enterprise metric request should **Execute**, **Clarify**, **Reject**, or be labeled a **Coverage Gap** before governed execution. The reader-facing system in the paper is **MIA-v2**. Historical MIA-v1 material is retained in the private research repository for protocol provenance but is not the artifact's primary implementation.

## Source snapshot

This artifact was curated from:

- source repository: `hollylessthan/metric-intent-assurance`
- frozen source commit: `58d753aa16dbd8e2372475f9002950f4aff7a498`
- artifact packaging branch: `artifact/publication-package-v1`

See `SOURCE_SNAPSHOT.json` and `ARTIFACT_MANIFEST.md` for the inclusion/exclusion policy.

## What is included

- final MIA-v2 implementation and canonical intent contracts;
- deterministic assurance, validation, clarification, and compilation code;
- MetricFlow and DuckDB backend fixtures;
- frozen SaaS, commerce, and support registries;
- the frozen Phase 4 v1.1 benchmark, 900 utterances, split metadata, adjudication summary, and human-validation record;
- B0, B1, B2, B4, and MIA prompts plus the final-v2 matched/sensitivity prompts;
- B3 logic in the local evaluation code (B3 is derived locally and therefore has no provider prompt);
- frozen reader-facing result summaries and challenge summaries;
- selected deterministic reproduction scripts and tests.

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
  tests.test_mia_v2_regression \
  tests.test_phase5_systems \
  tests.test_v2_matched_baselines
```

Optional MetricFlow dependencies:

```bash
python -m pip install -r requirements-metricflow.txt
```

## Benchmark

The frozen benchmark contains 300 canonical cases and 900 utterances across SaaS, commerce, and customer support. The development split contains 60 cases; the held-out test split contains 240 cases / 720 utterances. The canonical gold source is:

`benchmarks/phase4/final/canonical_cases.v1.1.jsonl`

Frozen registry snapshots are under `registries/phase4/`.

## Evaluation systems

The confirmatory system family is:

| ID | System |
|---|---|
| B0 | Direct Text-to-SQL |
| B1 | Unconstrained semantic-layer agent |
| B2 | Structured Text-to-Metrics |
| B3 | Binary selective baseline, derived locally from confidence/self-consistency |
| B4 | Generic four-action router without deterministic metric-specific predicates |
| MIA | Candidate generation + deterministic validation + calibrated four-action policy |

Because B3 is derived locally, `src/mia/phase5.py` contains its evaluation logic rather than a provider prompt.

## Reproducibility status

The deterministic code, benchmark, registries, prompts, and reader-facing summary evidence are packaged here.

**Pre-publication release gate:** the sealed raw provider-output archives used for the final MIA-v2 evaluation are still retained as immutable GitHub Actions artifacts in the private research repository. They must be migrated into public immutable artifact/release assets (with hashes) before this repository is labeled fully standalone reproducible or made the paper's final availability URL.

See `REPRODUCIBILITY.md` for the exact retained run IDs and the remaining release gate.

## Artifact hygiene

This repository intentionally excludes manuscript source, internal skeptical-review/planning documents, credentials, personal data, superseded experiment machinery, and files explicitly marked `RESTRICTED`.

## License

See `LICENSE`.
