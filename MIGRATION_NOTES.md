# Migration Notes

> **Historical migration log.** This file records the 2026-09-13 migration state and is not a current project-status source. For current capability and open work, use `PROJECT_STATUS.md`, `RULE_STATUS.md`, and GitHub Issues / `TODO.md`. Statements below such as “M3 has not started” are preserved only as historical context.

The legacy code was created while the project was still named Quanzhou Mahjong. The actual target is now 开心惠安二人麻将.

Do not perform a risky full rewrite. Recommended migration:
1. keep legacy code unchanged initially
2. add Huian-specific rule adapter and tests
3. migrate behavior module-by-module
4. only rename stable internals when it improves clarity

The most important correction is scoring: legacy Core contains an older two-player settlement assumption. Current real Huian screenshots support a different formula hypothesis documented in RULE_STATUS.md.

Vision V0.4 is only an early capture/segmentation prototype. It is not a trained Huian tile-recognition model and should not dictate final architecture.

## M1 implemented (2026-09-13)

Added `huian/rules/` and `tests/test_huian_rules.py` without changing the legacy
baselines. See `huian/README.md` for interfaces, explicit settlement opt-in,
UNKNOWN behavior and the limited post-Chi/Peng adapter scope. Validation:
22 Huian tests, 9 Core tests and 9 Environment tests passed on Python 3.12.14.

M2 Environment transitions and M3 Simulator remain pending. M1 does not make the
legacy Environment a complete Huian game and does not enable automatic play.

## M2 supported transitions implemented (2026-09-13)

The earlier M1 pending note is superseded for the supported M2 subset:
`huian/environment/` now owns HuianGameState, atomic transitions, full physical
tile accounting, pending discard references, loop guards and checkpoint history.
Rules-side phase legality lives in `huian/rules/phases.py`, accessed through the
existing HuianRulesAdapter. The legacy code remains unchanged.

Chi/Peng transfer the claimed river tile; kong replacement draws use the tail.
New kong declarations require an explicit experimental no-rob configuration until
scope is confirmed. Resolved post-kong scenarios can use the default rules.
Unknown initialization, PASS, flower replacement, wall boundary and win handling
remain blocked. See `huian/environment/README.md` for exact scope and usage.

M3 Simulator has not started; no complete-game or AI performance claim is made.
