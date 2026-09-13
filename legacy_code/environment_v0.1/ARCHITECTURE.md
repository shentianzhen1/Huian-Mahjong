# Quanzhou Mahjong Architecture

```text
Quanzhou Rules
      ↓
Quanzhou Environment
      ↓
Quanzhou Simulator
      ↓
Quanzhou AI
      ↓
Quanzhou Vision
      ↓
Executor
```

## Environment responsibilities

- Own `GameState`
- Apply an already-legal `Action`
- Create deterministic state transitions
- Keep event history
- Support clone/checkpoint/rollback
- Expose terminal state and reward
- Stay independent from vision and AI

## Core APIs

```python
env.reset()
env.legal_actions()
env.step(action)
env.clone()
token = env.checkpoint()
env.rollback(token)
env.is_terminal()
env.get_reward()
```

## Future Monte Carlo flow

```text
current environment
    ↓ clone
candidate action
    ↓ step
sample hidden state / wall
    ↓ rollout
terminal reward
    ↓ repeat thousands of times
compare expected value
```
