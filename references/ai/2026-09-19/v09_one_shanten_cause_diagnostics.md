# V0.9 one-shanten cause diagnostics — 2026-09-19

## Purpose

V0.9 used deterministic two-ply ordinary offense only at shanten 1, but its
positive first pilot failed independent confirmation. This diagnostic asks what
metric actually causes those one-shanten overrides on V0.6 trajectories.

Run: 35428855044

20 complete matches, 4 independent five-match blocks.

## Aggregate

- discard decisions: **4,553**
- shanten-1 exact V0.3 offense ties: **510**
- two-ply changed the V0.6 discard: **203** (39.80% of those exact ties)

Cause classification across all 510 shanten-1 exact ties:
- weighted post-shanten uniquely best: **0**
- terminal-win copies uniquely best: **0**
- weighted post-live copies uniquely best: **384**
- weighted post-effective-type count uniquely best: **13**
- still tied after all two-ply metrics: **113**

Among the 203 actual V0.6 -> two-ply discard changes:
- caused by post-live copies: **197**
- caused by post-effective types: **6**
- caused by post-shanten: **0**
- caused by terminal wins: **0**

Therefore every behavioral override came from downstream local ukeire metrics;
none came from a better weighted next-state shanten or more immediate winning
draws.

## Interpretation

The one-shanten gate did not isolate a genuinely stronger "reach tenpai
sooner" signal. Inside the exact V0.3 offense frontier, the primary two-ply
metrics were identical in this sample, leaving only small downstream
live-copy/type differences to change the discard.

That matches the A/B instability of V0.9 and argues against adding an arbitrary
epsilon threshold to the same feature stack.

## Decision

Retire the V0.8/V0.9 two-ply line as a promotion path for now. CurrentAgent
remains V0.6.

The next evidence target is opponent-state calibration. V0.6 estimates
candidate-specific wait risk **conditioned on the opponent already being in
ordinary tenpai**, but has no public estimate of whether the opponent is
actually in tenpai at the current point in the hand.

Next experiment:
1. passively label opponent ordinary-tenpai state offline from simulator truth;
2. predict only from public information (wall progress, public discard/action
   depth, opponent open-meld count and other non-hidden state);
3. measure AUC / calibration on held-out seeds;
4. only if the public tenpai-probability model is useful, combine it with the
   existing conditional wait-risk score for a new defense experiment.
