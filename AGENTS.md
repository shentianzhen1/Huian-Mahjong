# Agent Instructions

## Core rule
Do not invent Mahjong rules. If a rule is uncertain, mark it as UNKNOWN/TODO/configurable instead of hard-coding a guess.

## Evidence priority
1. Real Huian in-game screenshots / settlement screens
2. Huian player feedback from actual gameplay
3. In-game rule pages
4. External Quanzhou/Huian web sources

Never let lower-priority evidence overwrite higher-priority evidence.

## Architecture
Keep these layers independent:
- Rules
- Environment
- Simulator
- AI
- Vision
- Executor

The Rules layer decides legality/scoring.
The Environment owns GameState and deterministic state transitions.
The Simulator repeatedly drives complete games.
The AI chooses actions.
The Vision layer converts screen frames into GameState observations.
The Executor performs optional UI actions only after validation.

## Development priorities
1. Close remaining UNKNOWN evidence: gold reveal ownership, qiangjin window, youjin state machine, added/robbed kong, dealer-base fields
2. Keep simulation-only unit rewards separate from evidence-backed settlement
3. Analyze UNKNOWN stops from batch evaluation and improve Baseline discard/chi heuristics on completed hands only
4. Calibrate offline Vision ROIs and build an accuracy baseline
5. Monte Carlo / EV AI after ordinary-hand evaluation is stable
6. Opponent + danger model
7. Vision integration
8. Executor last; never click the live applet until validation is sufficient

Do not spend major effort on UI before evaluation reports are reproducible.
Do not rewrite Rules, Environment, or Simulator control flow for hygiene-only work.

## Testing requirements
After any change to rules/environment/simulator:
- run automated tests
- keep fixed-seed behavior reproducible
- reject impossible 5th copies of a tile
- reject negative wall counts
- verify only legal actions execute
- detect dead loops
- preserve zero-sum net settlement in 2-player hands where applicable
- add regression tests for real settlement screenshots whenever a rule becomes confirmed
- do not count UNKNOWN stops as draws or wins

## Naming
New code should prefer `Huian_*` or neutral `Mahjong_*` naming.
Do not waste time renaming stable legacy internals unless needed for integration.

## Performance
Final Windows machine may be a ThinkPad X13-class laptop.
Runtime should remain lightweight.
Prefer ONNX Runtime for deployed vision inference.
Heavy YOLO training or large-scale RL can be done on a stronger GPU machine/cloud later.

## Safety / fail-safe for future automation
Vision uncertainty or inconsistent state must stop execution.
Never click when confidence/state validation is insufficient.
Prevent duplicate actions and confirm post-action state before continuing.
