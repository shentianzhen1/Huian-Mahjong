# TwoPly V0.8 pilot — 2026-09-19

## Status

**PROMISING, NOT YET PROMOTED.** CurrentAgent remains TenpaiRiskTieBreakAgent V0.6.

V0.8 preserves the exact V0.3 offense frontier, then uses deterministic
next-draw / next-best-discard ordinary offense quality before falling back to
the promoted V0.6 relative tenpai risk when the two-ply metrics are still tied.

No opponent concealed tiles, future wall order, guessed special multipliers, or
hardware-specific constraints are used.

## Valid pilot

The original 25-pair jobs used a 20-minute timeout. Block 64000–64024 completed;
62000/66000/68000 were cancelled by the job timeout, not by code failure.

- original run: 35423589334
- retry run (remaining 75 pairs split into 15 five-pair jobs): 35425361054

All retry jobs completed successfully.

Combined disjoint seed ranges:
- 62000–62024
- 64000–64024
- 66000–66024
- 68000–68024

Total: **100 seed pairs / 200 complete eight-hand matches**.

## Combined result

- V0.8 wins: **110**
- V0.6 wins: **88**
- ties: **2**
- mean paired final-score delta: **+26.67**
- pooled paired score-delta SD: **120.4921**
- SE: **12.0492**
- approximate 95% CI: **+3.0535 to +50.2865**
- V0.8 deal-ins: **115**
- V0.6 deal-ins: **126**

The first pilot therefore clears the current first-stage score interval gate.

## Compute note

The deterministic two-ply analysis is substantially more expensive than V0.6.
That cost is recorded as an engineering metric but is not a promotion gate by
itself; deployment optimization is a separate stage.

## Next gate

Run an independent fresh 100-pair confirmation. Do not promote from this pilot
alone. If the independent block reproduces positive score improvement, extend
validation to a total sample comparable to the V0.6 promotion standard.
