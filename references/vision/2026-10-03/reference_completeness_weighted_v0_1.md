# Reference-completeness weighted SIFT candidate

Date: 2026-10-03  
Issue: #69  
Status: development-only; no Runtime promotion

## Why this slice exists

The current position-window + affine SIFT candidate reproduced the reviewed
independent `14.mp4` S234 packet at 7/9 faces and 1/3 exact groups. The two
remaining errors were both S2 ranked as S4.

A whole-hull diagnostic already showed that the false S4 fits used only part
of the S4 artwork, but a global hull threshold was not valid because sparse
S2 artwork naturally occupies a much smaller area.

This slice therefore measures a different quantity after the accepted affine:
**what fraction of the candidate reference keypoints are actually supported by
the query tile?**

## Reproducibility correction

SIFT behavior changed across OpenCV versions during this investigation.

A local OpenCV 4.13.0 rerun did not reproduce the frozen ranking packet and
was rejected for candidate evaluation. The result below was reproduced with:

- Python 3.13.5
- OpenCV 5.0.0
- NumPy 2.5.3
- CI-exported OpenCV wheel SHA256
  `ed709fdf9aa0bd1f2ed8549e71d19449b03a675bb581eb292285f6861953be37`
- CI-exported NumPy wheel SHA256
  `a5fa86b80fd24bcd1aff83ad23be44ea323de3f787be8f8b15d4a65621e25321`
- derived public spatial-reference NPZ SHA256
  `de55db970f7ebd4ca7a7bb8bcdf3f563273a4f68b6cc205b034f5fa801798ee3`

Under that frozen environment, the existing candidate reproduced exactly:
S234 7/9 and 1/3 groups; S789 15/15 and 5/5 groups; S8 PENG 15/15 and 5/5
groups.

## Diagnostic separation

For the two false S2 → S4 winners, the S4 reference keypoints supported by
the query were only:

- frame 2549: about 44.2%
- frame 2552: about 48.8%

The correct S2 candidates on those frames had about 84.3% and 86.3% reference
support. True S4 observations in the same sequence were about 94.2%–96.0%.

Across correct winners:

- S234 reviewed packet: minimum about 86.3%
- S789 control: minimum about 92.0%
- S8 PENG control: minimum about 91.0%

This supports the interpretation that the false S4 result is a partial dense
reference explanation, rather than whole-reference agreement.

## Candidate formula

One parameter-free reweighting was tried:

```
candidate_score =
    existing_spatial_window_affine_score
    * reference_keypoints_supported_by_query_fraction
```

No new acceptance threshold was selected. No exponent, class-specific rule,
S234-only restriction, or UNKNOWN override was searched.

All admitted competing classes remain in the ranking.

## Result on inspected development data

| Packet | Existing spatial candidate | Weighted candidate |
| --- | ---: | ---: |
| independent 14.mp4 S234 faces | 7/9 | **9/9** |
| independent 14.mp4 exact groups | 1/3 | **3/3** |
| S789 control faces | 15/15 | **15/15** |
| S789 exact groups | 5/5 | **5/5** |
| S8 PENG control faces | 15/15 | **15/15** |
| S8 PENG exact groups | 5/5 | **5/5** |

Wrong rankings and UNKNOWN are both zero for the weighted candidate in these
three inspected packets.

This is **not** a 100% accuracy claim. The formula was proposed after viewing
the development failures.

## Why this is not promoted

The candidate remains development-only because:

- the formula was selected after inspecting the S2/S4 failures;
- S2 and S3 currently have only one other original-match support;
- the S234 labels are assistant visual review, not user-confirmed;
- the S789 and S8 controls are from the same original match;
- no new source-disjoint unseen exposed-meld packet has tested this frozen
  formula.

The required next gate is therefore simple: freeze the formula unchanged and
evaluate it on a new source-disjoint real exposed-meld packet. Do not tune the
support radius or add a threshold after looking at that packet.

## Runtime boundary

Runtime identity threshold remains 0.82. This development score has no Runtime
probability meaning and is not wired into Runtime identity confidence.

CurrentAgent V0.10 is unchanged. Hint remains read-only. Executor remains OFF.
UNKNOWN continues to fail closed.
