# Development TODO

## P0 - next milestone
### Latest evidence priorities: five in-game pages received (2026-09-13)
- See `references/ingame_rules/2026-09-13/README.md` for originals and transcription.
- Received actual 惠安 two-player creation options: `references/room_settings/2026-09-13/README.md`. The screenshot has 单金不平胡 unchecked (label maps to `single_gold_can_pinghu=True`); verify the final created-room choice for each recorded game. Keep project default False per earlier player preference.
- Record opening through first discard to resolve two-player flower scheduling and exact gold-opening/index/accounting behavior.
- Done (2026-09-14 player confirmation): PASS advances to next player's draw; 16 tiles ends the hand with [0, 0]. Target room: 2 players, 8 hands, 单金不平胡 checked, no trusteeship.
- Obtain a third real settlement and Double/Triple results: the in-game page says 4/8/16, with an outer ×3 that must not be silently applied to two-player net scoring.
- Flower-set values and honor Peng now have in-game textual evidence, but stacking/room applicability and added-kong fan remain pending. No runtime defaults changed from these pages alone.

### M2 implementation status (2026-09-14)
- Done: Huian Environment atomic transitions, 144-tile accounting, pending-discard transfer, post-Chi/Peng discard, resolved-kong tail draw, clone/rollback and loop guards.
- Experimental only: Ming/An-Gang declaration assuming no rob-kong, explicitly recorded in configuration/events.
- Done: default Environment PASS, immediate 17→16 draw termination (head/tail), 16-tile import termination, zero rewards, deterministic replay/rollback regression tests; confirmed_flow names reuse the default implementation.
- Pending evidence/integration: opening procedure, flower replacement, special wins, automatic winning settlement and complete hand loop.
- See `huian/environment/README.md`. M3 Simulator remains pending.

### 1. Rules integration
- Create `HuianRules` / `HuianRulesAdapter`.
- Port only confirmed/high-confidence rules.
- Put uncertain rules behind explicit config/UNKNOWN branches.
- Replace outdated legacy settlement formula with the current Huian hypothesis only behind tests/config until confirmed.

### 2. Simulator V0.1
Required:
- deterministic 144-tile wall by seed
- deal / flower replacement / gold-opening hooks
- complete turn loop
- agent interface: `choose_action(state, legal_actions)`
- RandomAgent
- full event log / replay
- batch simulation
- terminal detection
- zero-sum rewards
- fixed-wall paired evaluation with swapped seats/dealer

Invariant checks:
- no fifth copy of any normal tile
- wall count never negative
- only legal actions execute
- no infinite loops
- deterministic replay from same seed
- settlement sums to zero in 2-player net score

## P1
### Rule evidence follow-up (web review 2026-09-13)
- Verify the exact mini-program identity and current 惠安 two-player room rules; see `references/HUIAN_WEB_RULES_2026-09-13.md`.
- Capture multiplier settings and rules pages for rob-kong, Sanjindao, Youjin chronology/permissions and the 16-tile boundary.
- Confirm exposed-triplet/honor-Peng fan, added-kong incremental versus total fan, and whether eight flowers confer a special win.
- Keep all external variant claims out of executable defaults until target-room evidence supports them.

### Baseline AI
- shanten / distance-to-win
- effective tiles
- remaining tile counts
- gold value
- meld quality
- special-hand / Youjin potential
- simple danger penalty

### Evaluation
- fixed-wall NewAI vs OldAI
- win rate
- average net score
- deal-in rate
- Youjin/Double/Triple rates

## P2
### Monte Carlo / EV AI
- clone current state
- sample hidden opponent hand/wall consistent with public information
- simulate candidate actions
- return Win Probability, Deal-in Probability, Expected Score separately

### Opponent model / danger
- discard sequence
- melds
- remaining tiles
- multiple opponent-hand hypotheses

## P3
### Vision
When Android device is available:
- USB debugging
- scrcpy stable window
- capture region
- dataset collection
- YOLO detection/classification
- ONNX export/inference
- multi-frame dedupe
- rules/state validator

### Executor
Only after stable vision:
- highlight-only mode
- confirm-to-click mode
- ADB tap
- state confirmation after each action
- fail-safe / emergency stop
