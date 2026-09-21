# Runtime Vision V0.2

`runtime_reader` is the read-only smoke path that joins Dynamic Geometry V0.1
with the human-approved Runtime V0.2 tile templates. It never mutates
GameState, calls Hint Alpha, or controls the game UI.

For one stable 3--5 frame burst:

```powershell
.\.venv-capture\Scripts\python.exe -m workspace.vision.tiles_runtime_v0_2.runtime_reader `
  --video <local-private-recording> `
  --start-frame <frame> `
  --frames 5 `
  --session <anonymous-session-id> `
  --output dataset/tiles_runtime_v0_2/work/runtime_smoke/result.json
```

Exact `tile_id` is emitted only when all current gates pass:

1. Geometry agrees across at least three frames.
2. Template confidence is at least `0.82`.
3. The class has independent-session support in the observed visual region.
4. Its visual category has no missing standard tile class.

`candidate_tile_id` is diagnostic only. Because `M2` is currently missing,
all Wan candidate identities fail closed to `UNKNOWN`; this prevents a true
M2 from being silently reported as M1 or M3. `safe_for_hint` and
`safe_for_executor` remain `false`.
