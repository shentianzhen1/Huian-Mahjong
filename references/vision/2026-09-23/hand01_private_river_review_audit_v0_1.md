# Issue #69: private river identity review integrity gate V0.1

**Status:** 2026-09-23; development-only; does not enable runtime tile identity.

This narrow slice follows PR #101. It validates a **separate, private** review
sheet against the SHA-locked unlabeled crop queue, original video, approved
source frame span, reviewed river zones, crop hashes **and source pixels**. It
never opens frozen four-action truth, supplies a player turn, creates an action
prediction or forwards labels to the current detector/assembler.

## Separate review states

- `pending`: not reviewed; tile and repeat unknown.
- `proposed`: tentative visual reading (including an AI-assisted draft); **zero
  approved evidence**. `reviewer` stays null.
- `approved`: requires an explicit separate reviewer, a valid one-of-34 project
  tile ID and source-frame evidence. A proposed duplicate must cite **both**
  source frames, link only to a prior same-actor candidate, and agree with an
  individually approved unique anchor. The software enforces metadata and
  pixels, not the reviewer's real-world identity or subjective accuracy.
- `rejected`: no approved identity.

`same_physical_tile_as` is only an adjudicated repeat decision. The geometry
queue's `possible_repeat_of` remains a hint, not a ground-truth relationship.
Only original video decoding + byte-identical cropped pixels can pass the
source-pixel check. If optional pixel verification is disabled for a synthetic
core-unit test, approved totals are forced to **zero**.

## Private reproduction

All of these files remain outside the public checkout. Run against your own
source-matching local recording and private review directory:

```bash
python -m workspace.vision.source_river_review_audit \
  --video /private/hand01.mp4 \
  --manifest references/vision/2026-09-23/hand01_river_geometry.development.json \
  --queue /private/review_queue.json \
  --decisions /private/decisions.proposed.private.json
```

The private decisions sheet has the schema
`source_river_review_decisions_v0_1`, the exact SHA256 of the complete
`review_queue.json` bytes, the queue's exact source session and SHA256,
`review_kind=development_visual_review`,
`excluded_from_formal_promotion=true`, and a `decisions` array. Each row has
`review_id`, `status`, `tile_id`, optional `same_physical_tile_as`,
`evidence_frames` and `reviewer`. No turn, action or frozen-event fields are
allowed. A new queue export requires a **new** decisions hash; never silently
reuse labels across source revisions.

## Actual private development pass (no private assets in Git)

The six PR #101 candidate PNGs were compared pixel-by-pixel to their decoded
source video frames after SHA verification. All six matched. A **private,
AI-assisted proposed** visual sheet was created for later separate human
adjudication; two same-side pairs are only *proposed* repeats. The audit reports:

- 6 source-pixel-verified candidates;
- 6 proposed, **0 approved** and **0 validated unique physical tiles**;
- 0 generated action predictions; tile/turn stay UNKNOWN in runtime;
- formal promotion and Executor remain blocked.

These already-reviewed old frames are development data and **cannot** serve as
a source-disjoint holdout. Human source-frame review, then additional independently
reviewed recording(s), are necessary before building/publicizing any public-tile
identity classifier or claiming a recognition accuracy.
