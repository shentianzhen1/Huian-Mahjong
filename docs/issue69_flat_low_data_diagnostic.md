# FLAT recognition with limited independent references

Date: 2026-10-03. These are separate offline diagnostics, not a relaxation of
the frozen SIFT candidate's two-other-original-match requirement or any Runtime
threshold. Query match and exact source SHA are excluded in both modes. No
classifier output from this diagnostic becomes a physical tile identity.

## Seven inspected ordinary melds

The verified private supplement adds 15 templates from five recovered groups.
The frozen two-other-match ranking has zero groups with all expected classes
scorable. A separate one-other-match diagnostic makes two groups fully scorable:

- Reviewed P678: face and group ranking P6/P7/P8.
- Reviewed M456: face ranking M4/M5/M3; legal group decoder ranks the wrong
  M345 sequence, so legality alone does not fix the identity.

The other five groups still lack reference support for one or more expected
classes. Do not include them in a claimed classifier-accuracy denominator, or
call the resulting 1/2 a generalization accuracy. All inputs were previously
inspected and these experiments remain selection/development evidence.

Reproduce:

```bash
python -m workspace.vision.evaluate_flat_meld_sift_low_data --private-template-zip /path/outside/repository/verified.zip --output /tmp/flat_low_data.json
```

## Within-Wan numeral diagnostic

Visual inspection shows that the M456 query crops preserve the numerals. One
fixed symmetric top-half transform was applied to both query crops and verified
Wan templates. No crop-ratio search or descriptor-parameter change occurred.

| Fixed mode | Independent face winners | Group ranking |
|---|---|---|
| Whole face, all available classes | M4/M5/M3 | M345 |
| Whole face, Wan classes only | M4/M5/M3 | M345 |
| Upper half, Wan classes only | M4/M5/M6 | M456 |

The Wan-only whole-face control isolates the improvement from merely removing
other suits. The result is consistent with shared lower-face artwork affecting
whole-face matching, but does not establish that as the sole failure cause.
The corrected group's margin is only 0.00876509; no development proposal or
Runtime acceptance is emitted. This single reviewed group does not validate suit
recognition, other Wan digits, circles/bamboo, or new original-match performance.

Reproduce:

```bash
python -m workspace.vision.evaluate_wan_numeral_probe --private-template-zip /path/outside/repository/verified.zip --output /tmp/wan_numeral.json
```

## Fixed transform, reverse source direction

The v0.2 evaluator also uses the verified private Wan crops as queries, excludes
their entire original match and exact SHA, and compares whole-face/Wan-only with
the unchanged upper-half/Wan-only transform. No ratio or scorer tuning followed
inspection of these results. The independent public recording supplies M4/M5/M6.

| Private query group | Expected face | Whole-face winner | Upper-half winner |
|---|---|---|---|
| G02, M345 | M4 | M4 | M4 |
| G02, M345 | M5 | M5 | M5 |
| G08, M567 | M5 | M5 | M5 |
| G08, M567 | M6 | M6 | M6 |

Both modes rank all four supported faces correctly: zero improvements and zero
regressions. These are four observations in two groups from **one** original
match, not four independent matches. The upper-half raw score gaps are smaller
on all four; those gaps are not calibrated confidence and must not justify
acceptance thresholds. Five other reviewed Wan faces (M1/M2/M3/M3/M7) have no
independent true-class support and are reported separately. None of the three
private groups is fully scorable, so there is no reverse-direction whole-group
success claim. The crops were previously inspected, not a blind holdout.

This provides a limited no-new-error check for the fixed transform, not evidence
of a general gain. Keep the branch offline and preserve the whole-face control.
Next: extend independent real-template coverage, then evaluate a separate suit
decision and digit ranking together. Do not tune on either inspected recording.

Results: `references/vision/2026-10-03/flat_meld_sift_low_data_diagnostic_v0_1.json`,
`wan_numeral_upper_half_probe_v0_1.json` (initial inspected query), and
`wan_numeral_upper_half_probe_v0_2.json` (both directions). Raw private reference
pixels remain outside the repository. Runtime identities remain UNKNOWN.
