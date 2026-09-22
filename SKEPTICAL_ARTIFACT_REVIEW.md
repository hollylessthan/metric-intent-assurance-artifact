# Skeptical Artifact Review

Date: 2026-09-21  
Scope: curated MIA publication artifact versus pinned research source commit `58d753aa16dbd8e2372475f9002950f4aff7a498`.

## Review question

Would an external reviewer be able to understand the study, inspect the frozen benchmark and method, trace the material paper claims to evidence, and reproduce the final reported results without relying on undocumented internal project history?

## Findings

### 1. Frozen data preservation — PASS

A Git-blob equality audit covered 29 critical benchmark, registry, configuration, prompt, and machine-readable evidence files after path renaming. All 29 are byte-identical to the pinned source commit. See `PRESERVATION_AUDIT.json`.

### 2. Public information architecture — PASS

The repository is organized by artifact function rather than internal roadmap phase. Public paths use `benchmark/`, `evaluation/`, `evidence/`, `prompts/`, `registries/`, `scripts/`, `src/`, and `tests/`. Historical paths survive only in `PROVENANCE_MAP.md` or immutable evidence identifiers.

### 3. Benchmark and governed context — PASS

The authoritative 300-case benchmark, 900 utterances, split metadata, three registry snapshots, adjudication/validation records, and sampled author quality-control record are present.

### 4. Final implementation — PASS

The final MIA-v2 parser/canonicalizer, grounding, deterministic assurance/validation, matched-baseline logic, contracts, and reference compilers are present. Artifact CI exercises the self-contained deterministic public checks.

### 5. Historical and negative evidence — PASS after remediation

The first packaging pass over-focused on final headline results. The review identified missing negative/development and contract-validity evidence. The artifact now includes:
- frozen historical controlled-study result records;
- historical policy/scaling analysis;
- the unfavorable/mixed pre-v2 challenge and immutable run binding;
- the 72-case independent action-contract study and instruction-harmonization sensitivity;
- the top-N benchmark-defect sensitivity.

This is important because the public artifact should preserve evidence that narrows claims, not only evidence favorable to MIA.

### 6. Final-v2 compact evidence — PASS

The final regression summary, final challenge summary/freeze, top-N sensitivity, final architecture code, prompts, and bounded reviewer-facing values are present. `EVIDENCE_INDEX.md` maps each major evidence layer.

### 7. Raw final-v2 sealed payload — BLOCKER for standalone reproducibility

The raw final-v2 provider outputs and several derived matched-control/mechanism/clean-prompt artifacts remain GitHub Actions artifacts in the private research repository. Their immutable run IDs are known and documented, but the payloads are not yet physically present in this repository.

This does **not** invalidate the compact evidence summaries. It does mean the repository is not yet a standalone reproduction package.

Required before public release:
1. migrate the sealed final-v2 provider/evaluation/matched-control/mechanism/clean-prompt artifacts;
2. record artifact filenames, source run IDs/artifact IDs, and SHA-256 digests;
3. update reproduction commands to consume only public assets;
4. run the full clean-checkout reproduction from the new repository;
5. preserve the source-bound summaries and raw payloads without rewriting frozen results.

### 8. Restricted/internal material — PASS

Files explicitly marked `RESTRICTED`, private participant workbooks, internal skeptical-review notes, manuscript working files, credentials, and superseded orchestration machinery are intentionally excluded. Aggregate participant-study evidence is retained without publishing participant-specific source files.

## Skeptical conclusion

The curated repository is now **reviewer-complete at the compact evidence level** and preserves the frozen source record across the critical files checked. It is **not yet publication-complete at the raw reproducibility level** because sealed final-v2 payloads still need migration.

Keep the PR in draft until that final migration and clean standalone reproduction pass are complete.
