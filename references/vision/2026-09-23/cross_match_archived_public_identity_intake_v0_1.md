# Issue #69: separate-match, previously-inspected public-face intake

This is a **development data loop**, not formal Vision source-disjoint
validation. All 3 archived clips are in-app replays and were opened or studied
before this registry was created. The first two are different hands of one
recorded match. The third is a separate visually confirmed room/match but was
previously used in rule research and has just been sampled for development.
Never group by filename or SHA alone when claiming independent matches.

## Actual separate-match source intake

- A distinct archived replay (SHA256 `f24898ecee56803c09bead267150a590143c043941d3287f436ed6e89930f51d`), 1046×480, ~29 fps, 3102 frames. Different visible room from the first two hands. Original Google Drive link, room token and raw pixels stay private.
- The archived replay is an **8/8 hand in the replay UI**, with visible playback controls, overlay text and possible exposed melds. It is unsuitable for labeling every public shape as a discard or for assessing live-capture accuracy.
- Three manually verified **public face crops** were extracted from source frame 350 using explicit developer-review geometry. All three were SHA-qualified and match original decoded source pixels. This is not a machine detector benchmark.
- Private review suggestions: one upper face and two lower faces; proposed identities stay in the **private** review package. **3 proposed, 0 independently approved**. No tile identity enters runtime or action reconstruction.
- Prior first/second-hand samples are from one match; the new sample is from a second match, so this demonstrates cross-match *sample intake*, not a formally valid blind holdout or measured cross-match recognition rate.

## Public controls

`public_source_lineage.py`: requires explicit match-group IDs, verifies SHA and prevents same-video conflicting match assignments. `compare_sources` only returns true different-match development provenance when both bytes and match group differ. It **never** certifies a previously inspected source for formal promotion.

`source_public_review_samples.py`: SHA verification **before decode**, verified source frame bounds, exact resolution, private-directory-only PNG export with independent source-pixel roundtrip, no identities/turns/actions in the queue. Its manually reviewed bboxes are not machine geometry detections and are source scoped; no other recording can reuse them by default.

To reproduce privately, supply the matching archived replay file:

```bash
python -m workspace.vision.public_source_lineage --registry references/vision/2026-09-23/public_source_lineage.development.json
python -m workspace.vision.source_public_review_samples \
  --video /private/archived-replay.mp4 \
  --manifest references/vision/2026-09-23/archived_replay_cross_match_public_samples.development.json \
  --registry references/vision/2026-09-23/public_source_lineage.development.json \
  --output-dir /private/archived_public_samples
```

**Next gates:** obtain a genuinely new untouched live-capture match, register it
and lock SHA/sample frames using existing `independent_batch_lock.py` before
watching. Keep current source in development; collect independent reviewer
approvals for 12 earlier and 3 new proposed crops with repeat adjudication,
then freeze separate public-region metrics and an independent turn cue. Do not
change Rules, AI, Hint, Simulator or Executor; Executor stays OFF.
