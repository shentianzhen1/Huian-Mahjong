# New recording intake and exact-frame correction — 2026-10-13

Issue #69, frozen candidate `a2c83fd`. The previously inventoried two private
MOV files have now been downloaded and byte-hashed. They contain 4,116 and
3,468 reported frames, approximately 69.615 and 58.4 seconds. Their coded size
is 1290x2796 with 90-degree rotation; decoded display size is 2796x1290.

Neither full SHA appears in tracked references/dataset text, and neither
matches the existing Runtime dataset exclusion prefixes. This only establishes
absence of these exact file identities, not original-match independence.
The initial views show the same room/seats and seventh/eighth-hand sequence;
conservatively keep both files in one UNVERIFIED candidate cluster. Do not
count them as two independent matches or as the frozen eight-recording formal
batch. Private videos, frames, crop pixels, filenames and Drive IDs are not
published.

The 20/50/80 percent frame ordinals were recorded before detector/classifier
evaluation. Initial manual lists and frozen Runtime exports were attempted,
but are invalidated: two manual count entries need correction, and a frame
identity audit found that OpenCV's random frame seek returns different pixels
from sequential decoding at nominal ordinal 2774 on the second MOV. Single
random seek and the old burst centre agree with each other; both disagree with
the actual sequential ordinal. This is an offline frame-provenance defect,
not evidence of a classification regression or a geometry-cache failure.
No accuracy/complete-hand summary from those initial exports is valid.

## Exporter correction

`whole_hand_baseline_export.py` now advances sequentially from the beginning
instead of trusting `CAP_PROP_POS_FRAMES` random seek. An optional integer
`source_frame` selects the exact decoded ordinal. Legacy timestamps still use
seconds times average FPS; that approximation is explicitly recorded and must
not be interpreted as an exact VFR presentation timestamp.

A truth sample can bind `reviewed_frame_rgb_sha256` together with its explicit
`source_frame`. The exporter checks the decoded RGB hash before calling the
detector/classifier. A mismatch or missing explicit ordinal stops the export.
Decoded dimensions come from the actual image after orientation handling.
Sequential advancement may cost more for late-video samples; this is an
offline evidence tradeoff and does not change live capture latency.

Actual private execution confirms the new burst centre matches an independently
decoded sequential frame. Binding the earlier random-seek review hash correctly
fails. Regression tests cover a decoder whose random seek would return incorrect
pixels, explicit ordinal selection, decoded dimensions and review-hash mismatch.
The focused local suite passes all 15 tests.

Metadata-only evidence:

- `references/vision/2026-10-13/new_recording_review_selection_v0_1.json`
- `references/vision/2026-10-13/new_recording_vfr_frame_identity_audit_v0_1.json`

Next: re-review exact ordinal frames, bind their RGB identities, correct and lock
the whole-hand lists, and verify all five burst frames describe the same hand.
Review detector alignment/crop quality before scoring. Since initial predictions
have already been inspected, these recordings are revealed diagnostics and must
not be represented as untouched blind holdout evidence. Formal promotion still
requires sufficient independently grouped fresh material under Issue #7.

Runtime reader/classifier, threshold 0.82, Agent V0.10, read-only Hint and Executor
OFF are unchanged. PR #126 remains Draft and unmerged.
