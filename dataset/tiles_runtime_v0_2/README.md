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


## Private Gold-skin review queue

When a real recording contains yellow Gold-skinned concealed tiles but the
exact source frame/bbox is not yet frozen, first build a **private review
queue**. This step is deliberately non-authoritative: it never edits
`labels.jsonl`, never marks a crop approved, and every exported candidate is
`safe_for_hint=false` / `safe_for_executor=false`.

The output directory MUST be outside the Git repository. The tool stores only
tile-sized candidate crops plus a local JSON review sheet; it does not copy the
full frame or video into the repository.

For the current first-hand M6 review target, use the stronger late-hand
human-reviewed window: **170–176 seconds**. The 174–175 second frames visibly
retain both yellow M6 Gold copies. This target belongs to the existing logical
session `session_eight_hand_match_a`; do not create a new session for this clip.

```powershell
python -m workspace.vision.tiles_runtime_v0_2.gold_skin_review_queue `
  --video "D:\path\to\private_match.mp4" `
  --dataset dataset/tiles_runtime_v0_2 `
  --output-dir "D:\HuianPrivateReview\gold_m6" `
  --source-session "<existing logical session for that match>" `
  --start-seconds 105 `
  --end-seconds 115 `
  --sample-fps 2 `
  --target-tile M6 `
  --max-candidates 12
```

`source_session` must describe the **logical match/source group**, not the
clip filename. If this Gold crop comes from a match already represented in the
Runtime bank, reuse that match's existing session; do not create a new session
just because the video is a different clip.

The queue sorts M6 top-1 proposals first, then by classifier confidence, but a
machine proposal is never labeling authority. Open the exported tile crops and
the original source frame, confirm that the selected crop is genuinely M6 and
contains only the yellow tile face, then admit exactly that reviewed crop with
`reviewed_tile_intake --gold-skin-only`.

After intake, rerun the source-disjoint Gold identity report and Runtime smoke
at the unchanged `0.82` threshold before considering any promotion.

## Reviewed single-tile intake

Use `workspace.vision.tiles_runtime_v0_2.reviewed_tile_intake` only after a
human has verified the exact tile identity and rectangle. The private source
video/image stays local; the tool persists only the tile crop plus anonymous
hash/session provenance. It requires explicit `--approved` and rejects
oversized crops, duplicate source rectangles, and non-standard tile IDs.

`source_session` is a **logical source group**, not a video filename. Multiple
clips cut from the same match (for example, one eight-hand match split into
several recordings) MUST reuse the same anonymized session ID. Different file
hashes from one match must never be counted as independent cross-session
evidence.

Example:

```bash
python -m workspace.vision.tiles_runtime_v0_2.reviewed_tile_intake \
  --source data/private/match_clip.mp4 \
  --source-session session_match_a \
  --source-frame 1234 \
  --bbox 400 380 42 66 \
  --slot 5 \
  --tile-id M2 \
  --region hand_region \
  --reviewer manual \
  --approved
```

After intake, rerun the Runtime Vision regression and dataset audit. New samples
remain development/prototype evidence; they do not change formal Vision
promotion status.


Yellow Gold-skinned concealed tiles may be admitted with `--gold-skin-only`.
Such a sample contributes only to the Gold-normalized identity bank and its
Gold-identity session coverage. It is deliberately excluded from ordinary
`hand_region` / `draw_visual` template banks and concealed-identity
evaluation, so the yellow UI skin cannot pollute normal white-tile recognition.

Vision CI publishes three separate validation views: same-region ordinary
templates, pooled concealed identity, and source-disjoint Gold-normalized
identity. The 0.82 acceptance threshold remains unchanged.


### Recover an old reviewed M2 locally

The 2026-09-19 V0.1 eight-hand dataset had 168 human-reviewed labels and did
contain M2, but its raw labels/ROI images were deliberately kept local. Runtime
V0.2 was rebuilt from a different geometry-holdout review pool, so that legacy
M2 was not automatically migrated.

If a local checkout still contains
`dataset/tiles_v0_1/labels/tiles.jsonl` and the corresponding ignored
`images/rois/` assets, scan only the old approved M2 labels first:

```bash
python -m workspace.vision.tiles_runtime_v0_2.legacy_reviewed_recovery \
  --legacy-dataset dataset/tiles_v0_1 \
  --runtime-dataset dataset/tiles_runtime_v0_2 \
  --tile-id M2
```

This is scan-only. It writes a local contact sheet and candidate plan under
`dataset/tiles_runtime_v0_2/work/legacy_reviewed_recovery/M2/` and does not
change tracked Runtime labels/templates.

After visually re-confirming one candidate, promotion requires both explicit
approval and an explicit **logical** session:

```bash
python -m workspace.vision.tiles_runtime_v0_2.legacy_reviewed_recovery \
  --runtime-dataset dataset/tiles_runtime_v0_2 \
  --tile-id M2 \
  --approve-candidate legacy_xxxxxxxxxxxxxxxx \
  --logical-session session_legacy_match_a \
  --reviewer manual \
  --approved
```

All clips from the same eight-hand match MUST use the same logical session even
if the old V0.1 labels used one session per video. This recovery path restores
class coverage without falsely creating cross-session evidence. Legacy private
paths and old video names are not written into the tracked Runtime label.

Geometry uses `hand`, `draw_visual`, `meld`, `gold`, and `unknown`.
`draw_visual` is transient: Vision observes it, the temporal tracker emits one
draw event across its merge into `hand`, and only a later GameState integration
may consume that event. Legacy `draw_region` label and ROI assets are read as
`draw_visual`; they are not evidence that draw is a permanent semantic zone.

## Promotion status

Runtime Vision V0.2 is an **experimental, read-only prototype**. The 2026-09-22 closeout audit found that the locked Phase 5C blind holdout did not pass every acceptance gate, so the reviewed Phase 6 assets are retained only as development/prototype assets. They must not be cited as evidence that V0.2 has formally generalized or is ready for Hint/Executor control.

Formal promotion remains blocked until a new source-disjoint blind holdout is reviewed and passes all acceptance gates. Runtime replay smoke tests with a known `session` must exclude templates from that same session. `safe_for_executor=false` remains mandatory.


## Coverage must be interpreted by classifier domain

The global Runtime label inventory currently covers **34/34** standard classes.
That number is only a dataset summary: it is **not** sufficient evidence that
every Runtime region can classify every class safely.

Current tracked domain coverage after the reviewed concealed M2 intake:

- global standard inventory: **34/34**;
- `hand_region`: 30/34; missing `M7, M8, P2, G`;
- `draw_visual`: 11/34;
- pooled `concealed_identity` (hand + draw visual): **34/34**;
- `gold_region`: 2/34;
- normalized `gold_identity` full-bank domain: **34/34**.

Class completeness is necessary but not sufficient. The new M2 closes the
**Wan-suit** completeness blocker, so Wan candidates such as M6 are no longer
blocked merely because M2 was absent. M2 itself still has only one logical
source session and must fail its cross-session identity gate. The pooled concealed domain now has all 34 standard classes. The new `N`
sample has only one concealed logical session, so N itself still fails the
cross-session gate. Existing classes retain their own confidence and
multi-session gates.

M6 now has a second reviewed concealed-domain sample under
`session_eight_hand_match_a`, distinct from the earlier approved M6
`draw_visual` session. This satisfies the stored cross-session support count
for M6 in the pooled concealed domain, but does not by itself prove that live
Gold-skinned M6 will cross the 0.82 confidence threshold.

The runtime category-completeness gate is therefore scoped to the classifier
domain actually used for the observation. A public river/meld M2 may be useful
for future public-tile work, but it must never make concealed-hand Wan
classification appear complete.

The audit also reports `multi_session_covered`. That field means only
"present under at least two stored logical `source_session` values"; it must
not be described as independent original-match evidence unless provenance
separately proves that relationship.
