# Project Context

## Goal
Build an offline-first Windows assistant for 开心惠安二人麻将 that can eventually:
1. understand the exact Huian rules
2. simulate complete games
3. choose strong actions using EV/win-rate analysis
4. recognize a real Android game screen
5. optionally execute actions through Android control

## Primary architecture
`Rules -> Environment -> Simulator -> AI -> Vision -> Executor`

High-impact rules also pass through a versioned metadata boundary:
`Evidence -> RULE_STATUS -> Rule Registry / RuleSnapshot -> Rules services -> Simulator/AI evaluation`.
Each snapshot has a stable fingerprint, so AI score/EV evidence produced under an older rule set cannot be silently treated as current evidence. See `docs/rule_isolation.md`.

### Rules
Owns legality, Hu/Ting, gold (金), flowers, Chi/Peng/Gang, Sanjindao, Youjin/Double-You/Triple-You, fan and settlement.

Confirmed target scope:
- single gold cannot Pinghu in the selected room
- exactly one gold may self-draw Hu when the standard structure is valid
- exactly two gold tiles can Hu only by self-draw, never from an opponent discard
- the opened gold indicator is itself one physical copy and stays outside the drawable wall; therefore only three playable gold copies can exist
- ordinary Hu and Youjin are evaluated as separate branches
- direct replay b3892b34 confirms one-gold ordinary self-draw with all three suits present; do not impose a missing-suit requirement
- the same recording shows 庄5/base30 and gold1 + flowers2 + triplet1: ordinary Zimo `(30+4)×2=68`, without extra dealer ×2 or subtraction of the loser’s fan; see `references/gameplay/2026-09-15/b3892b34_zimo68/README.md`
- retained Hu/scoring categories: Pinghu, Zimo, Sanjindao, Gang-Hu, Youjin, Double-You, Triple-You, Eight-Flower You, flowers, repeat-dealer/base scoring
- Sanjindao is an optional current-player special window. Confirmed prompts include opening with all 3 playable golds, a valid 2→3 gold draw, and—after an earlier PASS—a later own draw while exactly 3 gold still remain. PASS closes only the current prompt; it does not permanently disable later Sanjindao, ordinary Hu, or Youjin-family play. Player clarification on 2026-09-20 confirms the opened gold indicator is the fourth physical copy and is non-drawable, so 3 playable golds is the physical maximum; there is no four-gold recheck state. Sanjindao multiplier ×3 is confirmed/adopted, while direct target-room payment/dealer continuation/full settlement remain unresolved. 三金游 is the same state as Triple-You/三游 and is canonicalized as `TRIPLE_YOU` ×16
- every Hu by the kong declarer after a completed Ming/An/Added Kong tail draw is Gang-Hu; rob-kong is a separate response path, with an added-kong-only implementation contract and unresolved actual-room response evidence/scoring
- completed Ming/An/Added Kong draws reuse the normal draw pipeline and record their source as `wall_tail`
- each flower has a confirmed base value of 1 fan
- match_evidence_001 complete-match evidence reconciles “坐庄底分5分，连庄+5”: non-dealer own display base is 5, a newly sitting dealer's current settlement base is 10, each repeat adds +5, and a dealer change resets the new dealer to 10. Player confirmation 2026-09-19: no cap while the same dealer keeps the seat; +5 continues until the fixed 8-hand match ends, and dealer loss resets the new dealer to 10
- Youjin/Double-You/Triple-You multipliers are 4/8/16; winner fan, including one fan per flower, is added to current dealer base before the Hu multiplier. No extra Youjin-chain dealer-winner ×2 applies in the target room: match_evidence_001 hand5 dealer Youjin settles `(15+4)×4=76`, and the earlier dealer Triple-You settles `(35+3)×16=608`. Recorded Triple-You: `(35 + gold 1 + flowers 2) × 16 = 608`
- direct 66fe863f replay adds a P1 Peng→added-kong sequence and Chi→discard S1→opponent turn→M7→Youjin example. Its non-dealer winner has fan5 (gold1/flower1/triplet1/kong2), own-base display40, and current-dealer-base net100: `(20+5)×4`; it does not establish rob-kong windows or the full Youjin state machine
- no extra fan families for Menqing, Pengpenghu, Qingyise, Hunyise, or similar complex combinations
- when a discard has multiple legal Chi sequences, Rules exposes every sequence and the player/AI selects one exact option

The excluded fan names do not make an otherwise standard Hu structure illegal.
They simply add no named fan or AI objective. Exact special-Hu triggers and
unverified multipliers remain controlled by `RULE_STATUS.md`.

Current Rules API boundary:
- `HuContext` carries `SELF_DRAW`, `DISCARD`, `KONG_TAIL_DRAW`, or `ROB_KONG`, the winning tile, and the resolved kong kind where applicable
- discard-Hu analysis requires the winning tile, so an opponent-discarded gold cannot be silently accepted
- `SanjindaoDecision` exposes eligibility, confirmed multiplier 3, and `DECLARE_SANJINDAO` / `CONTINUE_PLAY`; phase timing and full settlement stay outside the pure eligibility service
- `YoujinStage.SANJIN_YOU` is an alias of `YoujinStage.TRIPLE_YOU`; it must not create a second state, while Sanjindao remains independent
- `YoujinScoreTerms` accepts the externally audited current dealer base and winner fan, then applies confirmed Youjin factors with dealer multiplier fixed at 1 by direct dealer-Youjin and dealer-Triple-You settlements; it does not decide payer or automatically aggregate unresolved fan categories
- `DrawSource` emits `wall_head` / `wall_tail`; old `head` / `tail` replay values are accepted only as migration aliases and new events are canonical

Confirmed Chi interaction boundary:
- Rules returns a list of concrete Chi sequences, not only `true/false`
- Environment actions carry the selected three-tile sequence and execute only it
- after the selected Chi completes, Environment immediately enters discard phase for that player; no normal draw occurs between Chi and discard
- AI evaluates each Chi sequence as a different action
- Vision/Executor must identify and select the matching option in the mini-program panel; uncertainty stops execution

Confirmed opponent response contract during the Youjin chain:
- Youjin / Double-You / Triple-You each gives the opponent exactly one normal draw opportunity.
- If that draw is a legal self-Hu, Hu is optional: the responder may Hu or decline and discard one tile.
- If the responder does not Hu, exactly one tile must be discarded; this special response discard enters the river but opens no ordinary Chi/Peng/Kong/discard-Hu claim window.
- After that discard, single/double You returns to the Youjin player for the confirmed progression draw; Triple-You settles at ×16.
- Youjin-stage identity is structural/stateful and must never be inferred from current Jin count alone.
- Flowers and AN_GANG / ADD_KONG may continue during the Youjin player's progression turn under the confirmed flow. Remaining scoring blockers are the shared Gang-Hu / Rob-Kong settlement gaps documented in Issue #4.

### Environment
Owns GameState and state transitions:
`reset()`, `legal_actions()`, `step(action)`, `clone()`, `checkpoint()`, `rollback()`, `is_terminal()`, `get_reward()`, event log.

The user's current implementation contract adds a non-gold Peng upgrade through `ADD_KONG` → `ROB_KONG_WINDOW`. Only this added-kong window may be robbed; MING_GANG and AN_GANG are confirmed not robbable. The original Peng and fourth hand tile remain physically unchanged until PASS commits `ADDED_GANG`; `pending_kong` never counts as another tile. PASS then requires a tail draw and the existing flower pipeline. A successful rob records winner/source without completing the kong. Rob-Kong multiplier ×2 is confirmed; payment/dealer continuation/full target-room settlement remain unresolved.

### Simulator
Runs full games and batches. Must support deterministic fixed walls/seeds and paired evaluation with swapped seats/dealer.

`SimulatorConfig.enable_added_kong` defaults to True; False removes added-kong candidates. The broad `enable_rob_kong` remains False/unsupported and must not be confused with the implemented added-kong-only response window. Completed MING_GANG / AN_GANG / ADD_KONG have no independent kong fee and may continue through ordinary play, ordinary Hu, or the normal 16-tile draw boundary. Only a successful Rob-Kong Hu and a kong-tail Hu still stop on unresolved real settlement flow via `ROB_KONG_SCORING_UNKNOWN` and `GANG_HU_SCORING_UNKNOWN`. These stops retain audit facts and do not use guessed rewards.

### AI
Roadmap:
Baseline heuristics -> Monte Carlo EV -> opponent/danger model -> optional RL/NN later.

Current AI frontier is `CurrentAgent = MeldAwareShantenAgent V0.10`. V0.10 preserves V0.6's discard policy and changes only CHI/PENG decisions: it compares PASS with each claim followed by the best forced discard, and claims only when the ordinary offense tuple strictly improves. Across two independent promotion batches totaling 200 seed pairs / 400 complete eight-hand matches, V0.10 beat V0.6 by 239 wins to 159 with 2 ties and a mean paired final-score delta of +54.805. `TenpaiRiskTieBreakAgent V0.6` remains the fixed main comparison baseline; `ShantenAgent V0.3` remains the explicit offense ablation baseline.

`PlayerObservation.match_context` carries only public eight-hand context: scores, hand index/hands remaining, dealer, current dealer base and consecutive dealer hands. Match evaluation also records discard/self-draw sources and deal-in counts. V0.11/V0.12's "exclude gold waits, then apply immediate score-aware value" path was structurally non-triggering and must not be revived without new evidence. Future strategy work must compare directly against CurrentAgent V0.10, while retaining V0.6 and V0.3 as controls.

A public-information Monte Carlo ordinary deal-in estimator now exists as research infrastructure. It samples plausible opponent concealed base-tile hands from the physically unseen pool and evaluates ordinary discard-Hu under the target gold restrictions without reading the actual opponent hand or wall order. It excludes Youjin/Sanjindao/Qiangjin and other special states and is not yet a decision policy. Next AI work is to calibrate this probability and runtime, then combine validated immediate-loss probability with expected score, dealer base and match context. Special-result EV must remain separated where settlement is still unresolved.

Decision output should distinguish:
- Win Probability
- State Value
- Expected Score / EV
Never label arbitrary model value as a probability.

AI/Vision architecture is hardware-agnostic by design. Do not reduce model class, search depth, training method, simulation scale, or strategy complexity because of the user's current computer. Measure compute cost, but optimize deployment separately after the strongest validated approach is identified.

### Vision
Preferred future route:
Android -> USB scrcpy -> window/frame capture -> OpenCV -> YOLO -> post-processing -> Rules validator -> GameState

Use coordinate grouping, multi-frame voting/dedup, hand-count validation, max-4-copy checks and legal-state checks.

### Executor
Progression:
1. locate suggested tile only
2. confirm-to-click
3. full automatic execution only after high confidence

Android ADB tap is the preferred future implementation.

## Evaluation philosophy
Do not claim win-rate improvement without measurements.
Use fixed-wall paired tests to reduce luck:
- same wall/seed
- swap seats/dealer
- compare average net score, win rate and deal-in rate across many pairs

New AI only graduates if it quantitatively outperforms the previous AI.

## Strategy modes planned
- win-rate priority
- EV/profit priority
- balanced
- auto mode adapting to score and remaining hands in an 8-hand match

## Current code baseline
The package includes three legacy baselines:
- Core V0.1.1
- Environment V0.1
- Vision Assistant V0.4

They still use Quanzhou naming. Core scoring contains outdated assumptions and must not be treated as final Huian scoring.
In particular, legacy or current boolean Hu helpers that do not receive a win
source cannot correctly enforce the confirmed two-gold self-draw-only rule.

## Python
User currently has Python 3.14.7 on Windows.
If compatibility issues arise with CV/ML dependencies, Python 3.12 64-bit may be installed side-by-side.
Do not force a reinstall unless actually necessary.
