# TenpaiLoss V0.7a pilot — 2026-09-19

## Status

**NOT PROMOTED.** CurrentAgent remains TenpaiRiskTieBreakAgent V0.6.

V0.7a preserved the exact V0.6 offense frontier (shanten, live effective
copies, effective-tile types), but inside that frontier it ranked candidates by
a tenpai-conditioned ordinary-Ron loss index:

`loss_index = average confirmed Pinghu loss across accepted tenpai templates,
with non-matching templates counted as zero`.

The index is conditional on the opponent already being in tenpai; it is not an
absolute EV.

## Implementation safety fix before the valid pilot

The first pilot run (Actions run 35421754523) exposed synthetic template
decompositions that FanAggregator correctly refused to score. Rules/FanAggregator
were not relaxed. The opponent model was changed so any synthetic template that
cannot be scored with the existing auditable fan path is marked incomplete, and
V0.7 falls back to V0.6.

After this change Core regression reached 278 tests and passed on Python
3.10/3.11/3.12 plus Legacy.

## Valid pilot

Actions run: 35421827363

Four disjoint 25-pair blocks, fixed wall + seat swap + identity-stable RNG,
32 templates per risk/loss estimate:

- seeds 30000–30024:
  - V0.7a 21 wins / V0.6 29 wins
  - paired score delta -8.96
  - deal-ins 35 vs 29
- seeds 32000–32024:
  - V0.7a 23 wins / V0.6 27 wins
  - paired score delta +16.40
  - deal-ins 30 vs 26
- seeds 34000–34024:
  - V0.7a 26 wins / V0.6 24 wins
  - paired score delta +22.48
  - deal-ins 29 vs 23
- seeds 36000–36024:
  - V0.7a 25 wins / V0.6 25 wins
  - paired score delta -16.92
  - deal-ins 25 vs 33

Combined 100 seed pairs / 200 complete eight-hand matches:

- V0.7a wins: **95**
- V0.6 wins: **105**
- ties: **0**
- mean paired final-score delta: **+3.25**
- pooled paired score-delta SD: **138.8912**
- approximate 95% CI: **-23.9727 to +30.4727**
- deal-ins: **119 vs 111**

## Conclusion

The pilot provides no evidence that loss-index-first ranking improves final
score over V0.6. It also produced more deal-ins overall.

Do not increase sample size for this exact policy. The next conservative
experiment is V0.7b: keep V0.6 relative risk as a hard earlier tie-break and use
confirmed loss severity only when the V0.6 risk score itself is tied.
