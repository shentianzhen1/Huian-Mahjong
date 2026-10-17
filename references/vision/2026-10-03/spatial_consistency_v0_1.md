# Position-aware SIFT development experiment

The independent `14.mp4` S234 detector evaluation still ranked only 3/9 faces correctly after symmetric preprocessing, source-disjoint references and full-face rectification. This experiment changes the offline scorer while keeping those inputs and crop methods fixed. It compares every admitted competing tile class; expected labels do not restrict candidate classes.

## Results

Full-face rectified crops, three frames (2549, 2552, 2555):

| Scorer | Correct faces | Wrong rankings | No ranking | Exact groups |
| --- | ---: | ---: | ---: | ---: |
| Frozen baseline | 3/9 | 6 | 0 | 0/3 |
| Affine consistency | 4/9 | 1 | 4 | 0/3 |
| Position window + affine consistency | 7/9 | 2 | 0 | 1/3 |

The position-window report reproduced exactly. Frozen control rankings and scores remained unchanged. S3 and S4 ranked correctly in all three frames; S2 still ranked as S4 in frames 2549 and 2552. Frame 2555 was the sole exact group. These are offline top-ranked identities, not calibrated Runtime acceptance.

The position-window candidate retained 15/15 faces and 5/5 groups on both S789 and S8 controls across all seven crop methods. Both controls come from the same original query match and do not provide independent-match generalization evidence. Affine consistency without the position window produced abstentions on several S789 crop methods, so that candidate is not suitable for broad adoption.

## Method and fixed development parameters

Descriptor extraction is byte-identical to the frozen extractor; keypoint coordinates are retained in normalized image coordinates. The window candidate searches reference features within distance 0.20 before applying the existing descriptor ratio test. Matches are deduplicated by query/reference positions rounded to two decimal places. Affine RANSAC uses seed 69, residual threshold 0.04, 2000 iterations and confidence 0.99. It requires four inliers, positive determinant, singular values within [0.65, 1.50], translation within 0.20 and query/reference convex-hull areas of at least 0.01. Rejection returns zero with an audit reason, without a raw-match fallback. The score combines inlier count, descriptor count, spatial coverage and mean descriptor distance.

These parameters and the preferred crop method were selected after inspecting development samples. This is not a blind holdout. The candidate preserves all supported competing classes and reports abstention separately from wrong ranking.

## Evidence, validation and limits

Detailed scores, spatial audits, input hashes and all crop-method summaries are in `spatial_consistency_result_v0_1.json`. The bottom S234 reference source and pinned crop hashes were verified; its labels were reviewed visually by the assistant, not confirmed by the user. S2/S3 have support from only one other original match, below the formal two-other-match qualification requirement.

38 focused tests passed, including byte-identical extraction, coherent affine alignment, reflection rejection, repeated-position rejection and spatially nearby matches beating distant descriptor distractors. The frozen control was rerun and retained its prior scores and rankings.

Use the existing evaluator CLI with `--reference-geometry` and `--score-policy frozen`, `spatial_affine` or `spatial_window_affine`; the independent S234 evaluation additionally uses the independent14 specification, the pinned bottom-reference video and `--bottom-reference-rectified`. The default scorer remains frozen. Private raw media and intermediate crops are not published.

Retain the window scorer as a development candidate only. Remaining S2-to-S4 errors block adoption. A plausible next hypothesis is that a partial motif alignment can still fit S2 to part of S4; the next experiment should inspect unmatched motifs and whole-face layout, without forcing S234 labels or lowering acceptance thresholds. This experiment does not establish that hypothesis as the cause.

Runtime and its 0.82 identity gate remain unchanged. CurrentAgent V0.10 is unchanged; Hint is read-only and Executor remains OFF. No formal promotion or merge is implied.
