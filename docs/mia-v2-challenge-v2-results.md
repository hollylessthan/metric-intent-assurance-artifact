# MIA-v2 fresh challenge-v2 results

Status: **prospective frozen final-method language-generalization evidence**

## Provenance

- workflow run: `35431947015`
- workflow conclusion: `success`
- source commit: `4a618a98caf4a6d823edc936c04c6d3af422dc76`
- workflow: `.github/workflows/mia-v2-challenge-v2.yml`
- evaluation artifact: `mia-v2-challenge-v2-evaluation-35431947015`
- evaluation artifact ID: `10580644552`
- evaluation artifact digest: `sha256:6f75683cbc47320801f1d0db44a02afd4731ecb3048a1710544ffc0b82d3a4ae`
- GPT artifact digest: `sha256:13685afbd291c7150010fb1d588f3e44078090d94b7f8d0d39dfbbe8dafd4827`
- Claude artifact digest: `sha256:a720b8db0b62ee278e73fff68480ff82546af8feb34cc8290278d978e16123b0`
- preflight artifact digest: `sha256:3392ce30b52bb297621eb8845ca13205850371496b1f70e7b1a382f6ac2e9206`

All workflow jobs completed successfully: contract tests, preflight, explicit authorization, GPT execution, Claude execution, and sealed evaluation.

## Frozen design

- 24 cases total.
- 11 precommitted Execute cases.
- 13 precommitted non-Execute cases.
- 2 independent non-author writers.
- 12 requests per writer.
- each writer contributed 4 Commerce, 4 SaaS, and 4 Support requests.
- writer requests were stored verbatim.
- task cards and expectations were frozen before provider inference.
- final MIA-v2 implementation was frozen before challenge construction.
- provider-visible packets exclude gold/task expectations.
- callable systems: B1, B2, B4, MIA-v2.
- B3 derived locally from B2.
- both frozen model families were evaluated.

## Results

| Provider | System | Action exact | UER | CEC |
| --- | --- | ---: | ---: | ---: |
| GPT | B1 | 11/24 = 45.83% | 11/13 = 84.62% | 11/11 = 100.00% |
| GPT | B2 | 11/24 = 45.83% | 10/13 = 76.92% | 11/11 = 100.00% |
| GPT | B3 | 11/24 = 45.83% | 10/13 = 76.92% | 11/11 = 100.00% |
| GPT | B4 | 15/24 = 62.50% | 7/13 = 53.85% | 9/11 = 81.82% |
| GPT | MIA-v2 | **20/24 = 83.33%** | **0/13 = 0%** | **10/11 = 90.91%** |
| Claude | B1 | 10/24 = 41.67% | 4/13 = 30.77% | 10/11 = 90.91% |
| Claude | B2 | 11/24 = 45.83% | 5/13 = 38.46% | 11/11 = 100.00% |
| Claude | B3 | 11/24 = 45.83% | 3/13 = 23.08% | 11/11 = 100.00% |
| Claude | B4 | 18/24 = 75.00% | 2/13 = 15.38% | 11/11 = 100.00% |
| Claude | MIA-v2 | **20/24 = 83.33%** | **0/13 = 0%** | **11/11 = 100.00%** |

MIA-v2 action-exact Wilson 95% interval in both model families: **[64.15%, 93.32%]**.

## Paired action correctness

Against B4:

- GPT: MIA-v2-only correct = 5; B4-only correct = 0; ties = 19.
- Claude: MIA-v2-only correct = 2; B4-only correct = 0; ties = 22.

Against B1:

- GPT: MIA-v2-only correct = 10; B1-only correct = 1; ties = 13.
- Claude: MIA-v2-only correct = 10; B1-only correct = 0; ties = 14.

## MIA-v2 residual errors

GPT MIA-v2 confusion:

- 3/3 Clarify correct.
- 3/3 Coverage Gap correct.
- 10/11 Execute correct; 1 Execute→Clarify.
- 4/7 Reject correct; 3 Reject→Coverage Gap.
- 0 non-Execute→Execute.

Claude MIA-v2 confusion:

- 3/3 Clarify correct.
- 3/3 Coverage Gap correct.
- 11/11 Execute correct.
- 3/7 Reject correct; 4 Reject→Coverage Gap.
- 0 non-Execute→Execute.

The remaining errors are therefore conservative action-taxonomy errors rather than unsafe execution.

## Interpretation boundary

The result supports a prospective statement:

> After final-method freeze, MIA-v2 made no unsafe executions among 13 non-Execute fresh challenge cases in either model family while retaining 10/11 GPT and 11/11 Claude correct Execute cases.

Do not convert this into a general claim that population UER is zero. The challenge contains 24 controlled cases and tests language/interpretation generalization under precommitted governed task semantics.
