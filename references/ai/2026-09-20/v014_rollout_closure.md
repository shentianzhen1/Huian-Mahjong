# V0.14 PublicRollout closure — 2026-09-20

## Decision

`PublicRolloutAgent V0.14` is **not promoted**. `CurrentAgent` remains
`MeldAwareShantenAgent V0.10`.

This is a research closure, not a claim that rollout can never help. The tested
objective intervened frequently while tending to give up immediate ordinary
tile efficiency, and the paired pilot did not show a positive direction.

## 25-pair pilot

Source: PR #25 description, completed before the intervention-diagnostic PR.

- 25 paired seeds / 50 seat-swapped eight-hand matches
- V0.14 wins: 23
- V0.10 wins: 26
- ties: 1
- mean paired score delta (V0.14 - V0.10): **-23.28**
- paired deal-in delta: **+0.24**

The pilot was negative-direction and did not meet a promotion gate.

## 5-pair intervention diagnostic

Source: GitHub Actions run `35501860506`, fresh seeds
`400200..400204`, both seat orders.

- completed attempts: 10 / 10
- stopped attempts: 0
- mean V0.14 score delta per match: **-24.0**
- mean V0.14 deal-in delta per match: **+0.3**
- multi-discard decisions: 1070
- decisions that passed the rollout search gate: 596
- interventions versus V0.10: 240
- intervention rate among searched decisions: **40.27%**
- intervention rate among all multi-discard decisions: **22.43%**
- mean immediate live-copy delta on intervention: **-0.7583**
- mean immediate effective-type delta on intervention: **-0.25**
- interventions sacrificing immediate live copies: 75
- interventions preserving immediate live copies: 165
- interventions improving immediate live copies: **0**
- special-cutoff rate: **18.76%**

Interventions by ordinary shanten were spread across 0–5 rather than isolated
to one narrow phase, so the issue is not a single obvious shanten bucket.

## Interpretation boundary

The diagnostic supports a concrete engineering conclusion: do not spend more
evaluation budget scaling this exact V0.14 policy unchanged. It does **not**
prove that every public-information rollout design is inferior.

Future rollout/EV work should:

1. keep V0.10's immediate-efficiency guard unless a scored special-rule value
   justifies the sacrifice;
2. evaluate against the confirmed Youjin x4/x8/x16 match profile rather than
   ordinary-only proxies when Jin/Youjin is relevant;
3. reuse the research-only direct Youjin value index from PR #38 without
   treating that index as full EV;
4. wait for unresolved Qiangjin / Sanjindao / Gang-Hu / rob-kong settlement
   gaps before claiming full special-rule EV.

## Related merged infrastructure

- PR #37: latest-main Youjin special-aware paired A/B evaluation, identity-stable
  RNG across seat swaps. Its smoke pilot completed 5/5 pairs, 10/10 matches,
  0 UNKNOWN.
- PR #38: narrow direct one-draw Youjin value index using the confirmed entry,
  upgrade, fan and x4/x8 settlement logic. It explicitly reports
  `is_full_ev = False`.

