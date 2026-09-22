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
- checks the frozen original H2 confirmatory record and reruns the top-N-excluded H2 sensitivity;
- regenerates challenge-v2 reader-facing metrics from its frozen scored evaluation;
- regenerates the reviewer-facing quantitative tables and Figures 2–3;
- verifies the regenerated values against `paper_numbers.json` and the frozen reader-facing evidence.

A successful run ends with:

`Paper evidence reproduction: PASS`

## Optional provider re-execution

Paper-number reproduction above is credential-free. Reviewers who want to make fresh provider calls can use the same exact request payloads with their own keys.

Final MIA-v2:

```bash
export OPENAI_API_KEY=...
python scripts/rerun_provider_requests.py \
  --provider gpt --system mia-v2 \
  --requests .reproduce/supplement/mia-public-reproducibility-supplement-v1/requests/final-mia/gpt/requests.jsonl \
  --output-dir .reproduce/provider-rerun/gpt
```

For Claude, set `ANTHROPIC_API_KEY` and use `--provider claude`.

Clean-prompt provider reruns use the same `--system mia-v2` path with the exact clean request files from the supplement, for example `.reproduce/supplement/mia-public-reproducibility-supplement-v1/requests/clean-prompt/gpt/requests.jsonl`.

Historical B0–B4 provider reruns are **not** supported by this curated artifact. Those systems are preserved as frozen historical evidence through their normalized held-out predictions and confirmatory records.

B4-Matched requests can first be rebuilt deterministically from the exact final-MIA requests and sealed semantic generations:

```bash
python scripts/prepare_b4_requests.py \
  --provider gpt \
  --final-requests .reproduce/supplement/mia-public-reproducibility-supplement-v1/requests/final-mia/gpt/requests.jsonl \
  --final-raw .reproduce/sealed/mia-public-sealed-evidence/final-mia/gpt/raw_outputs.jsonl \
  --output .reproduce/provider-rerun/b4-gpt-requests.jsonl
```

Then pass that request file to `rerun_provider_requests.py --system b4-matched` together with `--sealed-mia-raw`.

The frozen model IDs and decoding settings are carried in each request file. The supplied pricing manifests are `evaluation/openai-pricing.json` and `evaluation/anthropic-pricing.json`. Historical observed study costs are evidence records, not promises of future API cost.

## Benchmark construction provenance

`benchmark/construction/` preserves the synthetic seed builder and post-adjudication finalizer from the pinned source commit. The authoritative evaluated benchmark remains `benchmark/canonical_cases.v1.1.jsonl`; restricted annotation workbooks are not required for paper-number reproduction.

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
