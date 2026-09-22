# Reproducibility

## Scope

The artifact supports two levels of review:

1. **Credential-free paper evidence reproduction** from frozen benchmark/configuration plus sealed normalized outputs.
2. **Provider re-execution** when reviewers choose to supply their own API credentials; provider-run code is documented separately and is not required to reproduce the published quantitative tables.

The paper-number path makes no paid provider calls.

## Install

Python 3.11 is recommended.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev,duckdb]"
```

## Frozen source binding

- research source commit: `58d753aa16dbd8e2372475f9002950f4aff7a498`
- benchmark: `benchmark/canonical_cases.v1.1.jsonl`
- canonical cases: 300
- held-out test: 240 cases / 720 utterances

`PRESERVATION_AUDIT.json` records byte equality for 29 critical frozen files after public-path renaming.

## Release assets

### 1. Final-v2 sealed evidence

`mia-public-sealed-evidence-v1.zip`

- SHA-256: `429b0e1b5e427d1bc9840163e032b36a07c74a71913c13d0469d557fcb89b93b`
- contains final MIA-v2 normalized outputs/predictions/traces, B4-Matched outputs, clean-prompt outputs, mechanism/component reports, and top-N sensitivity records
- source workflow bindings are in `SEALED_ARTIFACT_MANIFEST.json`

Relevant source runs include final MIA-v2 `35426074276`, evaluation `35429477378`, B2-Matched `35457800186`, B4-Matched `35458314825`, mechanism replay `35461708139`, clean-prompt `35462465351`, paired clean-prompt audit `35466369794`, component analysis `35467947692`, and top-N sensitivity `35470004077`.

### 2. Paper reproducibility supplement

`mia-public-reproducibility-supplement-v1.zip`

- SHA-256: `1687798651c324abc5824d14ce94569765a90117e0695bfcff87ccea8b08bd99`
- contains exact final/clean request payloads required by replay scripts
- contains historical normalized B0–B4 + earlier-MIA held-out predictions for both providers
- contains the complete credential-free confirmatory result package, including `h2-contrastive-visibility.json`
- contains challenge-v2 scored evaluation JSON and normalized B1/B2/B3/B4/MIA-v2 predictions
- source bindings are in `REPRODUCIBILITY_SUPPLEMENT_MANIFEST.json`

Restricted writer source text, participant workbooks, provider transport logs, and credentials remain excluded.

## One-command paper evidence reproduction

After both assets are attached to release `artifact-v1.0`:

```bash
bash scripts/reproduce_paper.sh
```

The script:

- downloads and SHA-verifies both release assets;
- extracts them into an isolated work directory;
- restores exact request payloads beside the sealed normalized generations;
- recomputes historical B0–B4/MIA held-out metrics;
- recomputes the final MIA-v2 row and confidence intervals;
- deterministically regenerates B2-Matched from the same sealed final-MIA generations;
- evaluates B2-Matched and B4-Matched;
- reruns fixed-generation mechanism replay;
- reruns clean-prompt paired analysis;
- reruns final component analysis;
- reruns H2/top-N sensitivity;
- regenerates challenge-v2 reader-facing metrics from its frozen scored evaluation;
- verifies the regenerated values against frozen reader-facing evidence.

A successful run ends with:

`Paper evidence reproduction: PASS`

## Direct asset download

While the repository is private, GitHub authentication is required:

```bash
gh release download artifact-v1.0 \
  --repo hollylessthan/metric-intent-assurance-artifact \
  --pattern 'mia-public-*.zip'
```

Once the repository is public, reviewers can use ordinary HTTPS without `gh` authentication:

```bash
curl -L -O https://github.com/hollylessthan/metric-intent-assurance-artifact/releases/download/artifact-v1.0/mia-public-sealed-evidence-v1.zip
curl -L -O https://github.com/hollylessthan/metric-intent-assurance-artifact/releases/download/artifact-v1.0/mia-public-reproducibility-supplement-v1.zip
```

Always verify SHA-256 values above before use.

## Deterministic unit checks

```bash
python -m unittest \
  tests.test_evaluation \
  tests.test_mia_v2_preflight \
  tests.test_mia_v2_readiness_audit \
  tests.test_v2_matched_baselines
```

## Immutability rule

Frozen benchmark labels, thresholds, provider outputs, historical predictions, and confirmatory records are never rewritten during packaging. Corrections and sensitivity analyses are additional records, not mutations of frozen evidence.
