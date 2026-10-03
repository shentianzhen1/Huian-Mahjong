# Existing-video face acquisition, 2026-10-03

Four readable player FLAT groups were located in two already supplied September
26 video chunks: Hand 3 North and bamboo-1, Hand 7 bamboo-8, Hand 8 Wan-9.
Each group has three manually selected rectangular face ROIs at five fixed
frames: 60 crops in four groups from one original match. These are assistant
visual labels, not new user-confirmed identities or automatic splitter evidence.
Some perspective margins contain tile thickness or a neighboring edge. Do not
promote these rectangles as precise face masks.

The intake pins the actual downloaded video SHA, frame index, decoded time,
image size, bbox and PNG hash. It does not claim that these bytes are identical
to earlier uploaded versions of similarly named recordings. Raw videos and
crop pixels remain private. The conservative match assignment excludes both
the legacy first-hand and eight-hand aliases; separate clips/hands/frames must
never create additional independent support. The intake is not automatically
loaded into the default template bank.

## Frozen-bank diagnostic

The existing public + verified private SIFT bank is unchanged. Harvested crops
are queries only, never references in their own evaluation. Both same-match
aliases and exact query SHA are excluded.

| Assistant-reviewed class | Faces | One-other-match true-class support | Matching Top1 |
|---|---:|---:|---:|
| North | 15 | 0 | not evaluated |
| Bamboo-1 | 15 | 0 | not evaluated |
| Bamboo-8 | 15 | 15 | 0 |
| Wan-9 | 15 | 0 | not evaluated |

Bamboo-8 instead ranks bamboo-4 eight times and bamboo-2 seven times. Its only
independent same-class reference comes from `reviewed_recording_66fe`. This
isolates a supported-class ranking failure in one inspected group; it does not
establish whether the cause is crop margins, scale/rendering or descriptor
discrimination. Five nearby frames and three faces are correlated observations,
not 15 independent events. Under the frozen two-other-match condition none of
the four true classes is scorable. No accuracy denominator mixes those unsupported
classes into the bamboo-8 diagnostic.

## Reproduction

```bash
python -m workspace.vision.harvest_reviewed_meld_faces \
  --spec references/vision/2026-10-03/existing_video_meld_face_harvest_spec_v0_1.json \
  --video-directory /path/to/private/videos \
  --output-zip /tmp/existing_video_meld_faces.zip \
  --output-report /tmp/intake.json
python -m workspace.vision.evaluate_existing_meld_intake \
  --intake-zip /tmp/existing_video_meld_faces.zip \
  --private-template-zip /path/to/verified/private/supplement.zip \
  --output /tmp/intake_rankings.json
```

### Correction: the bamboo-8 reference was mislabeled by location

The source-pixel review found that the old S7/S8/S9 template ROIs and their
parent calibration bbox pointed at the first P1 meld. The actual S789 is the
second exposed group. The v0.1 0/15 result above is preserved as a dated result
from a contaminated reference bank; its earlier interpretation as a supported
bamboo-class ranking failure is invalid. It does not justify changing features.

After correcting the three face ROIs and parent group bbox, the unchanged query
crops and scorer rank all 15 bamboo-8 faces as S8 in one-other-match mode.
Two-other-match coverage remains zero. This is one reviewed development group,
not 15 independent events or a generalization accuracy. The new report pins the
label/source/recovery file hashes so annotation changes are visible.

See `existing_meld_intake_corrected_s789_probe_v0_2.json` and
`s789_template_location_correction_v0_1.json` in the October 3 references.
All 21 public-meld template crops were visually rechecked after the fix; no
additional identity/location mismatch was apparent in that limited inventory.
This does not audit concealed, river, action or private-template inventories.

North/bamboo-1/Wan-9 are useful candidate
material for other-match experiments, pending the same lineage and crop review
required of existing templates. Do not search thresholds on these viewed crops.
Runtime identities remain UNKNOWN, Hint read-only, Executor off.

## Fixed-reference reverse direction and a second query group

The three already reviewed S8 faces at frame 1800 were locked as experimental
references before the reverse run. No frame or crop search occurred. The
reference intake metadata and crop hashes are pinned to the public intake
record; this does not promote these assistant-reviewed manual ROIs into the
default template bank. First-hand/eight-hand match aliases are collapsed.

Adding these three faces from one original match gives the corrected 66fe S8
query independent true-class support and a correct S8 Top1. Nine other public
faces with true-class support before and after remain 9/9 correct. Eleven
other public faces still lack true-class support; their winners are not counted
as correct or incorrect classification outcomes. These controls span previously
inspected material and do not constitute a blind holdout.

A separate inspected query from Hand 8 was then harvested at the same fixed
4794/4797/4800/4803/4806 frames used for its Wan-9 intake. The second group is
visibly S7/S8/S9. It is scored against the unchanged corrected public + verified
private bank, excluding the entire September 26 match. The Hand 7 experimental
S8 references are not used for this same-match query.

| Hand 8, one-other-match diagnostic | Result |
|---|---|
| S7 independent face ranking | 5/5 S7 |
| S8 independent face ranking | 5/5 S8 |
| S9 independent face ranking | 0/5 S9; all five rank S2 |
| Legal group ranking | 4/5 S789; last frame ranks S678 |
| Two-other-match true-class support | none |

The final wrong group has a raw top-two score gap of 0.00048522. None of these
scores is calibrated Runtime confidence. Ranking a legal group does not establish
identity: all outputs and actions remain UNKNOWN. The five frames belong to one
group in the same September 26 original match as Hand 7; they do not add another
independent source. The next targeted inspection is S9 versus S2, preserving
these fixed crops, bank, and scorer settings as the baseline.

Reproduce reverse direction with `workspace.vision.evaluate_bamboo8_reverse_probe`
using the original intake zip and verified private-template zip. Reproduce
the Hand 8 group with `hand8_s789_harvest_spec_v0_1.json` and
`workspace.vision.evaluate_existing_meld_intake --include-group-rankings`.
Reports: `bamboo8_fixed_reference_reverse_probe_v0_1.json`,
`hand8_s789_intake_v0_1.json`, and `hand8_s789_fixed_sift_probe_v0_1.json`.

## One fixed reference-descriptor deduplication experiment

The representative frame 4800 S9 query has 23 ratio-filtered matches to S2,
but only eight distinct template descriptor indices; ten matches reuse one
reference descriptor. Its S9 reference has nine matches to seven distinct
indices. The original matcher counts each query match independently. This can
inflate a wrong reference's score through many-to-one matches on repeated local
patterns; it does not by itself prove which matching geometry is correct.

One fixed variant was run: for each template descriptor index (`trainIdx`),
keep only the smallest matched distance before calculating the same score.
Feature extraction, crop pixels, bank, source exclusions, ratio threshold and
raw-fallback selection are unchanged. No alternative variants or threshold
search followed the results. The scorer callback is temporarily replaced only
inside this offline harness and restored even on exceptions; the frozen module
and default Runtime path are not modified.

| Inspected comparison | Frozen baseline | Deduplicated reference matches |
|---|---:|---:|
| Hand 8 S7 faces | 5/5 | 5/5 |
| Hand 8 S8 faces | 5/5 | 5/5 |
| Hand 8 S9 faces | 0/5 | 3/5 |
| Hand 8 legal group ranking | 4/5 | 5/5 |
| Earlier Hand 7 S8 faces | 15/15 | 15/15 |
| Reverse 66fe S8 query | 1/1 | 1/1 |
| Nine paired scorable public face controls | 9/9 | 9/9 |

The remaining two S9 errors become S7, not S2. A correct group ranking can mask
those wrong individual winners; both metrics must remain separate. Many frames
are correlated observations of the same groups, and unsupported classes still
have no accuracy denominator. These inspected development comparisons do not
establish general improvement, two-other-match readiness or Runtime confidence.
Different orientation descriptors at the same coordinates are still distinct;
no reciprocal matching or spatial-consistency check was implemented.

Reproduce with `workspace.vision.evaluate_sift_reference_dedup_probe`, supplying
`--hand8-intake-zip`, `--original-intake-zip`, `--private-template-zip`, and
`--output`. The pinned result is
`sift_reference_descriptor_dedup_probe_v0_1.json`. Keep this variant offline.

## Fixed 3x3 position mask: rejected as a general scorer

The two remaining S9-to-S7 errors at frames 4800/4806 have inconsistent match
positions. A single fixed spatial diagnostic attached normalized 3x3 cell IDs
to the unchanged SIFT descriptors, allowed matches only within the same cell,
and retained the reference-index deduplication. Both ratio matching and raw
fallback obey the mask. No grid-size, threshold, crop or bank search occurred.
This is coarse position masking, not a verified perspective transform or
geometric model fit.

| Inspected metric | Frozen | Reference dedup | Fixed 3x3 + dedup |
|---|---:|---:|---:|
| Hand 8 S7 faces | 5/5 | 5/5 | 5/5 |
| Hand 8 S8 faces | 5/5 | 5/5 | 5/5 |
| Hand 8 S9 faces | 0/5 | 3/5 | 5/5 |
| Hand 8 legal group ranking | 4/5 | 5/5 | 5/5 |
| Baseline-scorable public controls | 9/9 | 9/9 | 7/9 |

Both new control errors are P6 queries with independent true-class support:
`public_meld_p6` ranks P7 and `eight_hand_h7_p456_p6_2` ranks P8. Both remain
scorable; these are actual ranking regressions, not missing-class abstentions.
The controls come from different original recordings. Hand 7 S8 remains 15/15
and reverse S8 remains correct, but those successes do not cancel the P6 errors.

Decision: do not adopt the grid candidate. The frozen scorer and the separate
reference-dedup development variant remain unchanged; no bamboo-only Runtime
route is introduced without a validated suit decision. A target group's 5/5
does not establish generalization. All three modes use previously inspected
material and the one-other-match diagnostic. Next inspect crop alignment and
geometric correspondence on the fixed S9 and regressed P6 pairs before designing
another score change; do not keep searching grid parameters on these samples.

Reproduce with `workspace.vision.evaluate_sift_spatial_grid_probe` using the same
three private input ZIPs and `--output`. Result:
`sift_fixed_spatial_grid_probe_v0_1.json`. The report compares controls across
scoring modes, rather than incorrectly treating the grid variant's internal
before/after reference test as proof of no regressions. All patched descriptor
and scorer callbacks are restored; Runtime identities remain UNKNOWN.

## Boundary and correspondence audit without another score change

The fixed S9 and reciprocal P6 query/reference pairs were inspected against
their exact source/crop hashes. No apparent wrong-tile ROI was found and their
glyphs are readable, but precise face polygons, perspective corners and glyph
clipping have not been verified. The reused bright low-saturation mask is only
a description of neutral tile material; a mask touching an ROI edge does not
prove a clipped glyph or identify the actual face plane.

The audit reproduces the frozen descriptors exactly and separately exports
their normalized keypoint positions. Of 22/29 distinct reference matches in the
two P6 directions, only 5/7 occupy the same 3x3 cells. For S9 frame4800/4806,
the correct S9 reference has 7/5 distinct matches with 2/2 in the same cells;
the competing S7 has 9/9 with 3/3 in the same cells. These are local descriptor
matches, not verified correspondences between equivalent glyph parts. Repeated
circle/bamboo features can jump between different symbols even for a same-class
pair. This makes a rigid ROI grid an inadequate geometric verification method.
No global geometric model was fitted, so do not declare crop offset or perspective
the sole cause of the regressions.

Code-path inspection also separates two input policies: the SIFT bank cuts
public templates directly from manifest rectangles; the ordinary FLAT evaluator
normalizes a group and then splits its query faces. Their equivalence has not
been validated. The recent Hand 8 and public-control probes both use direct
rectangles, so that broader pipeline difference does not explain all errors in
these probes.

Next perform one fixed preprocessing comparison on both query and reference
inputs, with the S9/P6 controls preserved; require readable face boundaries
before trying perspective changes. Do not reuse a high group ranking, the bright
mask or a descriptor count as proof of correct segmentation. This audit changes
neither crop pixels nor scores. Result: `meld_crop_layout_pair_audit_v0_1.json`;
reproduce with `workspace.vision.audit_meld_crop_layout_pairs --hand8-intake-zip
/path/to/hand8.zip --output /tmp/layout_audit.json`. Raw private pixels stay private.
# Symmetric single-face geometry A/B (development only)

The fixed report `references/vision/2026-10-03/sift_symmetric_geometry_probe_v0_1.json`
compares direct rectangular faces with the existing bright-mask tight crop,
deskew and aspect-preserving height-96 normalization applied identically to
all query and public/private/experimental reference faces. It does not use the
query-only 12% identity inset, descriptor deduplication or spatial grid mask.
The SIFT extractor parameters, ratio threshold and scoring callback are unchanged.
The adapter uses geometry pixels only: the three-face group's stack classifier
is not applicable to these single faces and its output is never used.
Normalization failure returns no descriptors, never a raw-image fallback.

| Fixed development endpoint | Direct rectangle | Symmetric geometry |
| --- | --- | --- |
| Hand 8 S7 faces | 5/5 | 5/5 |
| Hand 8 S8 faces | 5/5 | 5/5 |
| Hand 8 S9 faces | 0/5 | 5/5 |
| Hand 8 legal S789 groups | 4/5 | 5/5 |
| Baseline-supported public controls (including both P6 faces) | 9/9 | 9/9 |
| Existing Hand 7 S8 forward queries | 15/15 | 15/15 |
| Fixed S8 experimental-reference reverse query | 1/1 | 1/1 |

All 303 transformation calls succeeded (calls include repeated queries and
bank builds, not 303 distinct faces). Controls retain their baseline denominator;
lost coverage would count as regression rather than disappearing from the report.
The two-other-original-match condition still supports zero Hand 8 faces. M9,
North and S1 from the existing intake remain unsupported; they are not counted
as either successful identities or retrieval errors.

Decision: retain this as a reproducible development candidate, not Runtime or
promotion evidence. This supports testing input-domain alignment without
changing the scorer, but does not isolate which component of the combined
transform caused improvement, prove a true face-plane boundary, or certify
that single-face normalization equals group-normalize-then-split processing.
All query clips remain one original match and have previously been inspected.
Next: compare this fixed adapter against the actual group-normalization and
face-split chain with source-locked boundary review, before any integration.
Runtime gate 0.82, Hint read-only and Executor OFF remain unchanged.

## Fixed Hand 8 actual group-normalize/split probe

`references/vision/2026-10-03/sift_group_split_geometry_probe_v0_1.json` now
runs the repository's real `normalize_public_meld_crop` → FLAT-only
`split_flat_meld_faces` chain on original source frames 4794, 4797, 4800,
4803 and 4806. The group ROI is fixed as the bounding union of the three
source/hash-pinned manual face ROIs; no per-frame crop search is performed.
All five groups return FLAT and three 72×96 faces. The subsequent per-face
identity geometry and unchanged frozen SIFT ranking produce 10/15 correct
faces and 0/5 exact S789 groups, versus 15/15 and 5/5 when the same faces are
individually cropped first and then normalized. Expected tile positions inherit
the previously inspected manual review, not user-confirmed truth; this is
development diagnosis, not accuracy evidence. The face-boundary splitter was
not independently visually qualified, and `UNKNOWN` remains appropriate for
Runtime.

A contact-sheet visual check shows all principal glyphs remain visible in the
automatic thirds; it does not certify precise tile-edge polygons. After width
alignment, mean direct-vs-group processed-pixel grayscale correlation is 0.749
for S7, 0.921 for S8 and 0.614 for S9 (S9 RGB MAE 20.75/255). Across all five
frames S9 is consistently ranked S7 after the group path, while direct crops
remain S9. These measurements localize a substantial S9 input-image change;
they do not prove whether the cause is crop boundary, resizing/interpolation,
or their interaction. No scorer or threshold changed.

The dependency-free coordinate audit
`references/vision/2026-10-03/hand8_split_boundary_overlap_audit_v0_1.json`
maps the already pinned manual ROIs into the recorded normalized group: x ranges
0–75, 72–146 and 141–216, versus current equal thirds 0–72, 72–144 and
144–216. Thus equal thirds omit 3, 2 and 3 normalized pixels from those
rectangles in every fixed frame. The manual rectangles overlap and are not
certified tile polygons; this establishes a reproducible geometric discrepancy,
not a corrected boundary or causal explanation. The v0.2 SIFT rerun below
evaluates these fixed boundaries without promoting them to an automatic splitter.

The v0.2 development rerun in
`references/vision/2026-10-03/sift_group_split_geometry_probe_v0_2.json`
uses OpenCV 5.0.0, NumPy 2.3.5 and Pillow 12.3.0. It compares the original
direct-face baseline against five controlled modes, all with the same frozen
SIFT scorer, template bank and original-match exclusion:

| Query preparation | Correct faces | Correct S789 groups | S9 top-1 in five frames |
| --- | ---: | ---: | --- |
| Pinned manual face ROI → single-face normalize | 15/15 | 5/5 | S9 ×5 |
| Raw group equal thirds → single-face normalize | 10/15 | 0/5 | S2 ×3, S7 ×2 |
| Normalize group → equal thirds → direct SIFT | 10/15 | 0/5 | S2 ×5 |
| Normalize group → equal thirds → single-face normalize | 10/15 | 0/5 | S7 ×5 |
| Normalize group → pinned manual rectangle → direct SIFT | 10/15 | 0/5 | S2 ×5 |
| Normalize group → pinned manual rectangle → single-face normalize | 10/15 | 0/5 | S7 ×5 |

The raw equal-thirds control shows that changing crop context/boundaries can
lose S9 ranking even before group normalization. Restoring the pinned manual
boundaries after group normalization does not recover S9. Skipping the second
normalization changes the wrong top-1 class, but does not recover S9 either.
Thus neither a boundary-only replacement nor skipping the second resize is a
passing fix on these fixed queries. The manual rectangles are previously
inspected development labels, not independently verified tile polygons; these
five frames are one original match and do not qualify as generalization or
Runtime promotion evidence. The CLI preserves the v0.1 report and refuses
to overwrite an existing output file.

An additional source-pixel audit in
`references/vision/2026-10-03/hand8_boundary_band_pixels_v0_1.json`
maps the equal-third boundaries back to the pinned raw crops. For each of the
five S9 frames, the reviewed rectangle adds raw x=336–337 beyond the equal
thirds. The omitted two-column band has 0 chromatic body pixels under the
declared RGB-channel-span >45 diagnostic (the first/last raster rows are
excluded as decorative edges). This does not show colored S9 glyph truncation,
but the OpenCV raw equal-thirds counterfactual above shows SIFT sensitivity to
this crop context. An independent original-match holdout remains required.

As an independent source-integrity check, FFmpeg decoded the locked original
video and all 15 SHA-pinned face rectangles compared pixel-for-pixel equal to
the private intake crops. See
`references/vision/2026-10-03/hand8_crop_source_pixel_verification_v0_1.json`
and `workspace/vision/verify_hand8_crop_source_pixels.py`. This rules out an
intake ZIP/source-frame mismatch for these queries; it does not resolve identity.

Decision: reject this group-crop/split candidate for these fixed Hand 8 queries.
This does not invalidate the separate symmetric single-face A/B, nor prove the
group normalizer generally wrong. Next assess a geometry-aware face extraction
or identity representation on independent original matches without tuning the
frozen scorer to these five inspected frames.
