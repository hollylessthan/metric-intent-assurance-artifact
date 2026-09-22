# Independent Action-Contract Study

This record summarizes the frozen 72-case blind study used to evaluate whether independent non-author annotators could recover the four-action decision contract: **Execute**, **Clarify**, **Reject**, and **Coverage Gap**.

## Design

Two independent non-author annotators each completed the same 72 blinded cases using request, context, and governed registry evidence. The primary endpoint was exact agreement on the four-action decision. The dependence structure contained 65 clusters, including seven repeated two-case contrastive groups. Uncertainty was estimated with 10,000 contrastive-group cluster-bootstrap replicates.

No benchmark labels, system predictions, thresholds, or provider outputs were changed based on this study.

## Primary agreement

- exact action agreement: **72/72 (100%)**
- Wilson 95% interval: **94.93%–100%**
- unweighted Cohen's kappa: **1.00**
- cluster-bootstrap 95% interval for kappa: **1.00–1.00**

This supports recoverability of the four-action contract on the observed study cases. It does **not** establish agreement on every canonical intent slot.

## Comparison with frozen benchmark labels

Before instruction harmonization, each annotator agreed with the frozen benchmark action on **59/72 (81.94%)** cases.

Eight of the 13 apparent discrepancies were later identified as instruction-confounded Reject-versus-Coverage-Gap cases: the simplified human instructions did not reproduce the benchmark's original boundary for invalid named versions and invalid entity paths. A post-hoc harmonized re-review restored the original boundary and all three reviewers selected Reject on all eight cases.

Under that harmonized interpretation:

- benchmark-action agreement becomes **67/72 (93.06%)**
- five substantive disputes remain
- frozen benchmark labels remain unchanged

The five remaining disputes concern three generic-`segment` Clarify-versus-Execute cases and two effective-time Execute-versus-Clarify cases.

## Evidence files

- `action-contract-study.json`: machine-readable primary agreement analysis
- `action-contract-harmonization.json`: post-hoc instruction-harmonization sensitivity

The original private participant workbooks are not part of the public artifact. This public package preserves aggregate study evidence without publishing participant-specific material.
