# S2 → S4 partial-pattern diagnostic (development only)

Date: 2026-10-03  
Issue: #69  
Base HEAD before this diagnostic: `93ef716706b9ec808b2d627b65c7ccabb4faf2ab`

## Question

The current position-aware SIFT candidate improves the independent `14.mp4`
S2/S3/S4 row from 3/9 to 7/9 faces, but frames 2549 and 2552 still rank
the reviewed S2 face as S4.

The narrow hypothesis tested here is:

> the S2 query can be explained by only a subset of S4 artwork, while the
> scorer does not require the match to account for the complete S4 reference
> pattern.

This is a diagnostic experiment only. No Runtime score, threshold, class set,
Hint gate, or Executor behavior changes.

## Inputs

- Independent query source SHA:
  `f24898ecee56803c09bead267150a590143c043941d3287f436ed6e89930f51d`
- Bottom S234 development reference source SHA:
  `4ffc9187a08df3d11df34a8a0c087b31172cf39104920cc0e9ebd5f2e72780c4`
- Private template ZIP SHA:
  `e1dcede193c7e7d3f0c241ee9110bb0c8decd9048be372e5e1e25dbf0623d83c`
- Existing committed ranking:
  `spatial_consistency_result_v0_1.json`
- Query spec:
  `independent14_s234_detector_spec_v0_1.json`
- Bottom reference pin:
  `bottom_s234_reference_pin_v0_1.json`

Full query/reference keypoint hulls were re-extracted from the exact source
frames using the same full face-plane rectification, symmetric single-face
normalization and frozen SIFT constants. Existing inlier hull areas and
rankings come from the committed position-aware result.

## Result

For the two remaining S2 → S4 errors:

| Frame | Winner | query inlier / whole query hull | S4 reference inlier / whole S4 hull |
|---:|---|---:|---:|
| 2549 | S4 | 33.8% | 31.2% |
| 2552 | S4 | 34.2% | 28.5% |

Directly comparable true S4 observations use much more of the whole pattern:

| Frame | query coverage | reference coverage |
|---:|---:|---:|
| 2552 | 63.0% | 71.9% |
| 2555 | 76.1% | 76.6% |

Frame 2549's true S4 query coverage is 77.4%, but its committed winning S4
reference came from a different source-disjoint template, so no cross-reference
fraction is asserted for that row.

This supports the partial-pattern hypothesis: the false S4 winner is based on
a substantially smaller portion of the complete S4 pattern than true S4
matches in the same sequence.

## Important negative result

Do **not** turn the above into a global minimum hull-coverage threshold.

True S2 is itself sparse. Its successful/expected query coverage in the same
three frames is only about 14.6%–19.2%. A class-agnostic rule such as
"require 50% whole-face coverage" would remove the false S4 but would also
reject correct S2 evidence.

Therefore this slice does not introduce a new acceptance gate.

## Fair score comparison

Independent `14.mp4` S234:

- frozen scorer: 3/9 correct, 6 wrong, 0 UNKNOWN, 0/3 exact groups;
- current local-window + affine candidate: 7/9 correct, 2 wrong, 0 UNKNOWN,
  1/3 exact groups.

Controls retained from the same frozen comparison packet:

- S789: 15/15 correct, 0 wrong, 0 UNKNOWN, 5/5 exact groups;
- S8 PENG control: 15/15 correct, 0 wrong, 0 UNKNOWN, 5/5 exact groups.

Those controls come from the same original match and are not independent
generalization evidence.

## Code change in this slice

`sift_spatial_consistency_probe.py` now records, for successful affine
matches:

- whole query/reference keypoint hull area;
- inlier hull fraction of the whole pattern;
- inlier keypoint fraction;
- occupied 3×3 grid cells;
- unmatched grid cells.

These fields are audit-only. The descriptor extraction and score formula are
unchanged.

## Next smallest experiment

Test a **bidirectional/reference-completeness diagnostic** after affine
alignment: measure whether the candidate reference contains substantial
unexplained keypoint regions after mapping into the query.

Do not restrict ranking to S2/S3/S4. Do not choose a threshold from these three
reviewed frames. First measure the diagnostic on all currently ranked classes
and rerun the S789 and S8 controls.

## Evidence boundary

- The candidate was chosen after viewing development samples.
- 7/9 is not blind accuracy.
- S2/S3 currently have only one other original-match source.
- S234 reference labels are assistant visual review, not user confirmation.
- Runtime threshold remains 0.82.
- Runtime/Hint/Executor remain unchanged; UNKNOWN stays fail-closed.
