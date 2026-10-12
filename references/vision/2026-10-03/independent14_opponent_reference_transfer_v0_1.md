# Independent-recording S234: reviewed opponent reference transfer

Issue #69 / Draft PR #117 development experiment. Added reviewed S2/S3
reference support, but the independent recording still fails identity retrieval.
Keep Runtime unchanged; do not promote the S789 success to general accuracy.

## Reference qualification

The repository's reviewed September 26 first-hand opponent S123 strip is
SHA-pinned (`4a3c2b5f…75bc5de`), 71x165, five lossless 71x33 rows. Its queue
records USER_AND_VIDEO_REVIEW_CONFIRMED and original match
`reviewed_match_2026_09_26_first_hand`. The fixed central strip row is rotated
180 degrees for the top seat, split using the existing light-body adapter,
and each reference uses the same single-face normalization as the queries.
Visual inspection confirms the canonical bird / two / three sequence.

The declared raw source SHA is `fba5f67d…64fc3`. This turn reverified the strip
hash, not its pixel correspondence to the full original video. The accessible
similarly named uploads were 16.33s and 9.1s derived clips (different SHAs),
and cannot reverify the ~125s source window. Do not substitute their hashes or
claim recovered original frame indices. The reference ordinal is 3, not frame 3.
Raw original recheck remains pending. This is a declared-lineage development
comparison, not formal source qualification or blind validation.

Only one original match is added. Five temporal rows do not count five times.
Both all same-match aliases and identical source SHAs are excluded. This
supplement is excluded entirely from the related S789 query match.

## Controlled result

Original `14.mp4` SHA is verified before decoding frames 2549/2552/2555.
The reviewed S234 rectangle associates the actual detector candidate only;
candidate crop edges never depend on that rectangle. References from recording
14 are excluded. Scoring, thresholds and geometry parameters remain fixed.

| Actual detector + seam context | Before supplement | After supplement |
|---|---:|---:|
| Expected classes supported | 3/9 faces | 9/9 faces |
| Groups with all expected classes supported | 0/3 | 3/3 |
| Correct face rankings | 3/9 total; 3/3 supported | 3/9 supported |
| Exact groups correct | 0/3, unscorable | 0/3, scorable |

After supplementation, S2/S3 remain wrong in all three detector-crop frames;
S4 is correct. Frame 2552 winners are S5/S4/S4. Tight-body, outer-body and
measured-seam rectangle modes also score 3/9, 0/3; measured-seam rectification
scores 2/9, 0/3. Repeated rows and summaries are identical.

The same-match exclusion control admits zero supplementary references and
keeps S789 15/15 faces, 5/5 groups across all six symmetric modes. It is a
regression control, not another independent match.

## Interpretation and next acquisition

Normalization symmetry fixes the S789 development failure, but does not by
itself solve independent S234 identity transfer. These opponent reference
faces are small and have a different viewing pose from the bottom-seat query.
That domain gap is a plausible explanation, not a causally isolated finding.
No legal-group decoder is used to force the expected S234 answer.

Acquire reviewed bottom-seat exposed S2 and S3 from an original match excluding
recording 14, with exact raw-source SHA, frame indices, crop hashes and original
match grouping. Prefer comparable viewing pose before adding more same-event
frames. Re-run the fixed symmetric comparison against all competing classes.
Keep the opponent strip as an explicit cross-view transfer control. At least
two other independent matches remain required for the formal packet gate.

## Reproduce

Run `workspace.vision.evaluate_sift_detector_body_boundary_probe` with
`--spec-file references/vision/2026-10-03/independent14_s234_detector_spec_v0_1.json`
and `--reference-geometry`, once without and once with
`--opponent-s123-reference`, passing original `14.mp4`, the confirmed private
template ZIP and an output path. Numeric evidence, source/input hashes and
diagnostic rankings are in `independent14_opponent_reference_transfer_result_v0_1.json`.

29 focused tests passed, including source-SHA and same-match alias exclusion,
missing-lineage abstention and the geometry/private-loader/scorer regressions.
At preceding commit 1376dad, Tests, Vision Regression and Evidence Contracts
passed; this does not assert the new revision's CI result.

Development only; no runtime integration or promotion. Hint read-only,
Executor OFF; CurrentAgent V0.10 unchanged.
