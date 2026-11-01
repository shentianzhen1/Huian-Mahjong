# Validation source readiness — 2026-11-01

Execution and acceptance contract: [Issue #7](https://github.com/shentianzhen1/Huian-Mahjong/issues/7).
Machine-readable [inventory](validation_readiness_20261101.json).
This is a source qualification audit, not a new model evaluation or a new gate.

## What was checked

Re-listed the accessible Huian Drive root and three recording subfolders:
13 root videos plus 8 + 8 + 8 videos in the existing subfolders, 37 files total.
No private Drive IDs, media URLs or pixels are persisted here. This inventory
is limited to these accessible project folders, not every possible recording.

For the two newer 8-file candidate collections, metadata was also requested
with SHA256/MD5 and media fields. The connector returned normalized size/type/time
metadata without checksums. No source SHA was recomputed from media bytes.
A matching size, title or date does not establish source identity or independence.

## Qualification result

| Collection alias | Files | Current use / eligibility |
| --- | ---: | --- |
| legacy_root | 13 | Historical training/replay inputs; not a newly certified blind batch |
| oct03_development | 8 | Tracked revealed development intake, overlapping first-hand clips; not 8 matches |
| oct09_candidate | 8 | Requires exact hashes, reviewed match grouping and complete reference exclusions |
| oct12_candidate | 8 | Existing revealed diagnostics and unresolved grouping; not a certified blind batch |

This audit certifies **zero new fresh original matches** for formal promotion.
That is a certification result, not a claim that no unused recording exists.
No model inference, truth freeze, accuracy, latency or promotion result was
produced. Current execution environment could not start the local process runner,
so raw-video decoding and focused Python checks were unavailable in this run.

## Existing evidence to reuse

- `references/vision/2026-09-23/continuous_video_source_intake_v0_1.json`:
  historical exact-byte differences and unresolved MOV/MP4 equivalence.
- `references/vision/2026-10-03/new_match_eight_segment_intake_v0_1.json`:
  original-match grouping, overlap and revealed development scope.
- `references/vision/2026-10-07/concealed_lineage_drive_hash_audit_v0_1.json`:
  six unresolved template source SHAs did not match the then-accessible 14 sources.
  This old byte-hash result is not a fresh hash of all 37 files.
- `docs/vision/new_recording_exact_frame_rereview_20261013.md`:
  explicit sequential frame/RGB hashes and a retained animation checkpoint;
  truth/burst stability remain unqualified in that historical record.
- `references/vision/2026-10-07/whole_hand_20260926_independent_match_diagnostic_v0_1.json`:
  product-path and exact-SHA-filtered developmental results. Exact-SHA exclusion
  alone does not establish original-match-disjoint training.

## Execution handoff within #7

First reuse revealed recordings for development regression without calling them
blind validation. For candidate media, verify raw bytes, original-match groups,
overlap/derivatives, and exclusion from every baseline and experimental reference
bank. Do not infer grouping from folder names or create a new independent group
for each segment.

Only then select an untouched holdout, freeze source/version/frame selection
before inference, review truth without prediction suggestions, and run the
existing frozen promotion contract. Preserve animation checkpoints as rejection/
recovery cases rather than replacing them with cleaner frames after inspection.
`independent_batch_lock.py` rejects known source tokens but its exact-SHA checks
alone do not prove original-match independence; review grouping first.

The Issue #7 numeric requirements (including >=8 source sessions and its Gold,
geometry, identity, draw/PublicState and stress coverage) are unchanged.
The new inventory is deliberately not a promotion_bundle: unknown metrics are
not populated with zero, and no independent_batch=true claim is fabricated.
Runtime threshold 0.82, V0.10 and Executor OFF remain fixed.
