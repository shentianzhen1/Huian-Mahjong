# Issue #69 — original-video dual-region onset and background-control audit

**Date:** 2026-09-25. **Scope:** development-only original-video
optical/geometry diagnostics; source-overlapping background controls. No
user-approved claim action or independent full automatic three-observer event
has been established. **No video, crop, filename, raw video/frame SHA, precise
event timestamp, player identity or private review registry is committed.**

## Why upper-region disappearance is insufficient

The existing experimental original-video upper-public raised-tile probe
detects when one tall component disappears between two adjacent source frames.
This can be consistent with a player responding to a preceding public tile,
but the same visual signature also occurs during other game transitions.
A one-to-zero upper optical transition **MUST NOT** become DISCARD, CHI,
PENG or KONG by itself. The frame may be from an *in-game REPLAY*; replay
transport buttons are excluded from the upper source pixel region. Live
button detection requires different live-source evidence and remains
unimplemented. Concealed-hand shading is never used.

## Actual private source audit

Rechecked the existing seven previously selected candidate new-meld source
frame brackets, drawn from **two original matches**. Every original-video
SHA matched the previously approved private registry. All seven original
pre/post source-frame pixel SHA pairs matched their frozen private records.
The upper-region extractor independently reproduced **seven one-to-zero
raised-component withdrawals** across those selected adjacent pairs.
The separately maintained human-reviewed lower-region source ledger places
the first visually separated new public group at each of those same frame
pairs; two prior and two later upper negative-control frames were verified
stable for each previously selected case.

**This is seven same-source selected two-region visual correlations,
not seven verified CHI actions and not blind recognition accuracy.**
The lower NEW meld track/face labels at the first blurred animation
frame have NOT yet been reproduced by an independent automatic segmenter.
Actual incoming discarded tile identities, independent stable hand-count
change and owner sign-off remain unverified as complete triads.

A second private audit deterministically sampled **18 unrelated source
adjacent pairs per existing original clip**, across all **nine clips**:
**162 original-frame pairs** in total, excluding frames within 90 frames of
the seven already selected onsets. Both source frame and capture checks
were run on the original frozen files. The exploratory upper-only one-to-zero
detector emitted **two additional alerts** in those other windows. The
two alert frame sequences were visually reviewed and lack an independently
verified new lower meld onset in the audit. They therefore MUST remain
unattributed upper public withdrawals; a source-verified different
claim/discard or game animation is not established. This sample includes
unadjudicated game transitions: **do not derive a false-positive rate,
specificity, source-disjoint generalization or 162 proven no-event labels**.
There are still only two original matches.

The complete nine-video source hashes, 7 selected source frame indices and
pixels, 162 private background windows and the two other-alert source
contact sheets remain in the **PRIVATE** local review only.

## New safe join and tests

`public_raised_tile_withdrawal.py` preserves private original
source-session/SHA/epoch provenance in its in-memory successful review;
its public `to_dict()` deliberately redacts those identifiers.

`public_dual_region_transition.py` accepts:
- a source-verified successful UPPER raised optical withdrawal with exact
  original adjacent frames;
- a **separately source-reviewed** adjacent NEW LOWER public-meld onset
  on **those very same** frames, SHA, session and epoch;
- explicitly verified prior raised/post absent upper negative controls
  and independently reviewed upper/lower regions.

It rejects upper-only disappearance, mixed sources/epochs, mismatched frame
pairs, unstable controls, existing meld merely receiving shade, unknown
lower face count and upper→upper mismatches. Its only possible positive
is `SYNCHRONIZED_TWO_REGION_APPEARANCE_CANDIDATE_ONLY`. This is
not source-frame automated lower segmentation, an incoming-tile label,
a claimed discard, a real CHI/PENG/KONG or an Owner-approved event.
All such fields remain `UNKNOWN`; Runtime/Hint/AI/Executor untouched.
PENG/KONG never require positional shade, and ordinary DRAW remains a
separate draw_visual temporal observation.

Synthetic contract coverage is in `tests/test_public_dual_region_transition.py`
plus the source-provenance assertions in
`tests/test_public_raised_tile_withdrawal.py`. Both run in the
shared generic root-public Vision regression with its optional OpenCV
dependencies, as well as the normal core matrix.

## Next acceptance criterion

Use independent automatic source-pixel public-river identity, independently
tracked semantic concealed-hand count (not shaded-slot brightness), and
automatically tracked stable lower public-meld geometry to corroborate
a real **same-source** adjacent appearance bracket. The seven manually
selected examples are for development only; get untouched original
matches before reporting any independent validation metric. The seven
owner-facing action-event relations remain pending; all canonical output
retains `UNKNOWN` until evidence is sufficient.
