# TenpaiRiskLoss V0.7b validation — 2026-09-19

## Status

**NOT PROMOTED.** CurrentAgent remains TenpaiRiskTieBreakAgent V0.6.

V0.7b was a stricter follow-up to failed V0.7a. It preserved the promoted V0.6
ordering first:

1. ordinary shanten;
2. total live effective copies;
3. effective-tile type count;
4. V0.6 tenpai-conditioned relative risk.

Only when the V0.6 relative risk score was also tied did V0.7b use confirmed
ordinary-Ron loss severity as a final tie-break. The loss index remained
tenpai-conditioned and was never treated as absolute EV.

## Regression gate

Before evaluation:
- risk-first ordering had explicit regression tests;
- loss severity was allowed only after equal risk;
- incomplete/unscorable synthetic templates fell back to V0.6;
- Core regression reached **280 tests** and passed on Python 3.10/3.11/3.12;
- Legacy regression also passed.

## Pilot: 100 seed pairs / 200 matches

Actions run: 35422591322

Blocks:
- 38000–38024: 25:25, paired delta +2.56, deal-ins 38 vs 37
- 40000–40024: 29:21, paired delta +31.16, deal-ins 33 vs 14
- 42000–42024: 27:23, paired delta +44.36, deal-ins 21 vs 37
- 44000–44024: 27:23, paired delta +30.96, deal-ins 32 vs 39

Combined pilot:
- V0.7b wins 108
- V0.6 wins 92
- ties 0
- mean paired final-score delta **+27.26**
- pooled SD **140.2925**
- approximate 95% CI **-0.2373 to +54.7573**
- deal-ins **124 vs 127**

The pilot was promising but did not cross the promotion interval gate.

## Independent confirmation: another 100 seed pairs / 200 matches

Actions run: 35422821119

Blocks:
- 46000–46024: 25:24, 1 tie, paired delta -6.44, deal-ins 23 vs 29
- 48000–48024: 22:26, 2 ties, paired delta +11.52, deal-ins 27 vs 18
- 50000–50024: 28:21, 1 tie, paired delta +18.24, deal-ins 51 vs 32
- 52000–52024: 23:25, 2 ties, paired delta -22.64, deal-ins 33 vs 28

Combined confirmation:
- V0.7b wins 98
- V0.6 wins 96
- ties 6
- mean paired final-score delta **+0.17**
- pooled SD **122.4327**
- approximate 95% CI **-23.8268 to +24.1668**
- deal-ins **134 vs 107**

The initial advantage did not reproduce.

## Overall: 200 seed pairs / 400 matches

Across all eight disjoint 25-pair blocks:
- V0.7b wins **206**
- V0.6 wins **188**
- ties **6**
- mean paired final-score delta **+13.715**
- pooled paired SD **132.0347**
- SE **9.3363**
- approximate 95% CI **-4.5841 to +32.0141**
- deal-ins **258 vs 234**

## Decision

Do not promote V0.7b and do not spend another 100 pairs on this exact policy.
The independent confirmation collapsed from +27.26 to +0.17 and increased
deal-ins materially.

The next risk-model experiment should target sampling quality/stability itself,
rather than adding more tie-break layers on top of a coarse 32-template score.
A simple next test is to compare the same V0.6 policy with a larger template
sample against the promoted 32-template CurrentAgent, using fresh seeds.
