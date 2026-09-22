# Generated Phase 6 quantitative results

Generated from the byte-bound Phase 5 confirmatory and ablation artifacts.

## Main safety–coverage table

| Family | System | UER | CEC | Action Macro-F1 |
| --- | --- | ---: | ---: | ---: |
| GPT | B0 | 79.62 | — | 18.92 |
| GPT | B1 | 83.45 | 42.90 | 16.19 |
| GPT | B2 | 87.05 | 48.84 | 15.88 |
| GPT | B3 | 85.61 | 48.84 | 15.95 |
| GPT | B4 | 14.63 | 28.05 | 73.57 |
| GPT | MIA | 5.76 | 40.26 | 42.40 |
| Claude | B0 | 32.61 | — | 24.92 |
| Claude | B1 | 27.58 | 60.40 | 24.78 |
| Claude | B2 | 27.58 | 62.71 | 25.20 |
| Claude | B3 | 17.75 | 59.74 | 28.71 |
| Claude | B4 | 11.75 | 57.10 | 68.05 |
| Claude | MIA | 5.04 | 61.06 | 54.12 |

## Contract-valid-only sensitivity

| Family | System | UER denominator | UER | CEC denominator | CEC |
| --- | --- | ---: | ---: | ---: | ---: |
| GPT | B1 | 405 | 85.93 | 292 | 44.52 |
| GPT | B4 | 416 | 14.66 | 298 | 28.52 |
| GPT | MIA | 346 | 6.94 | 298 | 40.94 |
| Claude | B1 | 414 | 27.78 | 292 | 62.67 |
| Claude | B4 | 414 | 11.84 | 297 | 58.25 |
| Claude | MIA | 402 | 5.22 | 280 | 66.07 |

## Retained failure diagnostics

| Family | B0 | B1 | B2 | B4 | MIA | MIA non-Execute | MIA Execute |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GPT | 16 | 23 | 20 | 6 | 76 | 71 | 5 |
| Claude | 1 | 14 | 8 | 9 | 38 | 15 | 23 |

The full benchmark contains 12 authorization-primary cases: 12 development and 0 held-out.
GPT has 5 outputs across 4 cases where version is the sole recorded violation family.
Claude has 0 outputs across 0 cases where version is the sole recorded violation family.

## Fixed-candidate UER ablations

| Intervention | GPT change | Claude change |
| --- | ---: | ---: |
| Remove calibration | +14.87 pp (10.26–19.90) | +10.55 pp (6.02–15.56) |
| Remove grain/additivity constraints | +9.83 pp (5.71–14.50) | +7.19 pp (3.79–11.11) |
| Remove dimension/entity constraints | +5.28 pp (2.17–8.94) | +1.44 pp (0.46–2.66) |
| Remove time/version constraints | +0.48 pp (0.00–1.24) | +0.00 pp (0.00–0.00) |
| Remove policy constraints | +0.00 pp (0.00–0.00) | +0.00 pp (0.00–0.00) |
