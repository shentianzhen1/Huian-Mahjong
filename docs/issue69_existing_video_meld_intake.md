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
