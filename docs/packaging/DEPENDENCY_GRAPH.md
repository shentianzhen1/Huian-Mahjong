# Package dependency graph

This document describes the dependency direction that the current umbrella
distribution must preserve before any future multi-distribution split.

## Current DAG

```text
                 +--------+
                 |  core  |
                 +--------+
                  ^   ^  ^
                 /    |   \
                /     |    \
          +------+ +--------+ +--------+
          |  AI  | | Vision | |  ...   |
          +------+ +--------+ +--------+
             ^         ^
             |         |
        +-----------+  |
        | Simulator |  |
        +-----------+  |
             ^          |
              \        /
               \      /
              +----------+
              | HintAlpha|
              +----------+
```

The actual allowed edges are:

- **core** → core only
- **AI** → core + AI
- **Vision** → core + Vision
- **Simulator** → core + AI + Simulator
- **Hint Alpha** → core + AI + Vision + Hint Alpha

There is intentionally no dependency from:
- core to any `workspace.*` package;
- AI to Simulator/Vision/Hint;
- Vision to AI/Simulator/Hint;
- Simulator to Vision/Hint;
- Hint Alpha to Simulator.

CI enforces this with `tests/test_workspace_dependency_boundaries.py`.

## Current observations

The 2026-09-22 import audit found:

- AI depends on `huian` rules/environment compatibility, but not on Simulator or Vision.
- Simulator depends on core + AI.
- Vision is almost independent of product/AI code; PublicState reads only core
  match constants such as total score and hand count.
- Hint Alpha is the top product shell and depends on core + AI + Vision.
- No live Executor package participates in this graph.

## Split order implied by the graph

A real multi-distribution migration should follow the dependency direction:

1. stabilize **core**;
2. make **AI** and **Vision** independently installable against core;
3. make **Simulator** install against core + AI;
4. move **Hint Alpha** last, after AI/Vision package APIs are stable;
5. keep Executor outside the packaging plan until its separate safety gate exists.

This ordering minimizes temporary circular dependencies and avoids duplicating
source trees.

## Guardrail vs. package split

The repository still ships one umbrella distribution today. This dependency
contract is a prerequisite for a real split; it is not a claim that separate
`huian-ai`, `huian-vision`, etc. wheels already exist.
