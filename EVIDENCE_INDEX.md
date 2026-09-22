# Evidence Index

This index maps the paper's material evidence layers to the public artifact. It separates **frozen evidence physically present in this repository** from **sealed raw provider outputs that still need migration before public release**.

## Evidence physically present

| Evidence layer | Public artifact | Role |
|---|---|---|
| Frozen benchmark | `benchmark/canonical_cases.v1.1.jsonl` | 300 canonical cases; authoritative gold source |
| Request variants | `benchmark/utterances.jsonl` | 900 utterances |
| Registry snapshots | `registries/*.json` | governed semantic context bound by registry hashes |
| Benchmark validation | `benchmark/validation_report.json`, `benchmark/adjudication_report.json` | benchmark integrity and adjudication |
| Sampled author quality control | `benchmark/validation/human_validation_v1.json` | 100-case sampled quality-control record; not independent practitioner validation |
| Historical controlled study | `evidence/historical-controlled-results.json` | frozen B0–B4 and earlier-MIA study results and ablation record |
| Historical policy/scaling analysis | `evidence/historical-policy-and-scaling-analysis.json` | sealed-trace policy/class/scaling analysis |
| Negative development challenge | `evidence/development-challenge-negative-result.md`, machine-readable challenge evaluation and binding | preserves unfavorable/mixed pre-v2 evidence |
| Independent action-contract study | `evidence/action-contract-study.md`, `action-contract-study.json`, `action-contract-harmonization.json` | 72-case blind action-contract agreement and five retained substantive disputes |
| Final MIA-v2 regression | `evidence/mia-v2-regression-summary.json` | final-v2 controlled post-hoc regression summary |
| Final post-freeze challenge | `evidence/challenge-v2-summary.json`, `final-challenge-freeze.json`, `docs/mia-v2-challenge-v2-*.md` | small prospective phrasing-robustness challenge |
| Top-N benchmark-defect sensitivity | `evidence/topn-defect-sensitivity.json` | preserves frozen gold while reporting defect-excluded semantic-precision sensitivity |
| Final method source | `src/mia/` | parser/canonicalizer, deterministic assurance, validation, compilers |
| Frozen prompts | `prompts/` | historical callable-system prompts and final-v2 prompts |
| Frozen evaluation settings | `evaluation/` | benchmark freeze, study protocol, held-out config, threshold lock |

## Final-v2 evidence whose raw sealed payload is not yet migrated

These results are described in the paper and remain bound to immutable workflow runs in the private research repository. The compact reported values and run IDs are preserved in the public docs, but the **raw sealed predictions/traces are not yet physically present here**.

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

These are **reported evidence summaries**, not substitutes for the raw sealed payloads listed above.

## Preservation

`PRESERVATION_AUDIT.json` records a Git-blob equality audit across 29 critical frozen files. All 29 are byte-identical to the pinned research source commit after path renaming.

## Release criterion

The artifact is reviewer-readable now, but it should remain pre-publication/draft until the raw sealed final-v2 payloads above are migrated into immutable public assets and the reproduction commands run without access to the private research repository.
