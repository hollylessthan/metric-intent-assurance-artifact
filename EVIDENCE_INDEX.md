# Evidence Index

This index maps the paper's material evidence layers to the repository and its two hash-bound release assets: the final-v2 sealed bundle and the paper-reproducibility supplement.

## Evidence physically present

| Evidence layer | Public artifact | Role |
|---|---|---|
| Frozen benchmark | `benchmark/canonical_cases.v1.1.jsonl` | 300 canonical cases; authoritative gold source |
| Request variants | `benchmark/utterances.jsonl` | 900 utterances |
| Registry snapshots | `registries/*.json` | governed semantic context bound by registry hashes |
| Benchmark validation | `benchmark/validation_report.json`, `benchmark/adjudication_report.json` | benchmark integrity and adjudication |
| Sampled author quality control | `benchmark/validation/human_validation_v1.json` | 100-case sampled quality-control record; not independent practitioner validation |
| Historical controlled study | `evidence/historical-controlled-results.json` | frozen B0–B4 and earlier-MIA study results and ablation record; original H2 is sourced from the frozen confirmatory `h2-contrastive-visibility.json` record in the reproducibility supplement |
| Historical policy/scaling analysis | `evidence/historical-policy-and-scaling-analysis.json` | sealed-trace policy/class/scaling analysis |
| Negative development challenge | `evidence/development-challenge-negative-result.md`, machine-readable challenge evaluation and binding | preserves unfavorable/mixed pre-v2 evidence |
| Independent action-contract study | `evidence/action-contract-study.md`, `action-contract-study.json`, `action-contract-harmonization.json` | 72-case blind action-contract agreement and five retained substantive disputes |
| Final MIA-v2 regression | `evidence/mia-v2-regression-summary.json` | final-v2 controlled post-hoc regression summary |
| Final post-freeze challenge | `evidence/challenge-v2-summary.json`, `final-challenge-freeze.json`, `docs/mia-v2-challenge-v2-*.md` | small prospective phrasing-robustness challenge |
| Top-N benchmark-defect sensitivity | `evidence/topn-defect-sensitivity.json` | preserves frozen gold while reporting defect-excluded semantic-precision sensitivity |
| Final method source | `src/mia/` | parser/canonicalizer, deterministic assurance, validation, compilers |
| Frozen prompts | `prompts/` | historical callable-system prompts and final-v2 prompts |
| Frozen evaluation settings | `evaluation/` | benchmark freeze, study protocol, held-out config, threshold lock |

## Final-v2 sealed payload migration status

All relevant workflow artifacts have been enumerated, downloaded, inspected, and bound in `SEALED_ARTIFACT_MANIFEST.json`. The publication-safe layer is the normalized `raw_outputs.jsonl`, `predictions.jsonl`, `traces.jsonl`, and compact result reports. Provider transport evidence logs remain excluded. Exact request payloads required by deterministic replay are restored in the reproducibility supplement. The publication-safe bundle is attached to GitHub release `artifact-v1.0`: `mia-public-sealed-evidence-v1.zip` (1,317,896 bytes; SHA-256 `429b0e1b5e427d1bc9840163e032b36a07c74a71913c13d0469d557fcb89b93b`; 70 files). GitHub's reported digest matches the curated bundle manifest exactly. The repository is currently private, so external unauthenticated access is intentionally not yet available. This sentence and the corresponding private-access instructions must be removed/updated when repository visibility changes.

| Evidence | Source workflow run | Why needed |
|---|---:|---|
| Final MIA-v2 raw provider outputs | `35426074276` | reproduce final predictions/traces |
| Final MIA-v2 credential-free evaluation | `35429477378` | recompute final metrics |
| B2-Matched evaluation | `35457800186` | representation-matched control |
| B4-Matched provider outputs | `35458314825` | generic-router matched control |
| Fixed-generation mechanism replay | `35461708139` | deterministic component effects |
| Clean-prompt provider run | `35462465351` | prompt-wording sensitivity |
| Paired clean-prompt audit | `35466369794` | changed-case sensitivity decomposition |
| Parser / joint-validator component analysis | `35467947692` | unresolved-slot, validator-family, provenance, residual-failure evidence |
| Top-N sensitivity raw artifact | `35470004077` | source-bound defect-exclusion reproduction |

## Reviewer-facing final-v2 values

The public artifact preserves the paper's bounded final-v2 conclusions:

- Final MIA — GPT: UER 0.72%, CEC 82.84%, Macro-F1 75.12%; Claude: 4.80%, 78.22%, 75.48%.
- B2-Matched — GPT: 17.03%, 83.17%, 58.83%; Claude: 19.42%, 79.87%, 60.46%.
- B4-Matched — GPT: 6.24%, 83.17%, 80.51%; Claude: 4.32%, 78.22%, 80.24%.
- Ignoring explicit unresolved slots raises UER to 6.24% GPT and 24.46% Claude, with CEC unchanged.
- Turning all validator families off raises UER to 5.76% GPT and 11.51% Claude; grain/additivity alone restores full-MIA UER in both families on the sealed candidate distribution.
- Clean-prompt sensitivity raises UER from 0.72% to 1.44% GPT and from 4.80% to 6.00% Claude.
- Defect-excluded final-MIA wrong-intent execution on answerable requests is 1/267 GPT and 14/267 Claude.

Original H2 is intentionally treated as a **frozen confirmatory record**, not reconstructed from historical B1 predictions in this artifact. The top-N-excluded 80-group H2 sensitivity is recomputed from the per-row details in that frozen record by `scripts/topn_defect_sensitivity.py`.

These are **reported evidence summaries**, not substitutes for the normalized sealed payloads listed above. `SEALED_ARTIFACT_MANIFEST.json` records both ZIP-level and file-level SHA-256 bindings for those payloads.

## Preservation

`PRESERVATION_AUDIT.json` records a Git-blob equality audit across 29 critical frozen files. All 29 are byte-identical to the pinned research source commit after path renaming.

## Release criterion

The artifact now contains the sealed evidence binding. The paper-number gate is `scripts/reproduce_paper.sh`, which consumes both release assets and verifies regenerated quantitative evidence against the frozen records. While the repository is private, release downloads require authentication; after publication, the same asset URLs can be downloaded without authentication.
