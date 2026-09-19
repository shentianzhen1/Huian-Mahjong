# OneShanten TwoPly V0.9 pilot — 2026-09-19

## Status

**PROMISING, NOT YET PROMOTED.** CurrentAgent remains TenpaiRiskTieBreakAgent V0.6.

V0.9 was derived from V0.8 shadow diagnostics. It preserves V0.6 at ordinary
shanten 0 and shanten >=2, and allows deterministic two-ply ordinary offense
only inside exact V0.3 offense ties at shanten 1.

## Pilot

Actions run: 35428477670

Fresh disjoint seed ranges:
- 88000–88024
- 90000–90024
- 92000–92024
- 94000–94024

Total: 100 seed pairs / 200 complete eight-hand matches.

Results:
- V0.9 wins: **115**
- V0.6 wins: **84**
- ties: **1**
- mean paired final-score delta: **+24.62**
- pooled paired SD: **109.0051**
- SE: **10.9005**
- approximate 95% CI: **+3.2550 to +45.9850**
- V0.9 deal-ins: **111**
- V0.6 deal-ins: **125**

Compute cost was also materially lower than unrestricted V0.8. Five-pair jobs
typically completed in roughly 43–97 seconds rather than the multi-minute
V0.8 blocks.

## Decision

The pilot clears the first-stage score interval gate but is not sufficient for
promotion. Run a fresh independent 100-pair confirmation. Only if the effect
reproduces should validation be extended toward the 300-pair promotion scale.
