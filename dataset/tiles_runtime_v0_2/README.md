# Vision Runtime Dataset V0.2 (local-only)

This directory contains the reproducible, reviewed Runtime Vision asset set.
It is not a public raw-media dataset.

- `manifest.json`, the final reviewed `labels.jsonl`, and `roi_profiles/*.json`
  are Git-tracked long-term assets. Labels use anonymous `source_id` and
  `source_session`; absolute local paths are forbidden.
- `roi_profiles/` contains only manually calibrated geometry, never guessed boxes.
- `templates/hand/`, legacy-named `templates/draw/`, and `templates/gold/` may contain only
  tightly cropped Mahjong tiles after human privacy review. Final reviewed
  templates are Git tracked. The `templates/draw/` path is retained for asset
  compatibility; its geometry meaning is `draw_visual`, never a permanent
  game-state region.
- `validation/reports/` contains formal, anonymized reports and is Git tracked.
  `validation/generated/`, candidate indexes, full frames, videos, and all
  temporary crops stay local and ignored under `work/` or `generated/`.

Every future label must include `source_id`, `source_session`, `source_frame`,
`bbox`, `slot`, `tile_id`, `approved`, and `sha256`. No automatic selector is a
labeling authority. Runtime assets remain `safe_for_executor=false` until a
separate verified evaluation is complete.

Geometry uses `hand`, `draw_visual`, `meld`, `gold`, and `unknown`.
`draw_visual` is transient: Vision observes it, the temporal tracker emits one
draw event across its merge into `hand`, and only a later GameState integration
may consume that event. Legacy `draw_region` label and ROI assets are read as
`draw_visual`; they are not evidence that draw is a permanent semantic zone.
