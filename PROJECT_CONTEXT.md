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

### Environment
Owns GameState and state transitions:
`reset()`, `legal_actions()`, `step(action)`, `clone()`, `checkpoint()`, `rollback()`, `is_terminal()`, `get_reward()`, event log.

### Simulator
Runs full games and batches. Must support deterministic fixed walls/seeds and paired evaluation with swapped seats/dealer.

### AI
Roadmap:
Baseline heuristics -> Monte Carlo EV -> opponent/danger model -> optional RL/NN later.

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

## Python
User currently has Python 3.14.7 on Windows.
If compatibility issues arise with CV/ML dependencies, Python 3.12 64-bit may be installed side-by-side.
Do not force a reinstall unless actually necessary.
