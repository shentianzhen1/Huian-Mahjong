# Public opponent-tenpai probability calibration — pilot — 2026-09-19

## Purpose

V0.6's wait-risk score is conditional on the opponent already being in
ordinary tenpai. This experiment asks whether public state can estimate
P(opponent ordinary-tenpai) without exposing hidden opponent tiles to the
production agent.

A new offline-only Simulator decision observer receives a deep copy of truth
state for labels. Predictor features are copied only from PlayerObservation.

Run: 35431143375

## Data

- train seeds 130000–130099: 100/100 complete hands, 3,019 discard-decision samples
- held-out test seeds 140000–140099: 100/100 complete hands, 2,991 samples
- train tenpai prevalence: 11.9907%
- test tenpai prevalence: 9.6289%

Initial transparent model:
- wall bucket width 16 tiles
- opponent open-meld count when a cell has >=30 samples
- empirical-Bayes smoothing strength 8

## Held-out result

- AUC: **0.79679**
- Brier: **0.0795969**
- constant training-base-rate Brier: **0.0875751**
- mean prediction on true-tenpai states: **0.28054**
- mean prediction on non-tenpai states: **0.10652**

This is materially stronger than the earlier uniform-unseen-hand absolute
deal-in model and contains real public-state signal.

## Calibration caveat

The model is overconfident on this held-out block:
- prediction bin mean ~0.1266 -> observed 0.1036
- prediction bin mean ~0.3476 -> observed 0.2681
- prediction bin mean ~0.5726 -> observed 0.3609

Training prevalence also exceeded test prevalence (11.99% vs 9.63%), so this
pilot is not ready to be called a calibrated probability for production.

## Wall-stage structure in training

With bucket = floor((wall_remaining - 16) / 16):
- bucket 5 (roughly wall 96–111): smoothed P ~0.0052
- bucket 4 (80–95): ~0.1266
- bucket 3 (64–79): ~0.3486
- bucket 2 (48–63): ~0.5726

The monotonic phase signal is strong.

## Important coverage gap

All sufficiently populated meld cells had opponent_open_melds = 0. That is not
a model accident: CurrentAgent V0.6 still PASSes optional Chi/Peng/Gang claims.
Therefore V0.6 self-play does not provide coverage for realistic open-meld
opponents. Any later real-game use must either add meld-capable policy/data or
recalibrate from real replay observations.

## Next gate

Run a three-way split:
- training set
- validation set used only to choose wall-bucket width / smoothing
- untouched final test set

Only after the final test confirms useful AUC and Brier improvement should the
public-tenpai probability be exposed as a reusable model feature. It should
not yet change CurrentAgent decisions.
