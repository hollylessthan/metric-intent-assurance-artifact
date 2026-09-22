# MIA-v2 fresh challenge-v2 protocol

Status: **completed and frozen**. This document preserves the pre-inference protocol; final provider evaluation was completed under workflow run `35431947015` after the request/task freeze.

## Purpose

Challenge-v2 is the clean generalization test for the frozen MIA-v2 implementation in `reports/mia-v2/freeze.json`.

It must not reuse Phase 6B challenge-v1 requests or the old 720-utterance Phase 5 benchmark as sources of challenge wording.

## Simplified credible design

Challenge-v2 separates **technical ground truth** from **natural-language expression**.

1. Authors precommit 24 hidden governed task cards against the synthetic Commerce, SaaS, and Support registries.
2. The expected governed outcome for each card is precommitted before writers see any card and is checked by a credential-free deterministic registry audit.
3. Two independent non-author writers each receive twelve cards. They see the business task and authorized context, but no canonical IDs, no expected action, no MIA terminology, and no model outputs.
4. Writers turn each card into a natural analytics request while preserving the supplied meaning.
5. The final 24 written requests are recorded in `reports/mia-v2/challenge-v2/final_requests.RESTRICTED.jsonl` and must be frozen before any provider inference.
6. GPT/Claude then run on the frozen requests using the already frozen MIA-v2 implementation.

There is **no separate 24-row human technical-label review**. The technical labels come from the precommitted task specification plus deterministic registry evidence. Human effort is reserved for the part that actually needs humans: natural wording.

## Why this is still credible

The design has three independent safeguards:

- **precommitment:** expected outcomes are sealed before independent writers produce the model-visible wording;
- **deterministic evidence:** task cards are checked against the same frozen registry/context semantics used by the system, so labels are not assigned after seeing model outputs;
- **independent language:** the authors do not write the final model-visible requests.

Challenge-v2 therefore tests whether the frozen MIA-v2 system generalizes to fresh natural-language realizations of governed tasks without creating another large annotation exercise.

This is a controlled external-validity test of **language/interpretation generalization**, not a claim that the task distribution itself was sampled from the population of all real enterprise analytics requests.

The already completed Phase 6B challenge-v1 remains complementary evidence because its requests were independently authored open-endedly. Challenge-v1 and challenge-v2 answer different validity questions and should be reported separately.

## Writer independence

- Writers must not be paper authors or MIA developers.
- Writers must not see challenge-v1 outcomes, Phase 5 benchmark labels/templates, MIA-v2 old-benchmark errors, expected actions, canonical registry IDs, or provider outputs.
- Each writer receives twelve cards: four Commerce, four SaaS, and four Support.
- Writers may phrase requests naturally, but must preserve the supplied metric meaning, grouping/filter requirements, time requirement, and any explicit definition requirement.
- Writers must not deliberately add/remove requirements or invent additional policy constraints.
- No request may be edited, dropped, or replaced after provider outputs are observed.

## Primary systems

Run on both frozen Phase 5 model families:

- B1
- B2
- B4
- MIA-v2

Derive B3 locally from B2. B0 is omitted from the primary challenge-v2 comparison because it cannot express the four-action governance contract directly.

## Evaluation

Primary metrics on all 24 frozen cases:

- action exact accuracy;
- four-action confusion matrix;
- unsafe execution rate;
- correct execution coverage on Execute cards;
- paired MIA-v2 vs B4 correctness counts;
- per-provider results.

No post-output relabeling is allowed. Any wording-quality issue discovered after inference remains part of the frozen record and is disclosed rather than repaired.

## Stop rule

After challenge-v2 inference, the frozen MIA-v2 implementation is not modified based on challenge-v2 outcomes. Any later revision is a new system version and requires a new fresh evaluation set.


## Historical pre-inference writer collection status

The following records the state immediately before the challenge freeze and provider inference. Writer collection was complete.

- Writer A: 12/12 requests returned.
- Writer B: 12/12 requests returned.
- Each writer contributed 4 Commerce, 4 SaaS, and 4 Support requests.
- All 24 request cells are non-empty.
- A pre-inference side-by-side fidelity check found that all 24 preserve the supplied task semantics.
- Writer text was not rewritten after return.
- At this historical checkpoint, no challenge-v2 provider call had occurred.

The subsequent repository freeze bound the request bytes, task/expectation precommit, writer intake provenance, and frozen MIA-v2 implementation. Provider inference and evaluation then completed under workflow run `35431947015`; the public summary is `evidence/challenge-v2-summary.json`.
