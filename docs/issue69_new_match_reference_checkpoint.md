# New-match reference development checkpoint — 2026-10-04

The owner's new eight-hand recording supplies one additional original match,
not eight independent sources. The frozen samples are development references
with assistant visual labels, not owner adjudication or blind promotion data.
Runtime identity remains UNKNOWN and the 0.82 gate is unchanged; Executor is off.

## Fixed-reference transfer

The first experiment freezes 12 faces from the first previously pinned P1, N,
S1-containing, and S8-containing groups. Queries are 75 previously reviewed
manual crops from the older eight-hand recording. All query crops are SHA
verified; query-match aliases are collapsed and excluded. References and
queries use the same existing single-face normalization and frozen SIFT scorer.

| Old query class | One-other-match ranking after adding references | Two-other-match support |
| --- | --- | --- |
| N | 5/15 correct | Still unavailable |
| S1 | 15/15 correct | Still unavailable |
| S8 | 20/20 correct | 20/20 scorable and correct |
| S7, S9 | 5/5 each correct | 5/5 each scorable and correct |
| M9 | Unavailable in the 12-face experiment | Still unavailable |

The S789 query contains five correlated group frames, not five matches.
Existing public controls have no baseline-correct identity regressions in
either support mode. This does not establish automatic crop accuracy, a
calibrated probability, complete public-state readiness, or Runtime acceptance.

- [12-face reference pin](../references/vision/2026-10-04/new_match_fixed_reference_candidate_pin_v0_1.json)
- [Baseline versus 12-face transfer report](../references/vision/2026-10-04/new_match_fixed_reference_transfer_v0_1.json)

## M9 geometry and identity are separate

The generic detector misses the leftmost opponent M9 group in three reviewed
samples (73, 74, 75 seconds of segment04). At 74 seconds, its center falls below
the existing upper-group x guard and the whole group becomes a single-face
candidate. At 73 and 75 seconds, a brightness connection to an enlarged central
tile produces a merged component instead.

`public_meld_top_row_peer_probe.py` is an optional offline experiment. Two
existing upper-group peers define a shared body band. Within that band it
requires compatible dimensions, nearby spacing, and no duplicate existing
group. Without two suitable peers it abstains. It does not replace the generic
detector and has no Runtime caller.

On these three samples it recovers bbox `[479,12,70,31]` and nine visible crops
without a manual crop boundary. The three timestamps are inspected development
checks; pixel-exact polygons and other layouts remain unverified.

Freezing three M9 faces from 73 seconds adds class support for the old M9 queries
but gives **0/15 correct identities**: 12 rank as M4 and 3 as M6. The 15-face
reference experiment retains the S1/S8 results and adds no public-control
regressions. M9 and N identity remain blockers; do not promote these references
or the geometry probe on the basis of source support alone.

- [Geometry report](../references/vision/2026-10-04/new_match_m9_row_peer_geometry_v0_1.json)
- [15-face reference pin](../references/vision/2026-10-04/new_match_fixed_reference_candidate_pin_v0_2.json)
- [12 versus 15 reference transfer report](../references/vision/2026-10-04/new_match_fixed_reference_transfer_v0_2.json)

## Validation and next step

34 focused tests pass across detector calibration, meld normalization,
body context, face segmentation, and the new peer probe. The four new tests
cover leftmost recovery with/without a touching animation, missing peers,
distant bright components, and duplicate prevention. Generic detector inputs
remain unchanged. Synthetic tests do not establish real-video recall.

Next audit the SHA-pinned old and new N/M9 faces for label, glyph, perspective,
and descriptor mismatch while keeping this reference selection and scorer
frozen. Record any later feature or geometry alternative as a separate
development comparison; no score-driven replacement of the frozen references.
