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

Results: `references/vision/2026-10-03/flat_meld_sift_low_data_diagnostic_v0_1.json`
and `wan_numeral_upper_half_probe_v0_1.json`. Raw private reference pixels remain
outside the repository. Next: test a fixed numeral branch on additional
source-qualified Wan queries, preserving original-match exclusions and a
separate suit decision. Do not replace the general scorer or tune on this group.
