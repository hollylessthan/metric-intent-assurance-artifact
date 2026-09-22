# MIA-v2 freeze record

Status: **frozen before fresh challenge-v2 inference**

This record closes the old-benchmark MIA-v2 development loop and fixes the implementation boundary used for the fresh challenge-v2 evaluation.

## Freeze point

- Base commit: `e41469944641c3060c8eceea526944587323ce40`
- Prompt version: `mia-v2-minimal-v3-semantic-coverage`
- Final old-benchmark provider run: `35426074276`
- Final credential-free evaluation run: `35429477378`
- Final evaluation artifact: `10580057349`
- Final evaluation digest: `sha256:1a1f933ba651eadd93987a125ec4c21d8928eb5698aa8e3d443ddfac0c67df93`

## Frozen provider settings

| Provider | Model | Execute threshold | Ambiguity margin | Decoding |
| --- | --- | ---: | ---: | --- |
| GPT | `gpt-5.4-mini-2026-03-17` | 0.96 | 1.00 | max output 1200; reasoning none; temperature 0 |
| Claude | `claude-sonnet-5` | 0.60 | 0.00 | max output 1200; reasoning low; provider-default temperature |

These are retained from the frozen Phase 5 threshold lock for comparability.

## Compiler boundary

Mixed-entity semantic requests remain fail-closed as `GAP_COMPOSITION` unless a separately demonstrated and separately frozen end-to-end semantic-compiler capability path exists before challenge-v2 inference.

No new mixed-entity Execute claim is introduced by this freeze.

## Old-benchmark closure

The 720-utterance Phase 5 benchmark is now closed for result-driven MIA-v2 development.

Final post-hoc MIA-v2 results:

| Provider | UER | CEC | Macro-F1 |
| --- | ---: | ---: | ---: |
| GPT | 0.72% | 82.84% | 75.12% |
| Claude | 4.80% | 78.22% | 75.48% |

These remain post-hoc because the old benchmark informed MIA-v2 development. They do not replace MIA-v1 confirmatory Phase 5 results.

## Challenge-v2 gate

Before any challenge-v2 provider call:

1. hidden governed task cards must have known expected behavior;
2. independent writers must phrase requests without seeing canonical IDs or expected actions;
3. written requests and expectation records must be frozen;
4. credential-free preflight must verify exact cases, model IDs, call counts, and cost caps;
5. the frozen MIA-v2 implementation in `reports/mia-v2/freeze.json` must be used without result-driven modification.

If implementation changes after this freeze, challenge-v2 inference must not proceed under this freeze record; a new freeze record is required before provider calls.
