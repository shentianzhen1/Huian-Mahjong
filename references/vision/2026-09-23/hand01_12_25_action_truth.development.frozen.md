# #69 — first real, frozen *development* action truth (hand 1, 12–25 s)

**Frozen before running or inspecting machine predictions.** Video binary is the
byte-verified `3.mp4`, SHA256
`1560c1e04a632f07dc5f53947ba3080ed93ff927a7bd028a457f3415b0bc69a3`.
This is a previously reviewed match, **not** a source-disjoint evaluation or
formal Vision/Executor promotion dataset. No raw video, Google Drive ID,
private screenshots or personally identifying match metadata is published.

Canonical frozen, independently reviewed JSON:
`hand01_12_25_action_truth.development.frozen.json`, the loader-compatible
`public_action_attribution_eval_v0_1` schema. It is independent of any
model-predictions file. Its `truth_frozen=true` is **development evidence**
only; do not update its events using machine output.

## Scope and review method

- Video interval: first hand **12.000000–25.000000 seconds**, inclusive,
  original 0-index source frames **348–725**, `stream_epoch=0`. The original
  is 1046×480, video stream rate 29 fps and variable-frame timestamps
  verified with ffprobe; timestamps below are source PTS, not wall-clock.
- Direct reviewer visual audit: watch a complete chronological sequence of
  **quarter-second original-frame contact sheets**, compare pre/post original
  full-size frames around all candidate actions, and inspect unexpected
  upper hand / lower hand / both public zones / action-progress changes
  flagged by a **per-frame ROI image-difference scan of all 378 frames**.
  Image differencing is *navigation*, never an action classifier or truth
  label. Cross-check the complete interval's replay progress **1/18 → 5/18**
  against the four independently visible public hand-to-river changes.
  Intermediate draws/hand reorder and non-action UI overlay removal were
  separately checked rather than mislabeled as DISCARD.
- Reviewer confirmation: the user explicitly confirmed this exact source's
  **lower detailed hand is player, upper hand is opponent**. This does *not*
  establish simulator seat 0/1 or the layout of any other recording.
- The replay control overlay covers some of the playfield, so independent
  `turn_actor` evidence is **unavailable** for every frozen event; all
  `turn_actor=null`. No implicit turn alternation is imported from Mahjong
  rules or inferred from the action actor. Chinese tile glyphs below are
  visual-review notes; the strict truth's normalized `tile=null` until
  independent public-region tile-ID calibration is demonstrated.

## Exhaustive visible public actions for this interval

The frozen event frame is an unambiguous **public-tile-visible anchor**, not
the original finger click or animation's earliest hint. The earlier
`hand01_12_25_public_action_review_draft_v0_1.json` retains exploratory
first-change candidates; a 1-frame difference between candidate and frozen
public-tile anchor is deliberate.

| ID | Source frame | Source PTS (s) | Actor (user-confirmed source mapping) | Reviewed public tile | Visual evidence |
|---|---:|---:|---|---|---|
| A | 404 | 13.931033 | opponent / upper | 中 | Upper concealed 中 disappears and public upper-right 中 appears; central animation alone would not prove DISCARD. |
| B | 490 | 16.896556 | player / lower | 白板 | Lower concealed 白板 disappears and public lower-left 白板 appears; a separate bottom-right draw is not a second action. |
| C | 587 | 20.241378 | opponent / upper | 北 | Upper concealed 北 disappears and public upper-right 北 appears. |
| D | 685 | 23.620689 | player / lower | 發 | Lower concealed 發 disappears and public lower-left 發 appears. |

Quiet intervals within **12–25 s** were included in the audit; no other
*visible qualifying public action* was found. This does **not** certify that
the replay reveals hidden information or that all future game UI skins expose
every action. The public action event count for this **one development
interval** is four; no accuracy number can be computed without separately
captured **real machine predictions** on the identical source and epoch.

## Replay alignment audit

The 1/18→5/18 on-screen `进度` is a replay action-progress counter, not
the match hand number. It changes with the four observed outplays; no other
progress step falls within the frozen interval. Selected apparent anomalies
were checked: the waiting text disappears near frame 368 without any
public discard; around frame 513 the next draw reorganizes a hand;
frames 631–642 and 704–706 are existing-tile/turn-display animations.
These are part of the negative review, not extra truth actions.

## Next evaluation step

Run the actual public detector / candidate tracker / river and meld
observers / temporal assembler **against the same SHA256 capture**, then
export real source/epoch/frame-referenced predictions to an independent
prediction JSON. Evaluate against this frozen truth with
`python -m workspace.vision.action_attribution_eval --truth ... --predictions ... --output ...`.
Report false positives in quiet periods, missed events, wrong actor and
known-turn coverage separately. A formal source-disjoint holdout must use
new untouched recordings. **Executor remains OFF.**
