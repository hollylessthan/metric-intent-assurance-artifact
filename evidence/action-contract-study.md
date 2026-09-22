# Phase 6B main independent annotation results

Status: **main annotation complete; benchmark-discrepancy review pending**

This record reports the frozen 72-case Phase 6B blind independent annotation study. It does not modify Phase 5 benchmark v1.1, labels, thresholds, predictions, or confirmatory results.

## Frozen inputs

- Main-study freeze commit: `f1e9e85ba98cebf3e5b330f0e67d91589f02e880`
- Restricted main manifest SHA-256: `392fb75b08fb6bcd0e6e5217e0c1f97091742f764df6e1a9e5dd1cd6f24ec650`
- Bootstrap seed: `20260915`
- Bootstrap replicates: `10000`
- Bootstrap unit: `contrastive_group`; singleton cases remain singleton clusters
- Annotator A workbook Drive file id: `1Gxw9RZlI0GhkfL1oQ7ryvO-LxWJA4P3H`
- Annotator A workbook SHA-256: `825f23b94c0f9eafe60d274584b9f1ce8682daa174eea3d0da6f5d0fcd8489f8`
- Annotator B workbook Drive file id: `1xjjkpcRMcfC-2OkSgx9wBQv1WykUBgYh`
- Annotator B workbook SHA-256: `a872e2e82133a34ecae2f2060725e0488ab70b557b4a7bc8fa22079d863d1164`

Both workbooks contain 72 completed cases and aligned study-case IDs.

## Primary agreement result

The two independent annotators selected the same four-action decision on all 72 cases:

- raw action agreement: **72/72 = 100%**
- Wilson 95% interval for raw agreement: **[94.93%, 100%]**
- unweighted Cohen's kappa: **1.00**
- 10,000-replicate contrastive-group cluster-bootstrap 95% interval for kappa: **[1.00, 1.00]**
- defined bootstrap replicates: **10,000/10,000**

Under the frozen interpretation bands, this is **meaningful support** that qualified practitioners can recover the four-action contract from the supplied request, context, and registry evidence.

The manifest contains 65 dependence clusters, including seven repeated two-case contrastive groups.

## Comparison with frozen benchmark actions

Each annotator agrees with the frozen gold action on **59/72 = 81.94%** of cases (Wilson 95% interval **[71.52%, 89.13%]**). Because the annotators have identical action vectors, their gold confusion matrices are identical.

| Frozen gold | Annotator Execute | Clarify | Reject | Coverage Gap |
| --- | ---: | ---: | ---: | ---: |
| Execute (30) | 28 | 2 | 0 | 0 |
| Clarify (13) | 3 | 10 | 0 | 0 |
| Reject (15) | 0 | 0 | 7 | 8 |
| Coverage Gap (14) | 0 | 0 | 0 | 14 |

There are **13 unanimous annotator-versus-gold discrepancies**. They fall into four repeated mechanisms:

1. **Absent requested version: 4 cases.** Frozen gold is Reject; both annotators choose Coverage Gap.
2. **Missing governed entity path: 4 cases.** Frozen gold is Reject; both annotators choose Coverage Gap.
3. **Unspecified choice among multiple registered versions: 2 cases.** Frozen gold is Execute; both annotators choose Clarify.
4. **Generic "segment" reference: 3 cases.** Frozen gold is Clarify; both annotators choose Execute using the only evident registered segment dimension.

The first three mechanisms map directly to clarifications frozen after the instruction pilot: absent governed concepts/paths/versions are treated as Coverage Gap, and registry default/version metadata does not automatically resolve user intent when multiple registered definitions remain viable. This makes the 13 cases benchmark-discrepancy candidates, not inter-annotator disagreements.

They are recorded in `reports/phase6b/annotation_discrepancies.jsonl` with status `pending_separate_review`.

## Secondary interpretation fields

For the 31 cases both annotators label Execute, exact normalized string equality of the full plain-language interpretation is 0/31. This should **not** be interpreted as semantic disagreement: the frozen human-response protocol deliberately allowed plain analytics language rather than canonical schema fields, so wording and naming conventions differ mechanically.

The most stable directly comparable field is breakdown/grouping, which matches exactly on 31/31 Execute cases. Free-text metric naming, filter phrasing, time-period wording, rationale, and non-Execute explanations are retained as descriptive evidence rather than promoted to the primary reliability statistic.

## Required next step

No inter-annotator adjudication is needed because there are zero action disagreements.

The frozen-label correction policy does require a separate review of the 13 annotator-versus-gold discrepancies. Original responses and Phase 5 v1.1 remain immutable. A confirmed benchmark issue may only be reserved for a future benchmark version; Phase 5 must not be rescored.

For stronger publication evidence, use a qualified independent reviewer to classify only these 13 discrepancy cases from blinded request/context/registry evidence, without showing the frozen gold or annotator consensus. Record that review separately as the adjudication/discrepancy-review log.

A post-hoc sensitivity excluding confirmed disputed cases may be reported if decision-relevant, but it must not replace the confirmatory Phase 5 result.


## Post-review correction to interpretation

A later protocol audit found that eight of the 13 annotator-versus-gold discrepancies are **instruction-confounded**, not clean benchmark-label disagreements. The original Phase 4 taxonomy intentionally classifies invalid named versions and invalid entity paths as Reject, while the simplified Phase 6B human contract described unrepresented versions/entity paths under Coverage Gap. This mismatch affects four version cases and four entity-path cases.

Accordingly, those eight cases must not be treated as evidence that v1.1 is mislabeled. The substantive follow-up set is five cases: three generic-`segment` Clarify-versus-Execute cases and two effective-time Execute-versus-Clarify cases. See `docs/phase6b-discrepancy-review-results.md`.
