# Packaging Boundary

## Current state

The repository currently ships one umbrella Python distribution:

`huian-mahjong-assistant==0.2.0`

Its installed runtime namespaces are intentionally explicit:

- `huian/`
- `mahjong_framework/`
- `workspace/ai/`
- `workspace/simulator/`
- `workspace/vision/`
- `workspace/hint_alpha/`

The following repository areas are comparison/evidence/development assets and must never enter the wheel:

- `legacy_code/`
- `tests/`
- `dataset/`
- `references/`

CI inspects the installed distribution metadata and fails if this boundary regresses.

## Why extras are not a package split

Python extras such as `.[vision]` and `.[hint-alpha]` only control dependency installation.
They do **not** selectively remove Python modules from the wheel.

Therefore changing:

`pip install .`

to:

`pip install ".[vision]"`

does not by itself create a separate `huian-vision` package. A real split requires separate distribution build roots and deliberate import/API migration.

## Target shape

Long-term packaging can move toward:

- `huian-rules` — `huian.rules`, `huian.environment`, core framework
- `huian-sim` — simulator and evaluation
- `huian-ai` — agents
- `huian-vision` — capture/recognition and Vision tooling
- `huian-hint-alpha` — internal read-only product shell

This is an engineering boundary, not a release promise.

See also: [DEPENDENCY_GRAPH.md](DEPENDENCY_GRAPH.md) for the enforced cross-package import DAG.

## Migration order

1. Keep the umbrella wheel stable and lock its contents in CI.
2. Remove cross-package imports that make independent distributions impossible.
3. Give each future distribution its own import/API contract and tests.
4. Move console scripts only after their owning distribution can install independently.
5. Keep `legacy_code/` comparison-only throughout the migration.
6. Do not combine package-boundary moves with Mahjong rule or scoring changes.

## Non-goals

- No Executor packaging while Executor is disabled.
- No duplication of source trees just to manufacture separate wheels.
- No breaking public imports solely for repository hygiene.
