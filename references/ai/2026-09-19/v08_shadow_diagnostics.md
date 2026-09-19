# V0.8 decision-level shadow diagnostics — 2026-09-19

## Purpose

V0.8 failed independent score confirmation despite a positive first pilot.
Instead of tuning more weights, this diagnostic replayed **V0.6 as the live
policy** and asked V0.8 for a shadow decision on the exact same public
observation. Shadow decisions never changed the played trajectory.

Actions run: 35428021040

Four independent 5-match blocks:
- 80000–80004
- 82000–82004
- 84000–84004
- 86000–86004

All 20 matches completed.

## Aggregate decision counts

Across the V0.6 trajectories:

- all decisions: **15,118**
- discard decisions: **5,004**
- no exact V0.3 offense tie: **2,784**
- exact V0.3 offense ties: **2,220** (**44.36%** of discards)
- exact ties resolved by deterministic two-ply metrics: **1,204**
- exact ties still tied after two-ply and sent to V0.6 risk: **1,016**
- V0.8 changed the V0.6 discard: **780** (**15.59%** of all discards)
- changed because two-ply directly resolved the tie: **673**
- changed only after two-ply remained tied and V0.6 risk was applied: **107**

Thus most behavioral difference comes from the two-ply layer itself, not from
a different invocation of the risk model.

## Change rate by current ordinary shanten

| Shanten | Discards | V0.8 changes | Change rate |
|---:|---:|---:|---:|
| 0 | 1,328 | 26 | 1.96% |
| 1 | 1,415 | 215 | 15.19% |
| 2 | 1,034 | 247 | 23.89% |
| 3 | 752 | 192 | 25.53% |
| 4 | 363 | 89 | 24.52% |
| 5 | 89 | 8 | 8.99% |
| 6 | 22 | 3 | 13.64% |
| 7 | 1 | 0 | 0% |

The largest behavioral intervention is therefore at shanten 2–4, where a
two-ply horizon is least capable of representing the full route to a winning
hand.

## Qualitative finding

The stored changed-decision samples repeatedly show extremely small two-ply
differences causing an override, for example expected next-state live-copy
values such as 26.50 vs 26.54, 12.47 vs 12.36, 31.17 vs 31.18, etc.

This supports the interpretation that V0.8 is over-responsive to local
two-step differences, especially in medium-shanten states. That is consistent
with the observed A/B instability: first pilot positive, independent
confirmation flat/negative.

## Next experiment

Do not tune an arbitrary global epsilon first.

V0.9 should apply deterministic two-ply offense only at **ordinary shanten 1**
inside the exact V0.3 offense-tie frontier. At shanten 0 or shanten >=2, keep
the promoted V0.6 risk tie-break unchanged.

Rationale: at shanten 1, a draw + best discard horizon directly describes the
transition toward tenpai / improved one-shanten quality. At shanten 2–4 the
same two-step horizon is structurally myopic.

V0.9 remains experimental until fresh-seed paired 8-hand A/B beats CurrentAgent
V0.6.
