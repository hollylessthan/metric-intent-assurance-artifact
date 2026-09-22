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


## 4. Download the public sealed bundle

From a clean checkout, download the release asset:

```bash
curl -L \
  -o mia-public-sealed-evidence-v1.zip \
  https://github.com/hollylessthan/metric-intent-assurance-artifact/releases/download/artifact-v1.0/mia-public-sealed-evidence-v1.zip

python - <<'PY'
import hashlib
from pathlib import Path

p = Path("mia-public-sealed-evidence-v1.zip")
print(hashlib.sha256(p.read_bytes()).hexdigest())
PY
```

Expected SHA-256:

`429b0e1b5e427d1bc9840163e032b36a07c74a71913c13d0469d557fcb89b93b`

Extract it under `evidence/sealed/`, then run:

```bash
python scripts/verify_sealed_artifacts.py --require-all
```

## 5. Publication release gate

Before making this repository public and using it as the paper availability URL:

1. public sealed bundle uploaded and SHA-256 verified — complete;
2. source run/artifact IDs and file-level hashes recorded in `SEALED_ARTIFACT_MANIFEST.json` — complete;
3. reproduction commands use the public artifact repository and release asset — complete;
4. run the clean-checkout test/analysis procedure from this repository plus the public release asset;
5. final secrets/personal-data/restricted-material scan;
6. finalize the frozen public artifact tag after PR merge if desired.

The source artifacts have been enumerated, downloaded, safety-inspected, hash-bound, and repackaged into the public release asset `mia-public-sealed-evidence-v1.zip` under tag `artifact-v1.0`. GitHub reports the expected size (1,317,896 bytes) and SHA-256 `429b0e1b5e427d1bc9840163e032b36a07c74a71913c13d0469d557fcb89b93b`. The sealed publication bundle is now public. The remaining release-readiness task is a clean-checkout reproduction using only this repository plus the public release asset.

## 6. Immutability rule

Frozen benchmark labels, thresholds, provider outputs, and historical configurations must not be rewritten during packaging. Corrections or sensitivity analyses are added as separate records rather than mutating frozen evidence.
