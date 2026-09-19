# TwoPly V0.8 validation — 2026-09-19

## Status

**NOT PROMOTED.** CurrentAgent remains TenpaiRiskTieBreakAgent V0.6.

V0.8 preserved V0.3's exact current offense frontier and inserted a
deterministic ordinary two-ply lookahead before V0.6 relative tenpai risk.

## Pilot

Evidence:
- original run 35423589334
- timeout retry run 35425361054

100 seed pairs / 200 complete eight-hand matches:
- V0.8 wins 110
- V0.6 wins 88
- ties 2
- mean paired final-score delta +26.67
- pooled SD 120.4921
- approximate 95% CI +3.0535 to +50.2865
- deal-ins 115 vs 126

This first-stage pilot was positive.

## Independent confirmation

Run 35425899840, fresh disjoint seeds:
- 70000–70024
- 72000–72024
- 74000–74024
- 76000–76024

100 seed pairs / 200 complete eight-hand matches:
- V0.8 wins 100
- V0.6 wins 99
- ties 1
- mean paired final-score delta **-5.25**
- pooled SD **164.9545**
- approximate 95% CI **-37.5811 to +27.0811**
- deal-ins **117 vs 104**

The first-stage score advantage did not reproduce.

## Overall

Across 200 seed pairs / 400 complete eight-hand matches:
- V0.8 wins **210**
- V0.6 wins **187**
- ties **3**
- mean paired final-score delta **+10.71**
- pooled SD **144.9666**
- SE **10.2507**
- approximate 95% CI **-9.3813 to +30.8013**
- deal-ins **232 vs 230**

## Decision

Do not promote V0.8 and do not spend a third confirmation batch merely to chase
a positive interval. CurrentAgent stays V0.6.

The next step is decision-level diagnostics, not another blind heuristic:
measure how often V0.8 changes V0.6, at what shanten stages, whether the
two-ply layer resolves ties or falls through to risk, and which decision classes
are associated with later score swings. Use that evidence to define the next
experiment.
