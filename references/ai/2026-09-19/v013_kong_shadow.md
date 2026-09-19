# V0.13 KONG candidate shadow evaluation

Date: 2026-09-19

Status: **NOT PROMOTED — CurrentAgent remains V0.10**

## Candidate boundary

`KongAwareMeldAgent V0.13-shadow` extends the existing V0.10 decision flow but
only takes a legal `AN_GANG` or `MING_GANG` when all of the following hold:

- the ordinary pre-draw structure is exactly equal to the best current action;
- the projection has no `rob_kong` or `gang_hu_scoring` blocker;
- the player is not holding the gold tile, avoiding unresolved special windows;
- V0.10 has not already selected a strict CHI/PENG improvement.

`ADD_KONG` is never selected. `CurrentAgent` is unchanged.

## Evaluation

- Fresh seeds: `300000..300024`
- 25 seed pairs, original and swapped seats
- 50 complete eight-hand matches
- 0 incomplete/UNKNOWN pairs

| Metric | V0.13-shadow | V0.10 |
|---|---:|---:|
| Match wins | 26 | 24 |
| Average final score | 997.56 | 1002.44 |
| Average deal-ins per match | 0.86 | 0.68 |

Paired score delta (V0.13 minus V0.10):

- mean: **-4.88**
- sample SD: 180.44
- 95% CI: **-75.61 to +65.85**

The win count is a small-sample fluctuation; the confidence interval crosses
zero and the point-in-time deal-in rate is worse for the candidate. This is not
promotion evidence.

## Decision

Keep V0.13 as an explicit experiment for future larger samples or new evidence.
Do not change `CurrentAgent`, do not claim KONG EV is solved, and do not enable
automatic execution. Any future KONG promotion must first resolve or safely
model tail-draw value, special-state interactions, and the remaining rob-kong /
gang-hu settlement dependencies, then beat V0.10 on fresh fixed walls with seat
swaps.

## Verification

The candidate and its boundary tests pass in the local 317-test suite (315
existing tests plus two V0.13 decision tests).
