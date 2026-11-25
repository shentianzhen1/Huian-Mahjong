# Long-video geometry recovery audit — 2026-10-25

Replayed the SHA-locked October 12 recording sequentially at development head
`942a73084af8e26e4ac9e4960b07aabd544b7ffd`. All 2,847 frames decoded;
every sixth decoded ordinal contributes to overlapping three-frame bursts.
The existing explicit `edge_seams=True` candidate was used. No algorithm,
threshold, template, source qualification or live behavior changed.

473 windows reproduce the earlier geometry result: 359 trusted, 114 rejected.
32 rejected runs are followed by trusted geometry. From the first rejected
burst endpoint to the next trusted endpoint, the median is 0.5 seconds and
maximum 1.4 seconds at nominal 30 fps. This includes initial acquisition and
is not a count of recovered advice. The terminal rejection at endpoints
2832–2844 has no observed recovery.

Selected full frames and detector boxes were visually reviewed. Around
84–108, 228–252 and 1776–1800, a raised discard, departing tile and moving
hand change observed region counts within a burst. Around 306–318 the flower
replacement changes the draw region. Conservative cross-frame rejection is
appropriate for these transitions; no count gate should be relaxed from this
evidence. Not all 114 rejected windows received visual ground truth.

The screenshot's earlier “two blocked windows” has no exact frame mapping in
this audit. Do not claim these long-video examples identify those two windows.
Do not equate geometry recovery with complete-hand recognition, source-qualified
Gold acceptance, or displayed advice recovery. End-to-end advice recovery and
Windows capture latency require separate measurements under Issue #45.

Metadata, source and pixel hashes, observation counts, all run boundaries and
selected rejection examples are in
`references/vision/2026-10-25/geometry_recovery_audit.development.json`.
This is one already revealed development recording, not independent promotion
evidence. No private pixels are added. AI V0.10, 0.82, read-only Hint and
Executor OFF remain unchanged.
