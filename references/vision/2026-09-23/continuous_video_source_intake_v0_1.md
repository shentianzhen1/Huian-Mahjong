# #69 — retrieved real continuous videos, verified development intake

Date: 2026-09-23. This is the same previously reviewed match, **not a
source-disjoint holdout**. Do not mix this validation with formal Vision #7
promotion, and do not turn Executor on.

## What became available

The original complete eight-hand recordings and special `14.mp4` were located
in the user's connected Google Drive **Huian** folder and successfully retrieved
as nine continuous video binaries. Raw video bytes, private Google Drive IDs,
and personal identifiers stay outside the public GitHub repository.

`continuous_video_source_intake_v0_1.json` records the SHA256 of every
retrieved binary plus its ffprobe duration, dimensions, frame count and
anonymized source session.

SHA256 checks against the already-archived source hashes in
`references/gameplay/2026-09-19/`:

- **Exact, byte-identical:** hand 1 (`3.mp4`), hands 5–8
  (`10.mp4`–`13.mp4`), and special `14.mp4`: **6/9**.
- **Not byte-identical:** Google Drive `4.mp4`, `5.mp4`, `9.mp4` versus
  archived `4.mov`, `5.mov`, `9.mov`: **3/9**.
  Their durations and dimensions are consistent with the archive, but this is
  **not** proof of content equivalence. Treat them as separately hashed
  development video variants, not as exact archived-source matches.

Never transfer a truth row keyed by an archived MOV hash onto a differently
hashed MP4 just because the basename or duration looks familiar.

## First continuous-source visual reconnaissance (hand 1)

`3.mp4` is exactly
`1560c1e04a632f07dc5f53947ba3080ed93ff927a7bd028a457f3415b0bc69a3`.
The verified capture is 1046×480, approximately 29 fps, 1809 frames,
62.403 s. Frames have been inspected at **1-second intervals** through the
whole clip; key frames were also extracted at exact indices below.

| Video-relative frame | Approx. time | Direct visual observation |
| ---: | ---: | --- |
| 116 | 4.00 s | 开局 animation; do not confuse replay UI with match hand index. |
| 406 | 14.00 s | Enlarged central 中 face/action-focus candidate; **not enough by itself to label a DISCARD or actor**. |
| 1508 | 52.00 s | Large 自摸 animation; replay-control overlay obscures part of the public river. |
| 1624 | 56.00 s | Terminal settlement explicitly reads 第1/8局 and shows upper row +26, lower row −26, 自摸×2; consistent with archived hand-1 settlement. |

The center-area **进度 N/18** is the *replay/action progress bar*, not the
match hand index **第1/8局**. A prominent public tile face in the center is
not automatically an opponent discard: its presentation may be transient,
an offer, or another action animation. The top/bottom presentation shown in
one video is also not automatically a verified seat-number mapping.

This is an initial full-duration *coarse sample plus selected frame* review,
not a frame-by-frame frozen action-truth set. No actor/turn precision,
DISCARD precision, APPEARED false-positive rate, or temporal reconstruction
recall has been measured from it yet.

## Immediate executable development use

1. Use byte-exact hand 1 `3.mp4` as the primary available continuous
   **development** source. Maintain its SHA256 and exact video-relative frame
   index on every reviewed event. The 1-second contact sampling is navigation
   only; inspect every frame (or enough neighboring frames to exhaustively
   label the chosen interval) before freezing an interval in
   `action_attribution_truth.blank.json`.
2. Review a short contiguous interval **with negative/no-action frames as
   well as visible actions**. Freeze manual truth **before** inspecting model
   outputs. If replay controls obscure the river or actor evidence, use
   actor/turn UNKNOWN or leave an interval unapproved rather than guessing.
3. Replay actual public geometry detector → candidate tracker → reviewed
   channel → river/meld observer → temporal action assembler. Save source,
   tracking epoch, frame and model provenance. APPEARED never equals DISCARD.
4. Feed real assembler predictions and independently frozen manual truth into
   `workspace.vision.action_attribution_eval`; report abstentions,
   actor/turn coverage, false positives and misses with per-frame refs.
5. Use the other exact-match recordings for later **development** variety;
   source-disjoint formal promotion must use new untouched recordings under
   #7.

This closes the mistaken operational blocker “raw continuous videos not
accessible” for development #69. It does **not** close real-video accuracy
validation, manual truth, public-region tile identity, or formal #7 promotion.
