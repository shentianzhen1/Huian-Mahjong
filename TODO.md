# Development TODO

## P0 - next milestone
### Latest evidence priorities: five in-game pages received (2026-09-13)
- See `references/ingame_rules/2026-09-13/README.md` for originals and transcription.
- Received actual 惠安 two-player creation options: `references/room_settings/2026-09-13/README.md`. The screenshot has 单金不平胡 unchecked (label maps to `single_gold_can_pinghu=True`); verify the final created-room choice for each recorded game. Keep project default False per earlier player preference.
- Record opening through first discard to resolve two-player flower scheduling and exact gold-opening/index/accounting behavior.
- Done (2026-09-14 player confirmation): PASS advances to next player's draw; 16 tiles ends the hand with [0, 0]. Target room: 2 players, 8 hands, 单金不平胡 checked, no trusteeship.
- Done in multiplier/formula scope (2026-09-15 real-game report `7bc12fa…mp4`): target-room Youjin/Double/Triple are 4/8/16; recorded Triple-You is `(dealer base 35 + gold 1 + two flowers 2) ×16 = 608`. Flowers are inside winner fan before multiplication, superseding the earlier same-day additive-after-multiplication statement. Dealer-winner ×2 remains player-confirmed. Import the original video to add checksum/timecodes and still confirm payer, terminal flow and next dealer.
- Evidence follow-up: locate/import `7bc12fa…mp4`; extract the +608 settlement frame and record full filename, SHA256, duration and timestamp. Current workspace/D-drive/common-user-directory search found no matching binary.
- Flower-set values and honor Peng now have in-game textual evidence, but stacking/room applicability and added-kong fan remain pending. No runtime defaults changed from these pages alone.
- Done (2026-09-14 player confirmation): all completed Ming/An/Added Kongs draw from `wall_tail` through the normal draw pipeline, and a Hu by the declarer on that draw is Gang-Hu. Gang-Hu scoring and rob-kong remain pending.
- Done in rule scope (2026-09-15 player confirmation): `can_sanjindao = hand_gold_count >= 3`; declaring is optional and continued play may pursue 三游/三金游. 三金游 and 三游 are the same `TRIPLE_YOU` ×16 state; 三金倒 is a separate ×3 outcome. Their shared executable steps, non-flower base and full settlement remain pending.
- Done/reconfirmed (2026-09-14 player confirmation): after Chi, as after Peng, the acting player immediately discards without a normal draw; current Environment already implements this transition.

### M2 implementation status (2026-09-15)
- Done: Huian Environment atomic transitions, 144-tile accounting, pending-discard transfer, post-Chi/Peng discard, resolved Ming/An-Kong tail draw, clone/rollback and loop guards. Draw sources now emit `wall_head` / `wall_tail`; kong-tail events record `kong_kind` and `drawn_tile`, while old replay aliases remain readable. Added-Kong execution remains pending.
- Done in Rules: `HuContext` source-aware ordinary Hu, target-room one/two-gold discard restrictions, discarded-gold rejection, all-three-kong Gang-Hu classification, and shape-independent optional `SanjindaoDecision`.
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
