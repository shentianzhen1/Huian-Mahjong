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

### Rules
Owns legality, Hu/Ting, gold (金), flowers, Chi/Peng/Gang, Sanjindao, Youjin/Double-You/Triple-You, fan and settlement.

Confirmed target scope:
- single gold cannot Pinghu in the selected room
- exactly one gold may self-draw Hu when the standard structure is valid
- exactly two gold tiles can Hu only by self-draw, never from an opponent discard
- ordinary Hu and Youjin are evaluated as separate branches
- direct replay b3892b34 confirms one-gold ordinary self-draw with all three suits present; do not impose a missing-suit requirement
- the same recording shows 庄5/base30 and gold1 + flowers2 + triplet1: ordinary Zimo `(30+4)×2=68`, without extra dealer ×2 or subtraction of the loser’s fan; see `references/gameplay/2026-09-15/b3892b34_zimo68/README.md`
- retained Hu/scoring categories: Pinghu, Zimo, Sanjindao, Gang-Hu, Youjin, Double-You, Triple-You, Eight-Flower You, flowers, repeat-dealer/base scoring
- Sanjindao eligibility is `hand_gold_count >= 3`; declaration is optional, so legal actions must expose both immediate Sanjindao ×3 and continued play toward 三金游. 三金游 is the same state as Triple-You/三游 and is canonicalized as `TRIPLE_YOU` ×16. The exact shared state sequence, non-flower base and full settlements remain unresolved
- every Hu by the kong declarer after a completed Ming/An/Added Kong tail draw is Gang-Hu; rob-kong is a separate response path, with an added-kong-only implementation contract and unresolved actual-room response evidence/scoring
- completed Ming/An/Added Kong draws reuse the normal draw pipeline and record their source as `wall_tail`
- each flower has a confirmed base value of 1 fan
- room541913 complete-match evidence reconciles “坐庄底分5分，连庄+5”: non-dealer own display base is 5, a newly sitting dealer's current settlement base is 10, each repeat adds +5, and a dealer change resets the new dealer to 10. Player confirmation 2026-09-19: no cap while the same dealer keeps the seat; +5 continues until the fixed 8-hand match ends, and dealer loss resets the new dealer to 10
- Youjin/Double-You/Triple-You multipliers are 4/8/16; winner fan, including one fan per flower, is added to current dealer base before the Hu multiplier. No extra Youjin-chain dealer-winner ×2 applies in the target room: room541913 hand5 dealer Youjin settles `(15+4)×4=76`, and the earlier dealer Triple-You settles `(35+3)×16=608`. Recorded Triple-You: `(35 + gold 1 + flowers 2) × 16 = 608`
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

Confirmed opponent Hu permissions during the Youjin chain:
- opponent of a Youjin player may Hu
- opponent of a Double-You player may self-draw Hu
- opponent of a Triple-You player may Hu only by kong-replacement self-draw

Any more specific Youjin/Double-You response windows remain UNKNOWN unless listed
in `RULE_STATUS.md`.

### Environment
Owns GameState and state transitions:
`reset()`, `legal_actions()`, `step(action)`, `clone()`, `checkpoint()`, `rollback()`, `is_terminal()`, `get_reward()`, event log.

The user's current implementation contract adds a non-gold Peng upgrade through `ADD_KONG` → `ROB_KONG_WINDOW`. Only this window offers eligible `ROB_KONG_HU` or `PASS`. The original Peng and fourth hand tile remain physically unchanged until PASS commits `ADDED_GANG`; `pending_kong` never counts as another tile. PASS then requires a tail draw and the existing flower pipeline. A successful rob records winner/source without completing the kong. The 66fe863f replay supports the upgrade itself, not the rob-kong interaction; Ming/An rob-kong remains UNKNOWN.

### Simulator
Runs full games and batches. Must support deterministic fixed walls/seeds and paired evaluation with swapped seats/dealer.

`SimulatorConfig.enable_added_kong` defaults to True; False removes added-kong candidates. The broad `enable_rob_kong` remains False/unsupported and must not be confused with the implemented added-kong-only response window. Successful rob, declared kong-tail Hu, and an added-kong tail draw without Hu stop with `ROB_KONG_SCORING_UNKNOWN`, `GANG_HU_SCORING_UNKNOWN`, and `ADD_KONG_SCORING_UNKNOWN` respectively. The 16-tile boundary cannot manufacture a zero-fee settlement for an added-kong hand, and flower replacement cannot cross it. These stops retain audit facts and do not use ordinary simulation rewards.

### AI
Roadmap:
Baseline heuristics -> Monte Carlo EV -> opponent/danger model -> optional RL/NN later.

Huian AI should prioritize ordinary Hu/Zimo value, Sanjindao, Youjin paths and
risk. When Sanjindao is available it must compare declaring now with continuing
toward 三游/三金游; exact EV remains blocked until its trigger and multiplier are
confirmed. It should not optimize toward Menqing, Pengpenghu, Qingyise, Hunyise or
other excluded complex fan patterns.

Decision output should distinguish:
- Win Probability
- State Value
- Expected Score / EV
Never label arbitrary model value as a probability.

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
