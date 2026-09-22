# Provenance Map

The public artifact is organized by function rather than by the internal research roadmap. This file preserves traceability to the frozen source repository without requiring readers to understand internal phase numbering.

Source repository: `hollylessthan/metric-intent-assurance`  
Source commit: `58d753aa16dbd8e2372475f9002950f4aff7a498`

| Public artifact path | Original research path |
|---|---|
| `benchmark/canonical_cases.v1.1.jsonl` | `benchmarks/phase4/final/canonical_cases.v1.1.jsonl` |
| `benchmark/utterances.jsonl` | `benchmarks/phase4/utterances.jsonl` |
| `benchmark/leave_one_domain_out_folds.json` | `benchmarks/phase4/leave_one_domain_out_folds.json` |
| `benchmark/validation/human_validation_v1.json` | `benchmarks/phase4/adjudication/human_validation_v1.json` |
| `registries/commerce.json` | `registries/phase4/commerce/v1.json` |
| `registries/saas.json` | `registries/phase4/saas/v1.json` |
| `registries/support.json` | `registries/phase4/support/v1.json` |
| `evaluation/benchmark_freeze.json` | `config/phase4-freeze.json` |
| `evaluation/heldout_evaluation.json` | `config/phase5-heldout-evaluation.json` |
| `evaluation/study_protocol.json` | `config/phase5-study.json` |
| `evaluation/threshold_lock.json` | `config/phase5-threshold-lock.json` |
| `prompts/b0.txt` | `prompts/phase5/b0.txt` |
| `prompts/b1.txt` | `prompts/phase5/b1.txt` |
| `prompts/b2.txt` | `prompts/phase5/b2.txt` |
| `prompts/b4.txt` | `prompts/phase5/b4.txt` |
| `prompts/mia.txt` | `prompts/phase5/mia.txt` |

Some immutable identifiers inside frozen JSON records and code still contain historical strings such as `phase5-...` or `phase6...`. Those identifiers are preserved only when changing them would break traceability to sealed evidence; they are not part of the public repository navigation or conceptual model.
