# Frozen candidate on the newly reviewed match — 2026-10-13

Local checkpoint, pending explicit permission to export video-derived metadata.
No Runtime, threshold, AI, Hint or Executor code/dataset changed.

The user confirms the eight uploaded segments are one complete eight-hand match.
Independence from all previous development/training matches remains unverified.
The third-hand segment has no black band at ordinal 2148 but has one at its
later preselected 5370/8592 checkpoints; classify visibility by frame, not by
hand number. These recordings are revealed development diagnostics.

## Candidate restoration

- Sep-26 support video SHA matches frozen `05ef070e...` exactly.
- Historical `reviewed_tile_intake._read_frame` random-seek recipe reproduces
  all ten crop file hashes exactly. Sequential decoding initially reproduced
  only three, so the historical frame numbers are not silently reinterpreted
  as exact decoded ordinals. New query frames use sequential decoding and
  reviewed RGB-hash binding, not that historical support recipe.
- Frozen installer artifact 11760039064 ZIP digest matches
  `4fed2dc35f83611a5860c2487bf6cf338a9df67fec3da6522cdce2ac925ed28a`.
- Extracted bank has 147 approved labels; candidate is this bank plus only the
  ten hash-pinned Sep-26 crops/staging rows. No new-match query crop is support.
- Same primary-first UNKNOWN-only tight fallback policy; threshold 0.82 and
  source-support identity gates unchanged. Accepted primary identities cannot
  be overridden. No post-result tuning.

## Results

| Query batch | Tiles | Baseline correct accepted | Candidate correct accepted | Wrong accepted | Candidate UNKNOWN | Complete hands |
| --- | --- | --- | --- | --- | --- | --- |
| Hand 3, ordinal 2148, no band | 17 | 8 | 11 | 0 | 6 | 0/1 |
| Hand 7, three reviewed positions | 43 | 10 | 12 | 0 | 31 | 0/3 |

Hand 3 primary candidate accepts nine; eight fallback attempts add two correct
accepts (S4 and M2). M1 is newly accepted on the primary path. Remaining UNKNOWN:
S1, M4, M5 twice, M7, M9. M7 is a correct high-confidence candidate rejected by
the source-support gate; other remaining outputs fail confidence.

This is not an isolated causal experiment on black-band effects: the two hands
also differ in tiles, context, animation and state. The no-band complete-face
crops show classifier/support gaps even without the band. The seven-hand query
retains earlier animation/raised-selection annotations and truncated crops.
Count alignment does not mean advice eligibility. Four sampled hands remain
incomplete; the historical 43/43 Oct-3 result has not generalized to this batch.

Next: inspect winning template/source examples for S1 and Wan-class errors,
continue predeclared whole-hand sampling without using these query crops as
support, and treat occluded-body recovery as a separate development experiment.
No formal source-disjoint promotion, Windows live acceptance, public danger or
shanten readiness is claimed.
