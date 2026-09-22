# Phase 6A evidence-hardening results

All policy and class analyses use sealed Phase 5 traces. Threshold curves are secondary descriptive analyses; held-out labels were not used to select a policy.

## GPT

| System | Held-out execute coverage | UER | CEC |
| --- | ---: | ---: | ---: |
| B1 | 88.89% | 83.45% | 42.90% |
| B4 | 45.56% | 14.63% | 28.05% |
| MIA fixed policy | 21.11% | 5.76% | 40.26% |

No B2 confidence cutoff matched MIA's development execute coverage within two percentage points; no GPT coverage-matched comparison is reported.

Selected development point: tau_e=0.96, tau_a=1.00, cost=168. 6 eligible grid points are within 5% of that cost.

| Action | MIA P | MIA R | MIA F1 | B4 P | B4 R | B4 F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| execute | 0.842 | 0.422 | 0.563 | 0.814 | 0.881 | 0.846 |
| clarify | 0.256 | 0.303 | 0.278 | 0.802 | 0.765 | 0.783 |
| reject | 0.512 | 0.764 | 0.613 | 1.000 | 0.361 | 0.531 |
| coverage_gap | 0.208 | 0.291 | 0.243 | 0.650 | 0.986 | 0.783 |

Macro-F1: MIA 0.424; B4 0.736.

### MIA confusion matrix (gold rows)

| Gold / predicted | Execute | Clarify | Reject | Coverage Gap |
| --- | ---: | ---: | ---: | ---: |
| execute | 128 | 23 | 56 | 96 |
| clarify | 19 | 40 | 33 | 40 |
| reject | 0 | 14 | 110 | 20 |
| coverage_gap | 5 | 79 | 16 | 41 |

### B4 confusion matrix (gold rows)

| Gold / predicted | Execute | Clarify | Reject | Coverage Gap |
| --- | ---: | ---: | ---: | ---: |
| execute | 267 | 17 | 0 | 19 |
| clarify | 30 | 101 | 0 | 1 |
| reject | 30 | 7 | 52 | 55 |
| coverage_gap | 1 | 1 | 0 | 139 |

## CLAUDE

| System | Held-out execute coverage | UER | CEC |
| --- | ---: | ---: | ---: |
| B1 | 56.39% | 27.58% | 60.40% |
| B4 | 47.08% | 11.75% | 57.10% |
| MIA fixed policy | 28.61% | 5.04% | 61.06% |
| Development-matched B2 | 54.03% | 23.26% | 61.72% |

Selected development point: tau_e=0.60, tau_a=0.00, cost=14. 21 eligible grid points are within 5% of that cost.

| Action | MIA P | MIA R | MIA F1 | B4 P | B4 R | B4 F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| execute | 0.898 | 0.611 | 0.727 | 0.855 | 0.957 | 0.903 |
| clarify | 0.686 | 0.447 | 0.541 | 0.860 | 0.652 | 0.741 |
| reject | 0.679 | 0.250 | 0.365 | 1.000 | 0.229 | 0.373 |
| coverage_gap | 0.365 | 0.972 | 0.531 | 0.552 | 0.972 | 0.704 |

Macro-F1: MIA 0.541; B4 0.681.

### MIA confusion matrix (gold rows)

| Gold / predicted | Execute | Clarify | Reject | Coverage Gap |
| --- | ---: | ---: | ---: | ---: |
| execute | 185 | 27 | 7 | 84 |
| clarify | 19 | 59 | 8 | 46 |
| reject | 0 | 0 | 36 | 108 |
| coverage_gap | 2 | 0 | 2 | 137 |

### B4 confusion matrix (gold rows)

| Gold / predicted | Execute | Clarify | Reject | Coverage Gap |
| --- | ---: | ---: | ---: | ---: |
| execute | 290 | 13 | 0 | 0 |
| clarify | 46 | 86 | 0 | 0 |
| reject | 0 | 0 | 33 | 111 |
| coverage_gap | 3 | 1 | 0 | 137 |

## Validator scaling

| Metrics | Median ms | p95 ms | p99 ms | Validations/s | Peak Python MiB |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 10 | 0.0069 | 0.0093 | 0.0330 | 126896.3 | 0.05 |
| 50 | 0.0116 | 0.0149 | 0.0631 | 75238.1 | 0.29 |
| 100 | 0.0169 | 0.0186 | 0.0884 | 53893.2 | 0.60 |
| 500 | 0.0586 | 0.0837 | 0.1805 | 15237.1 | 2.98 |
| 1,000 | 0.1222 | 0.2000 | 1.1472 | 6439.5 | 6.02 |
| 10,000 | 1.8216 | 2.2116 | 2.9147 | 531.1 | 60.04 |

### Candidate-count sweep at 1,000 metrics

| Candidates | Median batch ms | p95 batch ms | p99 batch ms | Median per candidate ms |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 0.1397 | 0.2013 | 0.2674 | 0.1397 |
| 2 | 0.2839 | 0.4024 | 0.5418 | 0.1420 |
| 4 | 0.5880 | 0.8639 | 1.1460 | 0.1470 |
| 8 | 1.1871 | 1.5381 | 1.9510 | 0.1484 |
| 16 | 2.4131 | 2.9880 | 3.4196 | 0.1508 |

Environment: AMD EPYC 9V74 80-Core Processor; 9 logical CPUs; Python 3.12.14; Linux-6.18.44-x86_64-with-glibc2.39 (x86_64).

The reference implementation performs linear scans for registry object and policy lookup. Peak memory is Python allocation measured while constructing the registry, not process RSS. These measurements characterize this implementation, not an indexed production registry.
