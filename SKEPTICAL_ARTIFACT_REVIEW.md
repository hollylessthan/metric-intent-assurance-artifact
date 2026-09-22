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

The final MIA-v2 parser/canonicalizer, grounding, deterministic assurance/validation, matched-baseline logic, contracts, and reference compilers are present. Artifact CI exercises the self-contained deterministic checks.

### 5. Historical and negative evidence — PASS after remediation

The first packaging pass over-focused on final headline results. The review identified missing negative/development and contract-validity evidence. The artifact now includes:
- frozen historical controlled-study result records;
- historical policy/scaling analysis;
- the unfavorable/mixed pre-v2 challenge and immutable run binding;
- the 72-case independent action-contract study and instruction-harmonization sensitivity;
- the top-N benchmark-defect sensitivity.

This matters because the artifact should preserve evidence that narrows claims, not only evidence favorable to MIA.

### 6. Final-v2 compact evidence — PASS

The final regression summary, final challenge summary/freeze, top-N sensitivity, final architecture code, prompts, and bounded reviewer-facing values are present. `EVIDENCE_INDEX.md` maps each major evidence layer.

### 7. Final-v2 sealed payload transfer — PASS

The relevant final-v2 workflow artifacts were enumerated, downloaded, safety-inspected, and hash-bound in `SEALED_ARTIFACT_MANIFEST.json`. The publication-safe normalized outputs, predictions, traces, and compact result reports were repackaged into `mia-public-sealed-evidence-v1.zip` and attached under release tag `artifact-v1.0`.

GitHub reports the expected:
- size: 1,317,896 bytes;
- SHA-256: `429b0e1b5e427d1bc9840163e032b36a07c74a71913c13d0469d557fcb89b93b`.

The ZIP contains an internal `BUNDLE_MANIFEST.json` covering 68 scientific payload files. CI downloads the release asset, verifies the outer ZIP SHA-256, extracts it, verifies all 68 payload hashes, installs the artifact package, compiles the source/scripts, and runs the deterministic test suite.

### 8. Clean standalone reproduction — PASS under current private access

GitHub Actions run `35677608866` passed both:
- `deterministic-checks`;
- `public-release-reproduction` (authenticated because the repository is currently private).

The reproduction job succeeded at:
1. checking out the artifact repository;
2. downloading the release asset;
3. verifying its SHA-256;
4. extracting the bundle;
5. verifying every manifest-listed sealed payload;
6. installing the package;
7. compiling source/scripts;
8. running the deterministic tests.

No access to the private research repository was required.

### 9. Restricted/internal material — PASS for the curated artifact

Files explicitly marked `RESTRICTED`, private participant workbooks, internal skeptical-review notes, manuscript working files, credentials, provider transport evidence logs, and superseded orchestration machinery are intentionally excluded. Aggregate participant-study evidence is retained without participant-specific source files.

The changed-path review found no restricted/credential/manuscript/private-participant paths. The sealed bundle itself was separately safety-inspected before packaging. A broad repository-wide regex scan was not used as the sole basis for this conclusion because the connector hit its per-call limit; the conclusion rests on curated-source selection, bundle inspection, changed-path review, and successful reproduction/hash checks.

## Remaining publication-access items

These are not blockers for PR readiness:

1. The repository is still private, so unauthenticated reviewer access is not yet expected. After changing repository visibility to public, repeat the release download without authentication.
2. The existing `artifact-v1.0` release tag was created before the final closeout commits. After merge, create/retarget a final source-code tag so the repository snapshot and release documentation point to the final merged artifact state.

## Skeptical conclusion

The curated repository is **reviewer-complete and standalone-reproducible under its current authenticated/private access model**. The frozen source record is preserved, negative evidence is retained, the sealed evidence bundle is hash-bound and reproduced successfully, and no dependency on the private research repository remains.

PR #1 is ready for review. Public paper-URL readiness should be declared only after repository visibility is changed and unauthenticated release-asset access is verified.
