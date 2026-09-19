# TenpaiRisk V0.6 promotion evidence — 2026-09-19

## Decision

`TenpaiRiskTieBreakAgent` is promoted as the project's current AI policy
(`CurrentAgent`). `ShantenAgent` remains available explicitly as the V0.3
comparison baseline and fallback.

The promotion gate is final 8-hand score, not raw deal-in count.

## Policy boundary

V0.6 preserves the V0.3 offensive ordering exactly until the final canonical
tile-order tie break. The tenpai-conditioned wait-risk score may be used only
when candidate discards have identical:

1. ordinary shanten;
2. total live effective copies;
3. effective-tile type count.

The risk score is a relative ranking signal, **not** an absolute deal-in
probability. If a tied candidate includes Jin, or the risk model cannot produce
a usable estimate, V0.6 falls back to the V0.3 choice.

## Evaluation correction before promotion

An earlier paired evaluator seeded stochastic agents by seat. That is acceptable
for deterministic policies but adds avoidable noise to V0.6 because its
tenpai-template sampler is stochastic.

The evaluator was corrected so RNG seed identity follows the agent across seat
swaps. Regression tests now enforce that contract. Results produced before this
fix are diagnostic only and are excluded from the promotion calculation.

## Promotion runs

All promotion runs use:

- fixed match seeds;
- original + swapped seats for every seed;
- eight hands per match;
- real ordinary scoring and dealer-base progression;
- identity-stable agent RNG;
- V0.6 with 32 tenpai templates;
- complete pairs only; no imputation for UNKNOWN.

GitHub Actions runs:

- run 35420511674: seeds 7000–7049 and 9000–9049 (100 pairs / 200 matches);
- run 35420622352: seeds 11000–11024, 13000–13024, 15000–15024,
  17000–17024 (100 pairs / 200 matches);
- run 35420968672: seeds 19000–19024, 21000–21024, 23000–23024,
  25000–25024 (100 pairs / 200 matches).

The 10 seed blocks are disjoint.

## Combined result

Across **300 seed pairs / 600 complete eight-hand matches**:

- V0.6 match wins: **322**
- V0.3 match wins: **275**
- ties: **3**
- average paired final-score delta, V0.6 − V0.3: **+18.9633**
- paired score-delta sample SD: **146.4750**
- standard error: **8.4567**
- approximate 95% CI: **+2.3881 to +35.5385**
- V0.6 deal-ins: **319**
- V0.3 deal-ins: **350**

Because the primary score-delta interval is above zero on these disjoint held-out
blocks, V0.6 passes the current promotion gate. Deal-ins are recorded as a
secondary diagnostic only.

## Next strategy baseline

Future V0.7+ strategy experiments must compare against `CurrentAgent` /
TenpaiRisk V0.6, not against V0.3 alone. V0.3 remains useful as an explicit
ablation baseline to verify that new policies do not hide regressions behind the
risk tie-break.
