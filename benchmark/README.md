# Benchmark

This directory contains the frozen benchmark used to evaluate Metric Intent Assurance (MIA).

## Contents

- `canonical_cases.v1.1.jsonl`: authoritative 300-case gold benchmark.
- `utterances.jsonl`: 900 natural-language request variants derived from the canonical cases.
- `leave_one_domain_out_folds.json`: frozen transfer/evaluation folds.
- `adjudication_report.json`: benchmark adjudication summary.
- `validation/human_validation_v1.json`: fixed human-validation sample results.
- `execution_readiness.json`: compiler/runtime readiness evidence for gold Execute cases.
- `validation_report.json`: deterministic benchmark validation summary.

The benchmark spans three synthetic enterprise domains: SaaS, commerce, and customer support. The frozen split contains 60 development cases and 240 held-out test cases (720 held-out utterances).

## Registry binding

Each benchmark case is bound to an immutable registry snapshot through its recorded registry hash. The packaged registry files are:

- `../registries/saas.json`
- `../registries/commerce.json`
- `../registries/support.json`

## Immutability

The benchmark is frozen evidence. Packaging must not rewrite labels, gold intents, splits, or provenance hashes. Corrections or sensitivity analyses must be stored separately rather than mutating this benchmark.

For the mapping back to the original research repository paths, see `../PROVENANCE_MAP.md`.
