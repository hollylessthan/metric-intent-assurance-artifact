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
  tests.test_v2_matched_baselines
```

The artifact also includes the frozen benchmark, registries, prompts, final MIA-v2 implementation, and selected deterministic analysis scripts. These checks do not require provider credentials.

## 2. Frozen source binding

The curated artifact is pinned to research source commit:

`58d753aa16dbd8e2372475f9002950f4aff7a498`

The authoritative benchmark is:

`benchmark/canonical_cases.v1.1.jsonl`

The held-out test contains 240 cases / 720 utterances.

## 3. Sealed final-v2 provider artifacts

The final reader-facing evaluation was produced from immutable workflow artifacts retained by the research repository. `SEALED_ARTIFACT_MANIFEST.json` now records the exact source run IDs, artifact IDs, ZIP SHA-256 digests, and file-level SHA-256 hashes for the reviewer-safe contents. The relevant run IDs are:

- final MIA-v2: `35426074276`
- B2-Matched credential-free evaluation: `35457800186`
- B4-Matched provider evaluation: `35458314825`
- fixed-generation mechanism replay: `35461708139`
- clean-prompt sensitivity: `35462465351`
- paired clean-prompt audit: `35466369794`
- final component analysis: `35467947692`
- top-N benchmark-defect sensitivity: `35470004077`

The original source-repository procedure downloads those artifacts with `gh run download` and then runs the deterministic analysis scripts included here. During artifact curation, all 16 relevant workflow artifacts were downloaded and inspected. Provider transport evidence logs and duplicated request payloads are intentionally excluded from the publication package; normalized sealed outputs, predictions, traces, and result reports are the publication-safe reproduction layer.

When migrated payloads are present under `evidence/sealed/<artifact-name>/`, verify them with:

```bash
python scripts/verify_sealed_artifacts.py --require-all
```

Without `--require-all`, the verifier checks any sealed files already present and reports what is still missing.

## 4. Publication release gate

Before making this repository public and using it as the paper availability URL:

1. migrate the normalized sealed outputs/predictions/traces needed for the final result tables into this repository or immutable public release assets;
2. preserve the bindings already recorded in `SEALED_ARTIFACT_MANIFEST.json` and add destination URLs/paths once the large payload transfer is complete;
3. update reproduction commands so they no longer depend on access to the private research repository;
4. run the clean-checkout test/analysis procedure from this repository alone;
5. scan for secrets, personal data, internal-review notes, and any `RESTRICTED` file;
6. tag the frozen public artifact.

The source artifacts have now been enumerated, downloaded, safety-inspected, hash-bound, and repackaged into `mia-public-sealed-evidence-v1.zip` (SHA-256 `429b0e1b5e427d1bc9840163e032b36a07c74a71913c13d0469d557fcb89b93b`). The remaining step is attaching that curated bundle as an immutable public release asset (or otherwise transferring it into the repository). Until that transfer is completed, this repository should be described as a **curated pre-publication artifact**, not a fully standalone reproduction package.

## 5. Immutability rule

Frozen benchmark labels, thresholds, provider outputs, and historical configurations must not be rewritten during packaging. Corrections or sensitivity analyses are added as separate records rather than mutating frozen evidence.
