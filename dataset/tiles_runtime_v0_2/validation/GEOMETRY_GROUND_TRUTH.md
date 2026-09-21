# Geometry Ground Truth V0.2

Each non-empty JSONL row is one **human-reviewed** real frame. A detector
proposal is never ground truth until the reviewer has checked it against the
local source frame.

New rows use this schema:

```json
{
  "id": "geo_0001",
  "source_id": "src_...",
  "source_session": "session_...",
  "source_frame": 145,
  "size": [1046, 480],
  "frame_state": "trusted",
  "animation_type": null,
  "scene_type": null,
  "components": [
    {"pixel_bbox": [160, 415, 45, 60], "region_candidate": "hand", "confidence": 1.0}
  ],
  "hand_bboxes": [[160, 415, 45, 60]],
  "draw_visual_bboxes": [],
  "gold_bbox": [114, 412, 47, 64],
  "expected_hand_region_count": 15,
  "expected_draw_visual_count": 0,
  "expected_concealed_tile_count": 15,
  "review_status": "approved_geometry",
  "reviewer": "manual"
}
```

`frame_state` is one of `trusted`, `occluded`, `animation`, or `non_game`. Geometry regions
are `hand`, `draw_visual`, `meld`, `gold`, and `unknown`. The count invariant is:

```
expected_concealed_tile_count =
    expected_hand_region_count + expected_draw_visual_count
```

Normally `expected_draw_visual_count` is 0 or 1. `meld` and public `gold` do not
count as concealed tiles. A moving/merging tile whose geometry cannot be judged
reliably makes the frame `animation`; reviewers do not manufacture a stable box.
Automatic post-discard sorting uses `animation_type=hand_resort`. Such rows are
kept for rejection/temporal validation but excluded from stable geometry and
slot metrics.

Settlement pages and other screens outside active gameplay use
`frame_state=non_game` with an explicit `scene_type` such as `settlement`.
They contain no gameplay component boxes. They test whether geometry refuses
output and are excluded from stable component, region, and hand-count metrics.

Legacy approved rows remain frozen. At read time, `draw` is interpreted as
`draw_visual`, `trust_state` as `frame_state`, and
`expected_hand_component_count` as `expected_hand_region_count`. Compatibility
never rewrites approved bbox or region truth. A legacy row containing more than
one `draw` is preserved and warned about rather than silently corrected.

Source paths, player names, room IDs, tile IDs, and full screenshots are
prohibited.
