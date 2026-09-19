# TenpaiRisk 64-vs-32 template pilot — 2026-09-19

## Status

**NO CHANGE.** CurrentAgent remains TenpaiRiskTieBreakAgent V0.6 with 32
tenpai templates per exact-offense-tie risk estimate.

This experiment kept the policy identical and changed only
`template_samples` from 32 to 64.

## Pilot

Actions run: 35423104092

Fresh disjoint seed blocks, 25 pairs each:

- 54000–54024: 64-template 28 wins / 32-template 22 wins,
  paired delta +38.84, deal-ins 36 vs 22
- 56000–56024: 20 / 30,
  paired delta -49.88, deal-ins 23 vs 24
- 58000–58024: 27 / 23,
  paired delta +25.68, deal-ins 33 vs 35
- 60000–60024: 26 / 24,
  paired delta +9.80, deal-ins 26 vs 32

Combined 100 seed pairs / 200 matches:

- 64-template wins **101**
- 32-template wins **99**
- ties **0**
- mean paired final-score delta **+6.11**
- pooled SD **148.6166**
- approximate 95% CI **-23.0189 to +35.2389**
- deal-ins **118 vs 113**

## Decision

Do not increase CurrentAgent to 64 templates and do not spend a confirmation
batch on this exact change. Doubling template count roughly increases model work
without a stable score or deal-in benefit.

The next experiment should move away from more Monte Carlo samples and add a
deterministic second-order offense signal inside the existing exact V0.3
offense tie. Relative tenpai risk can remain the final tie-break after that.
