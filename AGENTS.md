# Agent Instructions

## Core rule
Do not invent Mahjong rules. If a rule is uncertain, mark it as UNKNOWN/TODO/configurable instead of hard-coding a guess.

## Evidence priority
1. Real Huian in-game screenshots / settlement screens
2. Huian player feedback from actual gameplay
3. In-game rule pages
4. External Quanzhou/Huian web sources

Never let lower-priority evidence overwrite higher-priority evidence.

## Source-of-truth order
1. GitHub Issues / TODO.md for current execution work.
2. RULE_STATUS.md for confirmed/unknown Mahjong rules.
3. RULE_EVIDENCE_MATRIX.md for evidence and state-machine gaps.
4. PROJECT_STATUS.md for the current integrated snapshot.
5. CHANGELOG.md only for history; do not treat older entries as current state.

If these disagree, do not average them. Prefer the higher-priority current source and fix the stale document.

## Rule isolation / versioning
High-impact runtime rules are registered in `huian/rules/registry.py` and grouped into an immutable `DEFAULT_RULE_SNAPSHOT`.

- `RULE_STATUS.md` / `RULE_EVIDENCE_MATRIX.md` remain the human evidence truth; the registry mirrors evidence-backed runtime values and must not invent rules.
- A corrected HIGH/CRITICAL rule must increment only that rule's revision, update its evidence/value/status, and add focused regression evidence.
- Saved Simulator and paired AI evaluation outputs must retain their rule snapshot fingerprint. Never combine score/EV promotion evidence across different fingerprints.
- WORKING/UNKNOWN values must not enter official AI reward/EV through a hidden fallback; use the confirmed gate or stop safely.
- Prefer small rule IDs and dependencies (legality vs multiplier vs full settlement) over one monolithic special-rule switch.
- See `docs/rule_isolation.md`.

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
1. Close remaining special-result evidence/settlement gaps: Qiangjin exact eligibility+settlement, Sanjindao real terminal settlement, Rob-Kong/Gang-Hu settlement, and Eight-Flower-You real multiplier/priority. The core Youjin/Double/Triple progression flow is implemented; do not reopen superseded response semantics unless higher-priority evidence conflicts.
2. Preserve the now-confirmed ordinary settlement/dealer-base/full-match regression chain; do not reopen solved rules unless higher-priority evidence conflicts.
3. Treat `CurrentAgent = MeldAwareShantenAgent V0.10` as the current AI frontier. Keep TenpaiRiskTieBreakAgent V0.6 as the fixed main comparison baseline and ShantenAgent V0.3 as the explicit offense ablation baseline. V0.11/V0.12's "exclude Jin waits, then apply immediate score-aware value" path was structurally non-triggering and must not be revived without new evidence. Next strategy work should focus on Jin-aware meld/special-state EV, KONG as a separate decision, or multi-step/full-match EV. Any promoted strategy must beat V0.10 in fixed-wall, seat-swapped, identity-stable-RNG paired evaluation.
4. Preserve the confirmed opening-gold physical accounting: the opened Jin is one reserved physical copy, cannot return to the drawable wall, and leaves at most three playable Jin copies.
5. Preserve the measured Vision baseline instead of chasing tiny static-template gains: hand+draw strict holdout is currently 98.66%, while Gold has same-batch temporal evidence but still needs independent-session generalization. Prioritize PublicState digit reading (scores / remaining tiles / hand index), label audit, new-session Gold/Draw validation, and scale/move/occlusion stress tests.
6. Integrate Vision observations with Rules/Match validation only through conservative state fusion. Score observations must conserve 2000 in the target two-player room; inconsistent or low-confidence reads must stop state updates.
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
