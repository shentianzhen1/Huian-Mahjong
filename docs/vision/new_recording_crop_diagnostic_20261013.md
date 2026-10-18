# Seventh-hand crop diagnostic — 2026-10-13

Private sequential source and three five-frame windows are documented in
`new_recording_exact_frame_rereview_20261013.md`. The user now confirms all eight
segments in the upload folder belong to one complete eight-hand match. This
does not establish separation from earlier training/development matches.

Before inference, the exact-frame truth was locked locally with SHA256
`5014d63779e9118a833b0107c2595f640545fefcb2877f4737ba9eafae44fbe9`.
All fifteen hand-region views and all 43 primary classification crops were
actually inspected. The PENG animation at ordinal 1734 and raised selection
at 2774 remain explicit visual-state annotations, not silent exclusions.

## Current committed dataset baseline

| Ordinal | Hand / draw truth | Correct accepted | Wrong accepted | UNKNOWN |
| --- | --- | --- | --- | --- |
| 693 | 16 / 1 | 5 | 0 | 12 |
| 1734 | 13 / 0 | 2 | 0 | 11 |
| 2774 | 13 / 0 | 3 | 0 | 10 |
| Total | 43 tiles | 10 | 0 | 33 |

All three automatic count alignments match truth. This does not establish
complete tile-body geometry or advice eligibility. Zero of three hands have
complete accepted identities. Raw Top1 is 35/43; all eight raw errors are
rejected. These are revealed, assistant-reviewed development checkpoints from
one segment, not independent accuracy or formal promotion evidence.

The 33 UNKNOWN outputs separate into:
- 26 below the unchanged 0.82 confidence threshold;
- seven correct raw identities above threshold rejected by existing regional
  cross-session source-support validation (SOUTH once, M7 twice, M8 four times).
  Session support is the existing gate's name, not proof of original-match
  independence.

## Crop defect and limits

The downloaded segment decodes with a black horizontal band across the lower
tile faces. The user reports no system line in the original video. Its origin
is unresolved; the previous system-home-indicator attribution is withdrawn.
Independent FFmpeg CLI decoding of ordinal 693 is pixel-identical to OpenCV
(mean absolute RGB difference zero), and shows the same band. This rules out
the contact-sheet generator and OpenCV-only drawing as its source for this
downloaded file, but does not prove what generated it before upload.
Thirteen actual primary crops have visibly truncated lower bodies: five at
693 and four at each later checkpoint. Their detector heights are 137–143
pixels, versus 161–170 pixels on the corresponding intact/raised components.
The band also visibly occludes portions of some longer crops.

Code inspection shows `classification_crop_bbox` pads downward by 5% of the
detected component height. Thus a shortened bright component is not recovered
to the full tile body by that padding. This identifies incomplete crop inputs in addition to classifier/source-support
limitations. The association with the band is a causal hypothesis, not yet an
isolated detector experiment. It does not prove
that every raw confusion is caused solely by the overlay or authorize removing
the support gate. Never invent glyph pixels under the bar.

Next experiment must preserve primary accepts, use a class-agnostic body-boundary
proposal, record occlusion, and compare the same locked frames with unchanged
support and 0.82. A larger crop must be independently reviewed for neighboring
tile contamination before interpreting recognition metrics. The historical
ten-asset Sep-26 candidate dataset has not been rebuilt in this session; this
baseline must not be called an A/B against the reproduced 43/43 candidate.

Runtime/Hint/AI/Executor code and production dataset are unchanged. No private
pixels are included. This note is local pending explicit approval to export
private-video-derived metadata to GitHub.
