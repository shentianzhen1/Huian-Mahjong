# Issue #69: private hand-1 public river identity review intake V0.1

**Development-only, machine-generated geometry candidates.** This stage creates
unlabeled private pixel crops for later independent human identity review. It does
not use frozen four-event action truth as labels, assign tile identities, or enable
the runtime classifier. No screenshots, video, or crop bytes enter public GitHub.

## Private local reproduction

Use only the SHA-matching first-hand recording. The hand-1 river manifest also
locks the reviewed **348–725** interval; no extrapolation to other recordings.

```bash
python -m workspace.vision.source_river_review_queue \
  --video /private/path/first-hand.mp4 \
  --manifest references/vision/2026-09-23/hand01_river_geometry.development.json \
  --first-frame 348 --last-frame 725 \
  --output-dir /private/path/hand01_unlabeled_review
```

The output directory must be outside the public checkout and empty. The CLI
creates review_queue.json and private cropped PNGs with SHA256 digests. Each
record starts with tile_id, turn_actor and action_kind null, review_status pending.
A geometry-only possible_repeat_of hint marks possible duplicates, without
deleting them or asserting physical tile identity.

## Actual private first-hand run

- 378 source-verified frames yielded **6 stable river candidate crops**: neither
  six approved identities nor six confirmed discards.
- Two candidates overlap strongly with earlier same-side crops after adjacent
  blob splitting. They are **possible repeats** pending human review.
- All 6 stay pending, tile/turn/action UNKNOWN. Original pixels and JSON are private.
- Existing real action replay remains **4 DISCARD-kind geometry candidates,
  4 strict abstentions, zero verified action positives**.
- Formal Vision promotion and Executor remain blocked.

## Next decision gate

A reviewer must verify crop identity and possible physical-tile repetitions
with source/frame provenance. Never import frozen event truth as classifier
predictions or treat this reviewed source as an independent holdout. Other
recordings need independently reviewed river zones and matching hashes.
