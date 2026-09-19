# V0.9 one-shanten override-cause diagnostics — 2026-09-19

## Purpose

V0.9 reduced unrestricted V0.8 to exact V0.3 offense ties at ordinary
shanten 1, but its independent score confirmation failed. This diagnostic
classified *which two-ply metric actually caused an override* on V0.6 live
trajectories.

Actions run: 35428855044

Fresh blocks:
- 112000–112004
- 114000–114004
- 116000–116004
- 118000–118004

All 20 matches completed.

## Aggregate counts

- discard decisions: **4,553**
- shanten-1 exact V0.3 offense ties: **510**
- two-ply shadow changed V0.6: **203**

Classification of all 510 shanten-1 exact ties:
- resolved by weighted post-shanten: **0**
- resolved by terminal-win copies: **0**
- resolved by weighted downstream live copies: **384**
- resolved by weighted downstream effective-tile types: **13**
- still exactly tied after all two-ply metrics: **113**

Classification of the 203 actual overrides:
- post-shanten advantage: **0**
- terminal-win-copy advantage: **0**
- downstream live-copy advantage: **197**
- downstream effective-type advantage: **6**

Therefore **100% of V0.9 overrides came from downstream live-copy/type
differences**. None represented a direct improvement in weighted probability of
reaching tenpai after the next draw+discard, and none represented more immediate
winning copies.

## Decision

End the two-ply-offense line here. Do not tune an epsilon or add more two-ply
depth merely to rescue V0.9.

The next offense/value experiment should use confirmed scoring information at
actual tenpai, where the comparison has direct game-value meaning:

- remain inside V0.3/V0.6 exact current-offense ties;
- only at ordinary shanten 0;
- enumerate the physically live winning tiles;
- compute confirmed ordinary self-draw and discard-Hu legality/fan/settlement
  using HuianRules + FanAggregator + observed settlement;
- prefer a candidate only on an auditable value criterion; unresolved fan or
  special-result inputs must fall back to CurrentAgent V0.6.

This moves from speculative deeper ukeire to confirmed terminal hand value.
