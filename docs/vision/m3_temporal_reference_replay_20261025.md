# Real M3 temporal-reference recovery — 2026-10-25

Previous c125647 passed all five CI workflows. Continued with the same verified
137-label clean experimental bank; no production code or installed assets changed.

Recovered the existing Sep26 source55328a7b… sequentially. Coarse frames4800–4920
at stride6 produced59 spatial candidates; fine frames4856–4872 at stride1
produced40. After visual inspection, fixed four representative M3 appearances
at4857/4861/4865/4867 before target A/B: normal, partial lift and high lift. These
are the SAME discard event and SAME original match, not four independent samples.
Do not infer class labels from the spatial selection heuristic.

The private raised-appearance packet is now2026.10.25.2(filename v0_2), with41
crops:6 reviewed hand development candidates,31 UNKNOWN,1 terminal Hu negative
and3 badge controls. Only four new crop files were added. Previous v0_1 remains
available. No private pixels were uploaded to GitHub.

Supplementing the prior15-reference offline candidate with these four crops
changes the actual frame1776 crop from S2 0.556055 to M3 0.856422. Full237-window
source-clock replay through the actual UI worker, dual-frame confirmation and
advice pipeline gives172→173 displayed shanten windows and41→42 discard windows.
Only1776 is new. No previous accepted hand, shanten or discard choices change;
all source RGB hashes match. No geometry-untrusted window displays advice and
the terminal Hu interval stays blocked.

All14 endpoint hand crops at1776 were visually re-reviewed and agree with the
candidate. Own meld count1 is sufficient for structural shanten1; the four tied
structural discards are M3/P2/P6/S8. Meld identities remain UNKNOWN, so public
remaining-copy/danger capabilities are not established. Earlier frames in the
burst were not fully reannotated. This is a revealed development checkpoint,
not independent per-window correctness or formal promotion evidence.

Clean134-query controls compare the prior candidate to this one with the same
bad-crop exclusions and match/SHA holdout protocol. Top1 correct110→109;
scores>=0.82 remain93, wrong scores>=0.82 remain0. The lost P5 top1 is explicit:
P5 0.749396→M3 0.449610, both rejected. M1/M8 low-score changes also stay rejected.
Do not describe this as a universal raw-accuracy improvement or zero-error model.

No installed reference version bump:19 references are an OFFLINE composite,
while the installed bundle remains2026.10.25.5. Threshold0.82, AI V0.10,
Executor OFF and Draft/unmerged PR stay unchanged. Full replay uses a fixed
source clock and ignores worker duration; Windows latency still needs its own
measurement. Source/crop SHA checks passed; no unrelated tests rerun for this
data-only update. Next validation must retain these regressions and use qualified
new-match/capture evidence rather than keep tuning these two revealed targets.
