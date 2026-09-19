# Public opponent-tenpai probability — final calibration — 2026-09-19

## Status

**Validated research feature for closed-hand CurrentAgent self-play.**
It is not yet a real-player absolute tenpai probability because the current
self-play policy does not take optional Chi/Peng/Gang and therefore provides no
open-meld coverage.

Run: 35431313344

## Three-way split

- training: 150 complete hands / 4,534 discard-decision samples
- validation: 100 complete hands / 2,964 samples
- untouched final test: 150 complete hands / 4,509 samples

Candidate grid:
- wall bucket widths: 8, 12, 16, 24
- empirical-Bayes prior strength: 8, 24, 64

Selection criterion: lowest validation Brier only; final test was untouched.

Chosen model:
- wall bucket width **8**
- prior strength **8**
- min populated meld-cell count 30

Validation:
- Brier **0.0777863**
- constant train-rate Brier **0.0861376**
- AUC **0.785872**

## Untouched final test

- train prevalence: **8.8222%**
- final-test prevalence: **7.9840%**
- mean prediction: **8.2847%**
- mean prediction on true-tenpai states: **16.6376%**
- mean prediction on non-tenpai states: **7.5600%**
- Brier: **0.0668696**
- constant train-rate Brier: **0.0735361**
- AUC: **0.799182**

Calibration bins on the final test:
- mean prediction 1.1427% -> observed 0.8097% (n=1,976)
- mean prediction 6.9072% -> observed 6.1184% (n=997)
- mean prediction 13.3702% -> observed 14.0420% (n=762)
- mean prediction 23.2859% -> observed 22.7390% (n=774)

The three populated probability bands above ~5% are well aligned on untouched
data, and ranking remains strong.

## Interpretation

Public hand phase/progress contains a reproducible opponent-tenpai signal.
This closes the specific research question left open by V0.6: P(opponent
tenpai | public state) is estimable in the simulator distribution.

However this probability is currently calibrated only on closed-hand
V0.6-vs-V0.6 trajectories. All populated open-meld cells have
opponent_open_melds = 0 because CurrentAgent passes optional claims.

## Decision

Keep CurrentAgent at V0.6. Preserve the public-tenpai estimator/calibration
infrastructure as a validated feature, but do not yet convert it into a
real-player absolute warning or a defense override.

The next AI priority is meld-action coverage:
1. add an auditable Chi/Peng claim evaluator;
2. compare PASS state with claim -> best mandatory discard state using the same
   shanten/live-effective-copy/effective-type metrics;
3. leave Ming-Gang/An-Gang/Added-Gang to a separate expected tail-draw + fan
   evaluation;
4. benchmark claim-capable policy directly against CurrentAgent V0.6.
