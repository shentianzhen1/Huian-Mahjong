# Raised-tile recovery probes — 2026-10-25

Follow-up to the advice recovery audit at `2ecc153`. Original source SHA,
reference version2026.10.25.5 and explicit trial classifier are unchanged.
No Runtime change or advice-acceptance improvement is claimed.

The actual neighbor-safe classification crops reproduce the worker failures:
frame228 W→E at0.400603 and frame1776 M3→S2 at0.556055. Detector-only crops
produce different scores and must not be described as current Runtime inputs.
Compared actual crops, vertical extensions/trims, and seven height/width ratios.
All32 evaluated crops remain below0.82. Best true-label results are W0.617365
and M3 0.735363. Arbitrary crop tightening is not a recovery solution.

A symmetric dark-ink feature removes background and tile-body proportions.
Both target identities rank first: W0.860487, M3 0.399475. However, approved
ordinary concealed labels tested while excluding each query's stored session
produce82/144 top1 correct;112 queries have true-class support,44 scores reach
0.82, and three of those are WRONG: S3→S7 0.845214, S5→S7 0.853485 and
S7→S5 0.853485. Core control bank excludes packet supplements. Target probes
include existing packet hand references. These protocols are diagnostic and
must not be pooled into one accuracy claim. Sessions are not independent matches.

Reject the global glyph classifier/fallback. W's single-frame success does not
qualify a separate honor-only path; no class-specific exception is introduced.
Preserve UNKNOWN,0.82, fresh dual-frame confirmation, AI V0.10 and Executor OFF.
Next useful work needs qualified raised/animated appearance support and stronger
classification evaluated on full hands; stop broadening simple crop/threshold
searches from these same anchors. Metadata retains every crop hash, box, score,
glyph ranking and all three high-score control errors. No private pixels added.

No production code changed, so no unrelated full test suite was rerun. The
previous advice recovery audit's20 regressions are historical validation, not
new tests for this offline rejected candidate.
