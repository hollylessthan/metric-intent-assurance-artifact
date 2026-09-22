# Development Challenge: Negative / Mixed Result

This record preserves the unfavorable independent-request challenge that preceded the final MIA-v2 design. It is retained because it materially informed later redesign and bounds the paper's generalization claims.

## Design

The challenge contains 24 independently authored requests from three non-author practitioners. A separate non-author reviewer fixed expected outcomes before system execution. Four cases were retained as genuinely unresolved and are excluded from resolved-action accuracy rather than forced into a label.

The frozen comparison used B4 and the earlier MIA implementation on GPT and Claude model families. No challenge case or expected outcome was removed because of the observed result.

## Resolved-action results

| Provider | System | Correct / resolved | Exact action accuracy |
| --- | --- | ---: | ---: |
| GPT | B4 | 11 / 20 | 55% |
| GPT | earlier MIA | 4 / 20 | 20% |
| Claude | B4 | 8 / 20 | 40% |
| Claude | earlier MIA | 8 / 20 | 40% |

Paired descriptive counts:

- GPT: B4-only correct 10; MIA-only correct 3; ties 7.
- Claude: B4-only correct 4; MIA-only correct 4; ties 12.

These results do **not** support a broad claim that the earlier MIA implementation generalized better than B4 to independently authored requests. They are retained as negative development evidence that motivated the final-v2 redesign.

## Provider-failure disclosure

GPT completed all B4/MIA calls without terminal failures.

Claude had seven terminal max-token failures in the MIA arm. The frozen fail-closed policy maps terminal provider/normalization failure to Clarify. Three failures occurred on genuinely unresolved cases; four occurred on resolved cases whose expected action was Clarify. Those four therefore count as policy-level action matches but not successfully normalized semantic outputs.

## Evidence files

- `challenge-evaluation.run35403416152.json`: machine-readable evaluation
- `development-challenge-run-binding.json`: immutable run/artifact binding

This negative result is historical evidence. It must not be presented as an evaluation of the final MIA-v2 architecture.
