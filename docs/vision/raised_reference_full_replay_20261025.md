# Recovered raised-reference full replay — 2026-10-25

At1569715, supplemented the existing experimental packet with only the two
reviewed Sep26 hand crops(W3180,M3 4860). Actual UI worker and pipeline, no
manual Gold, same237 fixed400ms source-clock endpoints as the earlier recovery
audit. All source-frame RGB hashes match the baseline. This is offline trial
replay, not Windows timing or independent accuracy; worker time is not scheduled.

Displayed suggestions171→172; post-draw discard windows40→41. No previous
accepted window lost and no previously accepted shanten/discards changed.
New frame228 has17 manually re-reviewed endpoint crops, all matching the
candidate hand; shanten2 with M3/P1/P4/P8/W tied structurally. Earlier frames
in the burst were not fully reannotated. Raised W is0.903375; M3 at1776 remains
UNKNOWN. No geometry-untrusted window displays advice. The terminal Hu interval
remains blocked. Candidate replay has15 references; installed13-reference
bundle2026.10.25.5 is unchanged.

Initial144 ordinary control queries: baseline106 correct,91 scores>=0.82,
4 wrong scores>=0.82; candidate111 correct,95 scores>=0.82,3 wrong. Subsequent
visual audit found the run had included ten previously reviewed bad crops.
Retain it as a raw diagnostic, not clean ground truth. In particular apparent
S8/S9 and clipped S6 errors must not silently become new rule/label facts.

Corrected134 control queries exclude the frozen ten bad crops from BOTH
training and queries. Reviewed original-match groups are held out; unresolved
queries hold out their exact source SHA. Sep26 queries exclude all packet
references. Unknown-source matches are not proven independent. Baseline105
correct,89 scores>=0.82,1 wrong; candidate110 correct,93 scores>=0.82,0 wrong.
Five M3 queries improve; another M1 remains wrong but below threshold. These
are candidate score diagnostics, not Runtime-gated acceptance probabilities.

The cleaned controls and the full replay use DIFFERENT training banks: full
replay deliberately retains the real current worker bank. Do not pool their
zero-error claim. Before any bundle change, repeat full replay under an explicit
cleaned experimental bank and evaluate negatives/complete hands together.
The prior HOG/glyph experiments also used the raw approved bank; their recorded
results remain historical raw diagnostics, not clean classifier verdicts.

No code, approved templates, source qualification, AI, threshold, Executor or
installed reference bundle changed. Private pixels remain in versioned packet
v0_1; public metadata retains hashes, source protocol, changed window and both
control results. No unrelated tests rerun for this data-only experiment.
