# Reproducibility

## 1. Credential-free checks available in this repository

Install the package and run the included deterministic test subset:

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

The artifact also includes the frozen benchmark, registries, prompts, final MIA-v2 implementation, and selected deterministic analysis scripts. These checks do not require provider credentials.

## 2. Frozen source binding

The curated artifact is pinned to research source commit:

`58d753aa16dbd8e2372475f9002950f4aff7a498`

The authoritative benchmark is:

`benchmarks/phase4/final/canonical_cases.v1.1.jsonl`

The held-out test contains 240 cases / 720 utterances.

## 3. Sealed final-v2 provider artifacts

The final reader-facing evaluation was produced from immutable workflow artifacts retained by the research repository. The relevant run IDs are:

- final MIA-v2: `35426074276`
- B2-Matched credential-free evaluation: `35457800186`
- B4-Matched provider evaluation: `35458314825`
- fixed-generation mechanism replay: `35461708139`
- clean-prompt sensitivity: `35462465351`
- paired clean-prompt audit: `35466369794`
- final component analysis: `35467947692`
- top-N benchmark-defect sensitivity: `35470004077`

The original source-repository procedure downloads those artifacts with `gh run download` and then runs the deterministic analysis scripts included here.

## 4. Publication release gate

Before making this repository public and using it as the paper availability URL:

1. migrate the sealed raw provider-output archives needed for the final result tables into this repository or immutable public release assets;
2. record filenames, source run IDs, artifact IDs where available, SHA-256 digests, and destination URLs/paths in a machine-readable manifest;
3. update reproduction commands so they no longer depend on access to the private research repository;
4. run the clean-checkout test/analysis procedure from this repository alone;
5. scan for secrets, personal data, internal-review notes, and any `RESTRICTED` file;
6. tag the frozen public artifact.

Until step 1 is completed, this repository should be described as a **curated pre-publication artifact**, not a fully standalone reproduction package.

## 5. Immutability rule

Frozen benchmark labels, thresholds, provider outputs, and historical configurations must not be rewritten during packaging. Corrections or sensitivity analyses are added as separate records rather than mutating frozen evidence.
