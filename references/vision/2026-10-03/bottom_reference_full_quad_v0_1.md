# Same-view S234 reference and full-face quadrilateral experiment

Issue #69 / Draft PR #117, revealed development evidence. Found and pinned a
bottom-seat S234 reference in existing footage. Neither adding that reference
nor rectifying both sides restores independent S234 identity retrieval.

## New reference

Original third recording `ScreenRecording_09-26-2026 22-30-33_1.mp4`:
SHA `4ffc9187a08df3d11df34a8a0c087b31172cf39104920cc0e9ebd5f2e72780c4`,
30 fps, 6194 frames. An eight-second coarse scan yielded 48 bottom-group
candidates. Visual inspection found the S234 group; frame 1920 was selected
and source/crop hashes pinned before scoring it against recording 14.
The detector ROI is `[395,429,133,78]` (xywh). All three crops are recomputed
from detector geometry and verified against PNG hashes in
`bottom_s234_reference_pin_v0_1.json`. Raw source and crop bytes remain private.

Labels are assistant visual review, not user confirmation. Same dated recording
chunks count as the single conservative September 26 original match. This
provides one other original-match reference for recording 14, not a formal
two-other-match qualification. It must be excluded from related S789 queries.

## Geometry ablation

The older quadrilateral method varied internal seams but kept the two outer
edges vertical. The new `face_plane_full_rectified` candidate measures both
outer light-face edges at blank face bands and extrapolates all four vertical
boundaries. It still assumes horizontal top/bottom bands and flat unrotated
groups; this is not a general perspective estimator or pixel-certified geometry.

The foreground outer-envelope probe abstains on this reference because its
component touches the search boundary near neighboring tiles. The new candidate
explicitly seeds from the existing detector light-face body instead, on both
reference and query. This is a named alternative, not a silent successful
fallback from the failed physical-body contour probe.

References are tested as (a) existing body-context crops and (b) full face
quadrilateral rectification. Queries retain all earlier crop controls plus the
new full quadrilateral mode. The frozen SIFT scorer and thresholds are unchanged.

## Result

Recording 14 frames 2549/2552/2555, all three expected classes supported:

| Configuration | Correct faces | Exact groups |
|---|---:|---:|
| Same-view reference, detector query crop | 3/9 | 0/3 |
| Rectified reference, detector query crop | 3/9 | 0/3 |
| Both sides use full-face quadrilaterals | 3/9 | 0/3 |

The rectified comparison repeats the same summaries. S4 remains correct;
S2/S3 remain wrong. The related S789 exclusion control admits zero new reference
faces and remains 15/15, 5/5 across all seven crop modes.

## Local matcher diagnostic

On frame 2552's detector-cropped S2, the rectified-reference configuration gives:

| Best reference class | Accepted local matches | Distinct reference descriptor indices | Reused matches |
|---|---:|---:|---:|
| Correct S2 | 3 | 2 | 1 |
| Winning incorrect S5 | 20 | 11 | 9 |

The scorer aggregates local match count and distance; it permits many query
features to reuse a reference feature and does not validate their global spatial
layout. The full-quad S2 query still favors S5 (12 matches, 9 distinct indices)
over S2 (8 matches, 6 distinct). Reuse is an observed contributor to the counts,
not a proof that eliminating reuse alone will fix recognition. Pose, photometric
differences and reference variety remain possible factors.

## Decision and next experiment

Keep the new source/pixel-qualified reference as a development asset. Reject
both same-view reference addition and this quadrilateral correction as complete
identity fixes. Do not keep tuning crop padding on these revealed frames.

Next compare the frozen local matcher with a separate spatial-consistency
candidate that retains keypoint positions and checks agreement across the face.
Report all competing classes and original-match exclusions. Global arrangement
must be tested, not inferred from a few matching bamboo strokes. Do not force
the expected S234 legal group or change Runtime confidence thresholds.

## Reproduction and validation

The detector boundary probe accepts `--bottom-reference-video` and optionally
`--bottom-reference-rectified`, alongside the independent14 spec and
`--reference-geometry`. The reference loader verifies source SHA, exact frame,
detector ROI, crop edges and PNG hashes. `sift_match_multiplicity_probe` reports
match reuse without changing scores. Numeric evidence and versions are in
`bottom_reference_full_quad_result_v0_1.json`.

33 focused tests passed, including sloping outer-edge geometry, wrong-source
rejection, duplicate-match diagnostics and existing source-exclusion, geometry,
private-loader and scorer tests. Preceding commit 9e47022 passed Tests, Vision
Regression and Evidence Contracts; this is not the new commit's CI status.

Development only; formal promotion false; runtime integration false.
Hint read-only, Executor OFF, CurrentAgent V0.10 unchanged.
