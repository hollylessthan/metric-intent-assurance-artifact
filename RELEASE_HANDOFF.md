# Public Release Handoff

The publication-safe sealed evidence bundle has already been built and verified locally.

## Bundle to attach

- File: `mia-public-sealed-evidence-v1.zip`
- Size: `1,317,896` bytes
- SHA-256: `429b0e1b5e427d1bc9840163e032b36a07c74a71913c13d0469d557fcb89b93b`
- Files: `70`
- Manifest: `SEALED_ARTIFACT_MANIFEST.json`

The bundle contains normalized sealed outputs, predictions, traces, matched-control evaluations, mechanism replay outputs, clean-prompt sensitivity outputs/audits, component-analysis reports, and the top-N sensitivity record.

It intentionally excludes provider transport evidence logs, duplicated request payloads, preflight-only artifacts, private participant materials, and files marked `RESTRICTED`.

## Recommended GitHub release

Create a release in this repository after PR #1 is merged:

- Tag: `artifact-v1.0`
- Title: `MIA Publication Artifact v1.0`
- Asset: `mia-public-sealed-evidence-v1.zip`

Attach the ZIP without modifying or recompressing it. After upload, verify that its SHA-256 remains:

`429b0e1b5e427d1bc9840163e032b36a07c74a71913c13d0469d557fcb89b93b`

## Release notes text

> Reproducibility evidence for the Metric Intent Assurance (MIA) publication artifact. The sealed bundle contains normalized model outputs, predictions, traces, matched-control results, mechanism replays, robustness analyses, and component reports used to support the paper's final reported results. Provider transport logs, redundant request payloads, private participant material, and restricted development files are intentionally excluded. See `SEALED_ARTIFACT_MANIFEST.json` for source workflow bindings and file-level SHA-256 hashes.

## Final verification after upload

1. Confirm the release asset filename is exactly `mia-public-sealed-evidence-v1.zip`.
2. Confirm its downloaded SHA-256 matches the value above.
3. Record the release URL and asset URL in `SEALED_ARTIFACT_MANIFEST.json`.
4. Update `REPRODUCIBILITY.md` to point to the public release asset.
5. Run the clean-checkout reproduction using only the artifact repository plus that release asset.
6. Run `python scripts/verify_sealed_artifacts.py --require-all` after extracting the asset under `evidence/sealed/`.
7. Mark PR #1 ready for review only after those checks pass.

## Current status

All source artifacts have been enumerated, safety-inspected, and hash-bound. The curated bundle is built. Repository CI is green. The only remaining publication-readiness action is attaching the immutable bundle and verifying the public copy.
