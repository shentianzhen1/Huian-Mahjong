# Huian Mahjong AI Project

Target game: 开心惠安二人麻将.

Long-term architecture:

`Rules -> Environment -> Simulator -> AI -> Vision -> Executor`

Current status:
- Rules: partially confirmed, still being calibrated from real Huian settlement screenshots and player feedback.
- Environment: V0.1 baseline exists and passes tests.
- Simulator: next major milestone.
- AI: not yet formally started.
- Vision: early prototype exists. Android + scrcpy is the preferred future capture path.
- Executor: not started.

The project is designed to work offline for normal use. Network access should be optional for updates, model sync, or remote training.

See `PROJECT_CONTEXT.md`, `RULE_STATUS.md`, and `TODO.md` before modifying core logic.
