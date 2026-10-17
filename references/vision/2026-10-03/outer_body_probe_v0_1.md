# Detector-to-outer-body development probe

Interpretation update: the identity comparisons below used normalized queries
against a raw-extraction reference bank. The subsequent
`face_plane_reference_symmetry_v0_1.md` ablation removes that asymmetry and
restores all six crop modes to 15/15 faces, 5/5 groups on S789. Preserve the
historical measurements, but do not attribute their failures solely to geometry
or treat direct outer-envelope cropping as intrinsically rejected.

This is an inspected development experiment for Issue #69 / Draft PR #117.
It rejects direct equal-third identity cropping from the new outer envelope.
No runtime observer or classifier threshold is changed.

## Method

Use the actual bottom-group detector ROI, expand the search by 10% per axis,
estimate table RGB from a three-pixel rim, and close a foreground mask whose
Euclidean RGB distance from the table exceeds 30. Require one contour with
substantial detector overlap and abstain when it touches the search boundary.
The adapter also retains the existing flat/unrotated restriction. Split the
envelope into equal thirds with two pixels of interior seam context.

Reviewed rectangles select the audit target only. They do not construct these
crop edges. Parameters are development choices, not independently validated.
Foreground can include bases and shadows: this is not pixel-exact body truth.

## Results

Frozen source-disjoint reference filtering and scorer, S789 frames
4794/4797/4800/4803/4806 from the SHA-pinned September 26 recording:

| Candidate | Correct faces | Exact groups |
|---|---:|---:|
| Raw detector + seam context | 10/15 | 0/5 |
| Tight light-face body + vertical/seam context | 15/15 | 5/5 |
| Foreground outer envelope + seam context | 14/15 | 4/5 |

The outer envelope is `[248,442,384,509]` in xyxy coordinates in all five
frames. Frame 4797 still ranks S9 as S7. Two runs produced identical reports;
OpenCV 5.0.0 and NumPy 2.5.3 also reproduce the older candidate controls.

Independent recording 14, frames 2549/2552/2555, has stable outer envelope
`[98,414,232,476]` (xyxy). Reviewed equal-third rectangle coverage is
0.875897/0.917133/0.917607. This is only a rectangle proxy: its reference
contains background, so low coverage alone does not demonstrate lost glyphs.
S2/S3 lack source-disjoint reference support; no independent identity accuracy
is asserted. The outer envelope is not certified against manual contour labels.

## Decision and next experiment

Keep complete physical-body geometry separate from identity-face geometry.
Do not replace the successful face crop with the outer-envelope equal-thirds
candidate. Next locate the visible face plane and actual internal separators
inside the detector-derived envelope; evaluate geometry and identity separately
with the same frozen scorer, then qualify new source-disjoint references.
Do not tune on these frames and call them a blind holdout.

## Reproduction

Run `workspace.vision.evaluate_sift_detector_body_boundary_probe` with the
source recording and private confirmed-template ZIP, and
`workspace.vision.audit_independent_meld_crop_coverage` with original `14.mp4`.
Both verify source SHA. Numeric evidence, hashes and dependency versions are in
`outer_body_probe_result_v0_1.json`. Private footage remains excluded.

Focused verification: 13 tests passed across the outer-body, detector body
context, independent rectangle coverage and two group-split probe test files.
These include translation, dark-base retention, empty foreground and clipped
search abstention; they do not establish real-video generalization.

Development only; formal promotion false; runtime integration false;
Hint read-only; Executor OFF.
