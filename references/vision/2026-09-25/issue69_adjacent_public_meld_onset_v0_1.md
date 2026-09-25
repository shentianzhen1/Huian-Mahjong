# #69 — Adjacent original-frame public meld onset review

**Date:** 2026-09-25. **Status:** source-reverified private development
observations and fail-closed PUBLIC-MELD source gate; NO automated
real-match action has been confirmed, and NO new runtime behavior.

## What was actually checked against the ORIGINAL private videos

The earlier seven CHI-like review cards paired an early public-discard
candidate with a later stable shaded exposed-meld screenshot, but their
early-to-later gaps were **14–43 still-uninspected intervening frames**.
Calling the later screenshot the first appearance was not safe: the
exposed group may already have appeared much earlier, while its shade
is delayed, and the preceding bottom-hand region may contain the
**same-looking hand tiles** before they become a separate meld.

This round re-opened the **original source video bytes**, verified source
SHA-256 for each of the seven existing groups and checked every group's
21 originally approved *later* face crops against their original decoded
frame/bbox pixel arrays (**21/21 exact matches**). The seven groups derive
from exactly **two** independently original matches, not seven.

For each of the seven candidates, the assistant privately sampled the
original-frame **pre-event hand or existing public-meld context**, followed
through the intermediate frames, and narrowed the **first visually
separated new three-face group** to a pair of **adjacent decoded source
frames**. Both original frames in every pair were decoded and their raw
pixel SHA values checked to differ. The seven distinct original-source
pre/post pairs and frame SHA values live ONLY in the private local audit.
They are not public training data, are not owner-approved event truth and
must not be mistaken for seven confirmed CHI actions.

**Why the distinction matters:** the new group's earliest visible frame
is an **animation/appearance bracket**, NOT a stable face-label frame,
NOT the player's click time and NOT the later shade's first visible time.
Owner approval of 36 static displayed face identities covers the later
samples, not the action relation or the initial animation pixels.
The previous hand-shadow eligibility hypothesis remains withdrawn.

## New source-gated implementation

`workspace/vision/public_meld_adjacent_onset.py` adds a strictly
read-only `review_adjacent_public_meld_onset` contract:

- Requires TWO consecutively indexed frames from the **same original
  source SHA, session, stream epoch, screen side and resolution** with
  separately attested **original decoded frame pixel hashes**.
- Requires independently reviewed **PUBLIC-MELD region**, separate
  from the concealed hand and Gold. Never inspects or uses hand shading.
- Rejects pre-existing target tracks merely changing shade, the same
  group reidentified under another tracker ID, an uncertain/missing
  new group, multiple simultaneous new groups, vanished/changed prior
  public melds, wrong face identity, overlay, source gaps and
  replay-source discontinuity. Replay video is permitted for *public
  meld geometry*: only LIVE *action buttons* need live-source proof.
- Returns only
  `NEW_MELD_VISUALLY_BRACKETED_OWNER_ACTION_PENDING`; actual
  `action_kind`, actor, incoming tile, action time and official
  event truth remain `UNKNOWN` without **independent** previous
  discard / hand-delta / meld-delta correlation and owner adjudication.
- This pure Python contract cannot verify raw video bytes or the
  upstream detector's visual classification itself: those must be
  attested by an actual private local source runner. Tests use
  synthetic generated source frames, not private recordings.

The existing `public_meld_observer_corroboration.py` now additionally
**requires a matching positive adjacent-original-frame onset result**.
A legacy `independently_reviewed_absent_before_present=True` Boolean,
a late shade or three synthesized RawObservations alone cannot
authorize the stronger observer corroboration result. The new onset
must match exact source scope, side, group track/approved later faces,
lie strictly after the alleged preceding discard and no later than
the first *stable* reviewed new group.

Regression: new root-public synthetic tests for source/epoch/ROI
mislabeling, pre-existing groups, same-identity re-tracking, non-adjacent
frames, bad source hashes, multiple new groups and no-shade
PENG/KONG. Existing triple-observer synthetic tests now pass a
separately constructed strict onset proof and include tests that
missing/pre-existing/inconsistent onset must abstain.

## Honest acceptance state

| Gate | Current state |
|---|---|
| Seven original-video source SHA checks | 7/7 pass |
| Previously approved later 3-face crop pixel checks | 21/21 exact |
| First visually separated group adjacent-frame brackets | 7/7 assistant-reviewed private development brackets |
| Automatic first-group segmentation on those original frames | **NOT YET independently verified** |
| Automatic discard + hand-delta + meld-delta triplets | **0 independently verified real-video matches** |
| Owner-approved action-event truth | **PENDING** |
| Source-disjoint blind promotion | **NOT qualified: only two original matches** |
| Runtime action/Hint/Executor | **unchanged; action UNKNOWN; Executor OFF** |

The adjacent-frame brackets eliminate large *visual appearance timing*
uncertainty on those seven candidates without pretending to solve
full automatic event recognition. Next: run genuinely separate private
source-frame public-river, concealed-hand-count and exposed-meld
observers in the narrowed windows; compare provenance and fail closed
for incomplete/contradictory results. Do NOT use any replay transport
button as a live action prompt or call animation onset the click time.


## Source-local exploratory optical edge-gap diagnostic

The next low-level pixel check is now implemented in
`workspace/vision/public_meld_gap_onset.py`, with synthetic tests in
`tests/test_public_meld_gap_onset.py`. It independently re-hashes
the **actual decoded consecutive BGR frame pixels** and checks for a
newly visible **teal background separator near the independently
reviewed late PUBLIC-MELD group's edge**, never for eligibility
shading within the concealed hand. It cannot be used if the original
source/ROI or the later group bbox is not separately authenticated.
The optical cue alone can never identify a tile or action.

On the SAME seven private original-video onset pairs already inspected
above, a deliberately provisional HSV edge-gap profile using each
group's previously approved late bbox produced **six exploratory optical
appearance candidates** (pre-gaps 0–4px, post-gaps 27–30px). **One pair
correctly abstained** under this diagnostic: the adjacent pre-frame
ALREADY had a wider separator in a differently styled row, so a fresh
new-group gap cannot be distinguished by this feature alone. This
does **not** mean that the seventh event was not a claim; it requires
a geometry/track/region signal that can distinguish the earlier
separated row from the newly exposed group.

**These are 6/7 SAME-EXAMPLE optical diagnostics, not recognition
accuracy:** the bbox profile and provisional thresholds were inspected
on these same seven previously selected samples; there is no untouched
test set, no reliable independent label for the animation frame, no
owner-approved action event and no independently reproduced automatic
river+hand+meld triplets yet. A changed UI layout, dimmed tiles or an
already exposed group may cause false optical gaps. The complete
three-channel reconstruction still requires the strict verified
adjacent PUBLIC-MELD track gate and independently observed evidence.

The 14-onset synthetic gate tests + two observer integration negatives,
and the optical probe's nine synthetic negative/positive tests are in
the shared #113 Vision lane. Archive video bytes, the 14 source frames,
their raw SHA values and the private seven-event registry stay outside
the public repository.


## Source-local upper public raised-tile disappearance (exploratory, no identity)

The same seven PRIVATE original-source adjacent-frame onset pairs now have a
second, spatially separate, **algorithmic pixel signal**: the enlarged
upper-side public tile-like component vanishes between the pair while the
assistant-review lower-side new-meld separation begins. This uses
**upper-region raw BGR pixels only**, never the concealed-hand brightness
or the game replay's `重播/暂停/返回/下一步` transport controls.

`workspace/vision/public_raised_tile_withdrawal.py` introduces an
**exploratory** automatically extracted tall upper bright-component
withdrawal probe. The module checks original source-video SHA/session/epoch,
true adjacent source-frame indices, exact recomputed decoded-frame SHA,
stable dimensions and independently verified unoccluded upper PUBLIC
region. It demands exactly one prior tall candidate and zero later
candidates; a still-visible raised tile, absent prior raised shape, two
competing raised shapes, capture gap, changed source, mismatched frame
hash or doubtful region all return `UNKNOWN`.

A private source-only recheck, against the **same seven already selected
onset pairs and the previously frozen source SHA/frame-pixel registry**,
returned a shape-withdrawal candidate on **7/7 pairs**. Stable-shape
negatives were separately tested at two pre-event frames and two
post-event frames per group: **7/7 earlier unchanged pairs still had
the raised component; 7/7 later unchanged pairs had no raised component**.
This is fourteen within-source negative *pairs*, all from just two
original matches. No cropped or raw images or original private frame hashes
are committed to the public repository; original records remain in the
private local audit.

**NOT an accuracy claim:** the exploratory ROI and profile were designed
using these same seven chosen clips. Although the source montage visibly
shows upper tile withdrawal synchronized with the manually selected new
lower group in all seven, the full matching between the actual discarded
tile identity, lower public meld identity and concealed-hand count has
NOT been automatically verified. The upper tall blob can include both
the enlarged tile and the flat underlying public river row; its connected
component bbox is NOT the exact tile bbox or an independent OCR identity.
An upper animation, replay overlay at another region, another source/UI
skin or a coinicidental redraw can confound this diagnostic.

Of the seven selected lower-onset samples, the earlier exploratory
lower-edge gap test returned six source-local optical candidates and
abstained on one already-separated row. The new upper detector is a
**separate ROI-based development cue** to help source-frame triage,
especially when lower-side gaps are already present; it does not
overrule lower-region abstention or make missing automatic three-channel
observations complete. CHI/PENG/KONG, incoming tile, actor attribution,
exact click time and owner event truth all remain `UNKNOWN`.
No rules, scoring, AI, Hint, Runtime or Executor changes.

`tests/test_public_raised_tile_withdrawal.py` adds ten synthetic
checks across both approved resolutions and the stable, ambiguous,
replay-agnostic public region, byte-hash, source, frame-gap, dtype and
resolution negative cases. Tests are in merged #113's generic root-public
Vision CI; the private real-video checks are separate from CI. The
next full acceptance step remains **automatic upper public-tile identity
and river provenance + stable concealed-hand count loss + independently
tracked lower meld delta**, reviewed against the owner event labels.
