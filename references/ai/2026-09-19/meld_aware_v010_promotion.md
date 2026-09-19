# MeldAwareShantenAgent V0.10 Promotion Evidence

Date: 2026-09-19

## Decision

Promote `MeldAwareShantenAgent` to:

- `CurrentAgent`
- `CURRENT_AGENT_VERSION = "v0.10"`
- `CURRENT_AGENT_NAME = "MeldAwareShantenAgent"`

Keep `TenpaiRiskTieBreakAgent V0.6` and `ShantenAgent V0.3` as fixed comparison/ablation baselines.

## Policy delta from V0.6

V0.10 inherits V0.6 discard behavior unchanged. It only changes optional CHI/PENG decisions after an opponent discard.

For every claim opportunity:

1. PASS keeps the current concealed hand and evaluates ordinary offense.
2. Each legal CHI/PENG is projected as a fixed exposed meld.
3. The mandatory post-claim discard is optimized with the same shanten/live-effective-tile engine.
4. The claim is taken only if the resulting offense tuple is strictly better:
   - lower shanten;
   - then more live effective copies;
   - then more effective tile types.
5. If Jin is already in hand, the policy conservatively PASSes because Youjin/special EV is still outside this ordinary claim evaluator.
6. Kongs are not changed by V0.10.

This keeps the new behavior narrow and auditable.

## Pilot validation

Opponent: `TenpaiRiskTieBreakAgent V0.6`

Design:

- 100 paired seeds
- seat swap for every seed
- 200 complete 8-hand matches
- fixed-wall paired evaluation
- no UNKNOWN stops

Seed regions:

- 160000–160024
- 162000–162024
- 164000–164024
- 166000–166024

Results:

- V0.10 match wins: 121
- V0.6 match wins: 78
- ties: 1
- mean paired final-score delta V0.10 - V0.6: +67.32
- claim opportunities: 5,611
- CHI taken: 1,141
- PENG taken: 497
- claim PASS: 3,815
- Jin-in-hand guard PASS: 2,467

The policy changed enough decisions to be meaningful rather than benefiting from a tiny number of rare claims.

## Independent confirmatory validation

Completely disjoint seeds:

- 168000–168024
- 170000–170024
- 172000–172024
- 174000–174024

Design:

- another 100 paired seeds
- another 200 complete 8-hand matches
- no UNKNOWN stops

Results:

- V0.10 match wins: 118
- V0.6 match wins: 81
- ties: 1
- mean paired final-score delta: +42.29
- pooled SD across the 100 paired deltas: 159.69
- SE: 15.97
- approximate 95% CI for mean delta: +10.99 to +73.59
- mean paired deal-in delta: about -0.48
- claim opportunities: 5,604
- CHI taken: 1,021
- PENG taken: 506
- claim PASS: 3,890
- Jin-in-hand guard PASS: 2,572

One of four 25-seed regions was negative, so the policy is not universally dominant on every local seed block. The pooled independent confirmation nevertheless remains positive with the interval above zero.

## Combined evidence

Across both stages:

- 200 paired seeds
- 400 complete 8-hand matches
- V0.10 wins: 239
- V0.6 wins: 159
- ties: 2
- combined mean paired score delta: +54.805
- total claim opportunities: 11,215
- total CHI taken: 2,162
- total PENG taken: 1,003

Promotion is based primarily on the independent confirmatory batch, not on the combined mean alone.

## Guardrails

- V0.10 does not infer UNKNOWN special-win settlement.
- It does not use opponent concealed tiles or wall order.
- It does not modify the promoted V0.6 discard tie-break model.
- Jin-in-hand claim decisions stay conservative until Youjin/special EV is modeled.
- Kongs remain outside this claim policy.
- Future versions must beat V0.10 on disjoint paired seeds before promotion.

## Shanten-engine validation added alongside promotion

The ordinary shanten/effective-tile engine is cross-checked against the exact structural Hu solver on deterministic random samples:

- complete 17-tile hands;
- 16-tile tenpai / winning-next-draw existence;
- gold-wildcard cases;
- one fixed open-meld cases.

The full test suite remained green after these cross-checks.
