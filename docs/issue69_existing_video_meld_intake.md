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
