# Baseline Test Results at Handoff

> **Historical handoff record.** Counts and limitations below describe earlier snapshots and must not be used as the current test-status source. Use `PROJECT_STATUS.md` and the latest GitHub Actions runs for current regression status.

## PASS / 16-tile regression — 2026-09-14

- Project tests: 53 passed; legacy Core: 9 passed; legacy Environment: 9 passed.
- Total: 71 tests passed with Python `-B -m unittest discover -s tests -q`.
- Covers both-seat PASS, river retention, head draw, head/kong-tail 17→16
  termination (including a flower), [0, 0] rewards, 144-tile conservation,
  illegal actions, boundary imports, seeded multi-turn replay and rollback.
- Screenshot A/B settlements still pass unchanged; no four-player scoring imported.

Environment used for this verification: Python 3.13.5.

## Core V0.1.1
9 tests passed:
- actions
- default 8-hand match setting
- double-gold cannot Pinghu
- gold fills sequence for Zimo
- normal 17-tile win
- legacy real two-player settlement test
- single-gold cannot Pinghu
- Ting example
- 144-tile wall

Important: the legacy settlement test reflects an older scoring assumption and must be replaced/updated when Huian settlement is integrated.

## Environment V0.1
9 tests passed:
- checkpoint/rollback
- clone independence
- discard transition
- draw reduces wall
- end-hand rewards
- event log
- paired wall seeds
- reset to 144-tile wall
- zero-sum stats

These passing tests are a baseline, not proof that Huian rules are complete.

## M2 verification — 2026-09-13

Interpreter: bundled Python 3.12.14, using `-B` to avoid bytecode writes.

- Project-root tests: 42 passed (22 M1 rules/adapter tests + 20 M2 environment tests).
- Legacy Core: 9 passed.
- Legacy Environment: 9 passed.
- Total: 60 passed; all unittest commands exited 0.
- `python -B -m huian.environment.demo` exited 0: Chi transferred the river tile,
  discard retained all 144 physical tiles, and rollback restored the original hash.

Coverage includes atomic post-validation failure, rejected state imports, fifth
copies, claim source/index validation, post-claim hand sizes, resolved-kong tail
draws, flower/16-tile boundary blocking, strict legality enforcement, mutation
isolation, seed/replay reproducibility, checkpoint restoration and loop guards.
New kong declarations are tested with an explicit experimental no-rob setting;
default unknown scope is separately tested to block. This is not a full-game test.
