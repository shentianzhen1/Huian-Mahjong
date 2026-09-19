# OneShanten TwoPly V0.9 validation — 2026-09-19

## Status

**NOT PROMOTED.** CurrentAgent remains TenpaiRiskTieBreakAgent V0.6.

V0.9 was derived from V0.8 shadow diagnostics. It kept V0.6 unchanged at
ordinary shanten 0 and shanten >=2 and used deterministic two-ply ordinary
offense only inside exact V0.3 offense ties at shanten 1.

## First pilot

Run 35428477670, fresh 100 seed pairs / 200 complete eight-hand matches:
- V0.9 wins 115
- V0.6 wins 84
- ties 1
- mean paired score delta +24.62
- pooled SD 109.0051
- approximate 95% CI +3.2550 to +45.9850
- deal-ins 111 vs 125

The pilot passed the first-stage interval gate.

## Independent confirmation

Run 35428647950, fresh disjoint seed ranges:
- 96000–96024
- 98000–98024
- 100000–100024
- 102000–102024

100 seed pairs / 200 complete eight-hand matches:
- V0.9 wins **103**
- V0.6 wins **95**
- ties **2**
- mean paired score delta **-4.01**
- pooled SD **152.1881**
- SE **15.2188**
- approximate 95% CI **-33.8389 to +25.8189**
- deal-ins **92 vs 104**

The first-stage score advantage did not reproduce.

## Overall

Across 200 seed pairs / 400 complete eight-hand matches:
- V0.9 wins **218**
- V0.6 wins **179**
- ties **3**
- mean paired score delta **+10.305**
- pooled SD **132.8140**
- SE **9.3914**
- approximate 95% CI **-8.1021 to +28.7121**
- deal-ins **203 vs 229**

## Decision

Do not promote V0.9 and do not spend a third batch merely to chase a positive
interval. CurrentAgent stays V0.6.

The next diagnostic must separate *why* one-shanten two-ply changes a decision:
- a genuine change in the weighted probability/count of reaching tenpai after
  the next draw + best discard;
- a change only in terminal-win copies;
- or merely a tiny downstream live-copy/effective-type difference after the
  same weighted post-shanten.

That classification should define the next policy rather than tuning an
arbitrary epsilon from A/B outcomes.
