# Phase 4 pilot benchmark

This package contains the deterministic seed and final v1.1 gold for Paper 1's controlled Metric Intent Assurance benchmark: 300 canonical cases and two intended meaning-preserving paraphrases per case, producing 900 utterances across SaaS, commerce, and customer support.

## Files

- `canonical_cases.jsonl`: protected structural records with canonical IDs, seed actions/reasons, intents or causal non-execution evidence, provenance, split, and contrastive metadata.
- `utterances.jsonl`: protected flat utterance-level evaluation view.
- `validation_report.json`: deterministic structural QA and frozen hashes.
- `leave_one_domain_out_folds.json`: three transfer folds with source development, source test, target test, and excluded target-development IDs.
- `annotation/annotation_crosswalk.csv`: internal study-control mapping from opaque IDs to protected canonical IDs and seed actions; never distribute it.
- `annotation/human_question_intake.csv`: confidentiality-review intake for a future human-sourced subset.
- `annotator_distribution/`: the only allowlisted blinded input distribution for models and human reviewers.
- `../../registries/phase4/*/v1.json`: authoritative protected copies of the three registry snapshots.

The former full-human annotation worksheets under `annotation/` are archived fallback materials. The authoritative validation procedure is `../../docs/phase4-model-review-runbook.md`.

## Frozen seed design

| Property | Value |
|---|---:|
| Canonical cases | 300 |
| Utterances | 900 |
| Seed Execute / Clarify / Reject / Coverage Gap | 120 / 60 / 60 / 60 |
| Final v1.1 Execute / Clarify / Reject / Coverage Gap | 125 / 56 / 60 / 59 |
| Development / held-out test | 60 / 240 |
| Contrastive groups / cases | 120 / 240 |
| Leave-one-domain-out folds | 3 |
| Domains | 3 |
| Metrics per registry | 24 |
| Dimensions per registry | 30 |

Development and test use disjoint surface-template banks. Semantic families, paraphrase groups, and contrastive groups do not cross splits. Each contrastive pair declares and validates one governed semantic mutation. Filter utterances use closed registry-backed vocabularies. All source questions in this seed are synthetic and registry-derived.

## Rebuild and structural validation

```bash
python scripts/build_phase4_pilot.py --output-root .
python -m unittest tests.test_phase4_benchmark -v
```

The build is deterministic. Rebuilding must reproduce the hashes in `validation_report.json` and `config/phase4-freeze.json`. Default rebuilds preserve annotation and intake work. `--overwrite-annotation-assets` is destructive and should be used only before review begins.

## LLM-assisted language validation

Prepare the blinded provider-neutral run without reading protected gold:

```bash
python scripts/phase4_model_review.py prepare \
  --repo-root . \
  --output-root phase4_runs/prepared
```

The study ran GPT, Claude, and Gemini independently over the same 300 cases with exact frozen prompts and an exact JSON schema. A fixed 30-case subset was repeated for stability. Only after all three runs were locked did aggregation compare model recoverability with deterministic structural gold. One result-visible practitioner/author then reviewed the fixed stratified 100-case sample, producing 93 Correct, 7 Incorrect, and 0 Unsure judgments; the seven corrections were incorporated into v1.1. The seven unique stability disagreements were also reviewed and resolved. There was no second independent human annotator, expert adjudicator, or inter-annotator kappa under the executed protocol.

## Execution readiness

```bash
python scripts/phase4_execution_readiness.py \
  --repo-root . \
  --execute-duckdb \
  --output phase4_runs/execution_readiness.json
```

Compilation and execution are reported separately. The final v1.1 benchmark passes all 125 Execute cases on both generated MetricFlow and DuckDB domain fixtures. The held-out study is sealed; do not repair or regenerate the benchmark in place. Any later benchmark revision must receive a new version and must not replace the confirmatory v1.1 source.

## Research status

Phase 4 is **complete under the executed revised protocol**. The benchmark remains synthetic and registry-derived. The human sample's 93% exact judgment rate missed the preregistered 95% point target, and only 100/300 cases received direct human review. Use `../../docs/pre-paper-skeptical-review.md` and `../../docs/protocol-deviations-and-amendments.md` for the required paper limitations; do not describe all 300 cases as independently human adjudicated.
