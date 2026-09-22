# Release Handoff

## Current release state

The sealed evidence bundle has been uploaded successfully.

- Release tag: `artifact-v1.0`
- Release title: `MIA Publication Artifact v1.0`
- Asset: `mia-public-sealed-evidence-v1.zip`
- Size: `1,317,896` bytes
- SHA-256: `429b0e1b5e427d1bc9840163e032b36a07c74a71913c13d0469d557fcb89b93b`
- Scientific payload files: `68`
- Total ZIP members including bundle manifest/README: `70`

GitHub's reported asset digest matches the locally built bundle exactly.

## What the bundle contains

The bundle contains normalized sealed outputs, predictions, traces, matched-control evaluations, mechanism replay outputs, clean-prompt sensitivity outputs/audits, component-analysis reports, and the top-N sensitivity record.

It intentionally excludes provider transport evidence logs, duplicated request payloads, preflight-only artifacts, private participant materials, and files marked `RESTRICTED`.

## Verified reproduction

GitHub Actions run `35677608866` successfully:

1. checked out the artifact repository;
2. downloaded the release asset using repository authentication;
3. verified the ZIP SHA-256;
4. extracted the sealed evidence;
5. verified all 68 payload files against `BUNDLE_MANIFEST.json`;
6. installed the package;
7. compiled source/scripts;
8. ran the deterministic test suite.

This reproduction does not access the private research repository.

## Current repository visibility

The artifact repository is currently **private**. Therefore the browser/release URL works for authenticated users but an unauthenticated `curl` correctly returns 404.

When the repository is made public, rerun an unauthenticated download check:

```bash
curl -L --fail \
  -o mia-public-sealed-evidence-v1.zip \
  https://github.com/hollylessthan/metric-intent-assurance-artifact/releases/download/artifact-v1.0/mia-public-sealed-evidence-v1.zip

echo "429b0e1b5e427d1bc9840163e032b36a07c74a71913c13d0469d557fcb89b93b  mia-public-sealed-evidence-v1.zip" | sha256sum -c -
```

## Final source tag after merge

The current `artifact-v1.0` tag was created before the final closeout commits. It points to commit `2e515078bd90291f9482f1f3b5d23c641cb9d94d`.

After PR #1 is merged, create or retarget a final source-code tag to the merged artifact commit. The release asset itself does not need to be rebuilt: its hash-bound evidence contents are already final.

## Paper availability URL gate

Use this repository as the paper availability URL only after:

1. PR #1 is merged;
2. the final source tag points to the merged artifact state;
3. repository visibility is public (when appropriate for the submission process);
4. unauthenticated release-asset download and SHA-256 verification succeed.
