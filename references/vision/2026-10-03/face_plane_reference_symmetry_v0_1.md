# Face-plane seams and reference preprocessing symmetry

Issue #69 / Draft PR #117, inspected development evidence. The actual detector
ROI path now retains S789 15/15 faces and 5/5 groups when references and queries
use the same existing single-face normalization. Reviewed boxes are used only
to associate the audit target, never to construct crop boundaries.

## Problem and controlled comparison

The detector boundary probe normalized each query before SIFT extraction, but
built both public and private reference descriptors from raw crops. This
asymmetry confounded earlier conclusions about boundary errors. The earlier
reports remain valid measurements of that asymmetric configuration, not proof
that its crop geometry alone caused the errors.

The new optional `--reference-geometry` ablation applies the same
`normalize_single_face` before extracting public/private reference descriptors.
It preserves reference images, SHA checks, same-original-match exclusions,
query processing, scoring and thresholds. Scoped callbacks are restored before
query evaluation. Nothing is changed in the runtime classifier.

## Geometry experiment

Within the detector-derived foreground envelope, find the pale face extent,
then find well-occupied blank bands near its top and lower region. Search for
dark seams near each nominal third in each band, requiring contrast and
rejecting search-edge minima. Extrapolate the measured seam slopes to form
three quadrilaterals. Compare bounding rectangles and perspective-rectified
faces separately. Equal thirds restrict search only; they are not accepted cuts.
This supports only flat, unrotated bottom groups. It is a limited developmental
candidate, not a general perspective or stacked-tile solution.

S789 has identical measured band rows `[443,490]` and seam positions
`[[49,91],[44,88]]` relative to its outer envelope across five frames.
Independent recording 14 has band rows around `[415/416,460]` and seams
`[[48/47,88/87],[40,81]]` across three frames. These are measured candidates,
not manually certified pixel-exact body labels.

## Results

S789 frames 4794/4797/4800/4803/4806, same frozen scoring function:

| Crop method | Raw references, normalized queries | Both sides normalized |
|---|---|---|
| Actual detector + seam context | 10/15 faces; 0/5 groups | 15/15; 5/5 |
| Tight face body, no seam context | 10/15; 0/5 | 15/15; 5/5 |
| Tight face body + seam context | 15/15; 5/5 | 15/15; 5/5 |
| Full foreground body + seam context | 14/15; 4/5 | 15/15; 5/5 |
| Measured seam bounding rectangles | 10/15; 0/5 | 15/15; 5/5 |
| Measured seam perspective rectification | 10/15; 0/5 | 15/15; 5/5 |

Symmetric results repeat identically. The existing S8 triplet control retains
15/15 faces and 5/5 groups in all six symmetric modes; it comes from the same
original match and is not independent identity validation. Independent recording
14 is a geometry check only: S2/S3 lack source-disjoint reference support.
Reviewed rectangle coverage includes background and cannot establish glyph loss.

Manual inspection of normalized S9 outputs shows crop-shape changes; the
asymmetric rectified frame 4797 scores S7 0.13750 vs S9 0.12818. The old tight
face candidate scores S9 0.12169 vs S7 0.09119. Scores are diagnostic development
rankings, not calibrated probabilities or runtime acceptance.

## Decision

Retain symmetric preprocessing for development comparisons. The seam method
has no measured identity advantage over the simpler detector crop under this
configuration, so do not add its complexity to runtime now. Do not claim the
entire localization problem is solved: contour truth, tilted/stacked layouts
and source-disjoint identity coverage remain unqualified.

Next qualify independent S2/S3 references from other original matches, then
compare the simpler detector path and measured seams with symmetric processing.
Keep revealed frames as regression evidence, not a new blind holdout.

## Reproduction and checks

Run `workspace.vision.evaluate_sift_detector_body_boundary_probe` once with
and once without `--reference-geometry`, using the SHA-pinned source and
confirmed private template ZIP. S8 control uses
`existing_video_meld_face_harvest_spec_v0_1.json`, source 1/group 0 via `evaluate`.
Run `workspace.vision.audit_independent_meld_crop_coverage` on original `14.mp4`.
Hashes, versions, seam coordinates and summaries are preserved in
`face_plane_reference_symmetry_result_v0_1.json`. Raw footage remains private.

19 focused tests passed, including sloping seams, coordinate translation,
missing-seam abstention, dark-base retention and existing probe checks.
The previous commit 8a8456d passed Tests, Vision Regression and Evidence
Contracts; that is not a claim about this revision's pending CI.

Development only; no formal promotion or runtime integration. Hint read-only,
Executor OFF; CurrentAgent V0.10 unchanged.
