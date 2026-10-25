# Existing raised-appearance recovery — 2026-10-25

Recovered and SHA-verified the existing Sep26 video55328a7b…; sequentially
decoded6512 frames. Every12th frame was scanned for hand components at least
7px above the median of eight or more components, selecting candidates at least
24frames apart. This heuristic recovered37 crops, not37 qualified examples.

Reviewed original full-frame context for six selected crops. W at3180 and M3
at4860 are raised-hand development candidates. W at2424 is a terminal Hu
screen and is excluded from positive continuing-play references. Three S8
crops at3504/6120 are Ting-badge controls, not confirmed raised examples.
The remaining31 crops retain UNKNOWN. No raised S9 example was established by
this limited scan; absence from the scan does not prove the recording lacks it.

The private pixel packet is version2026.10.25.1 in the separate
`raised_appearance_private` family (filename v0_1); it does not change the
installed reference bundle2026.10.25.5. Its37 crops, review sheet, hashes and
separate two-positive manifest are saved privately. Public metadata contains
no pixels. All crops remain in one reviewed Sep26 original-match group and
none is an approved template or independent holdout.

Supplemented the existing explicit development classifier with just the two
positive candidates and repeated the two actual Runtime crops. Frame228 W
changes from E0.400603 to W0.903375; frame1776 M3 remains S2 0.556055. Query
pixels were not training references. This is a revealed target-only diagnostic,
not a full replay, error-control evaluation, calibrated probability or promotion.
Do not deploy from this result. Complete-hand and negative-control replay must
precede any proposed packet update. No runtime code, model, threshold, AI,
Executor or installed bundle changed. No unrelated tests rerun for this data-only
recovery; all source, frame/crop RGB and crop-file hashes were recorded.
