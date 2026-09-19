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
1. Close remaining special-result evidence/settlement gaps: Qiangjin exact eligibility+settlement, Sanjindao real settlement, Youjin/Double/Triple executable state machine, Rob-Kong/Gang-Hu settlement, Eight-Flower-You real multiplier/priority.
2. Preserve the now-confirmed ordinary settlement/dealer-base/full-match regression chain; do not reopen solved rules unless higher-priority evidence conflicts.
3. Treat `CurrentAgent` / TenpaiRiskTieBreakAgent V0.6 as the current AI frontier. Keep ShantenAgent V0.3 as an explicit comparison/ablation baseline. Next strategy work is EV + public-information danger/opponent modeling + 8-hand score/dealer context; new AI must beat CurrentAgent V0.6 in fixed-wall paired evaluation.
4. Resolve opening-gold physical accounting as a lower-frequency Rules/Environment evidence task without inventing tile ownership.
5. Calibrate offline Vision ROIs, build a labeled real-tile dataset, and establish a measured accuracy/stability baseline.
6. Integrate Vision with Rules validation only after the offline accuracy gate is defined.
7. Executor last; never click the live applet until Vision confidence, multi-frame stability, and post-action validation are sufficient.

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
Do not constrain algorithm, model, architecture, search depth, training method, or evaluation design around the user's current computer model or hardware.

Design priority is:
1. strategy strength / accuracy / correctness;
2. reproducible evaluation;
3. architecture extensibility;
4. then deployment optimization.

Runtime, memory, model size, and latency must still be measured as engineering metrics, but they are **not promotion gates unless a specific deployment target is explicitly defined later**.

It is acceptable to use GPU machines, cloud compute, larger models, deeper search, RL/NN training, or heavier offline analysis when they improve the project. Deployment optimization (ONNX Runtime, pruning, quantization, caching, batching, model distillation, smaller fallback models, etc.) should be treated as a separate implementation stage rather than an upfront design constraint.

## Safety / fail-safe for future automation
Vision uncertainty or inconsistent state must stop execution.
Never click when confidence/state validation is insufficient.
Prevent duplicate actions and confirm post-action state before continuing.
