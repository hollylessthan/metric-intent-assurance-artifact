# Phase 6B external-validity challenge results

Status: **frozen challenge execution complete; interpretation provisional pending trace-level failure decomposition**

Workflow run: `35403416152`  
Execution commit: `b134acea870b8d0726383fa4634f07e129a5af90`

## Design preserved

The challenge set contains 24 independently authored requests from three non-author practitioners. A separate qualified non-author reviewer froze expected outcomes before any MIA or baseline execution. Four cases were retained as `genuinely_unresolved` because the independently authored request and writer note conflicted; they are reported separately and are not forced into the resolved-action accuracy denominator.

The frozen comparison is B4 versus MIA on the two Phase 5 model families. No challenge case, expectation, Phase 5 prompt, threshold, registry, or policy was changed after outcomes were observed.

## Primary resolved-action results

| Provider | System | Correct / resolved | Exact action accuracy | Wilson 95% CI |
| --- | --- | ---: | ---: | --- |
| GPT | B4 | 11 / 20 | 0.55 | [0.342, 0.742] |
| GPT | MIA | 4 / 20 | 0.20 | [0.081, 0.416] |
| Claude | B4 | 8 / 20 | 0.40 | [0.219, 0.613] |
| Claude | MIA | 8 / 20 | 0.40 | [0.219, 0.613] |

Paired descriptive counts:

- GPT: B4-only correct 10; MIA-only correct 3; ties 7.
- Claude: B4-only correct 4; MIA-only correct 4; ties 12.

At face value, these end-to-end results do **not** support a broad claim that MIA's four-action decisions generalize better than B4 to independently authored requests. However, the aggregate score combines reviewer-label instability, candidate-generation errors, reference-compiler limitations, and a newly exposed grouped-entity contract mismatch. The trace-level decomposition in `docs/phase6b-challenge-trace-diagnostic.md` must be read together with this table before drawing a method-level generalization conclusion.

## Error-pattern interpretation

GPT MIA is strongly conservative on this challenge set. It predicts Reject for all six reviewer-expected Clarify cases, the one expected Coverage Gap, six of ten expected Execute cases, and correctly preserves all three expected Reject cases. This pattern is consistent with an over-rejection failure mode on independently worded requests rather than improved four-action discrimination.

Claude MIA shows a different pattern: it frequently maps expected Execute cases to Coverage Gap, while recovering four of six expected Clarify cases, one of three expected Reject cases, and the single expected Coverage Gap.

These are descriptive patterns only. They do not identify whether the root cause is candidate generation, natural-language interpretation, registry grounding, or the downstream deterministic assurance layer without further trace-level analysis.

## Provider-failure disclosure

GPT completed all 48 B4/MIA calls with no terminal failures.

Claude produced seven terminal `max_tokens` failures, all in the MIA arm. The frozen `fail_closed_invalid_output_v1` policy maps terminal provider/normalization failure to Clarify. Three of the seven failures were on genuinely unresolved cases and are outside the action-accuracy denominator. Four failures were on resolved cases whose reviewer-expected action was Clarify; therefore four of Claude MIA's eight exact-action matches are fail-closed fallback matches rather than successfully normalized MIA semantic outputs.

The primary result remains the frozen policy result above. This failure composition must be disclosed alongside it; it should not be hidden by rerunning or selectively replacing provider outputs.

## Generality claim

The challenge experiment narrows the paper's external-validity claim.

The defensible interpretation is:

- Phase 5 remains the confirmatory evaluation of the frozen benchmark.
- Phase 6B challenge evidence shows that independent request authors produce materially different language and edge cases.
- MIA's deterministic safety contract still fail-closes on invalid outputs, but the end-to-end four-action classification advantage observed in the benchmark does not transfer uniformly to this independent challenge set.
- The paper should therefore claim evidence for governed decision behavior on the benchmark and explicitly bounded transfer, not broad production-domain generalization.

No challenge case should be removed or redesigned because of this unfavorable/mixed outcome.

## Source binding

Machine-readable evaluation:
`reports/phase6b/challenge_evaluation.run35403416152.json`

Artifact/run binding:
`reports/phase6b/challenge_run_binding.run35403416152.json`

GitHub Actions artifact digests and individual run-report hashes are preserved in the binding record.
