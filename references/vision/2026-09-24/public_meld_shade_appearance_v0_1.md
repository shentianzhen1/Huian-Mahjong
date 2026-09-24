# Issue #69 — Exposed meld shaded-face appearance V0.1

**Date:** 2026-09-24. **Scope:** development-only appearance hint from
existing footage; **not** an action, incoming tile identity, or live
recognition claim. The owner's observation is that an acquired tile can
look darkened in an exposed meld. Our first implementation explicitly
tests that visual cue while requiring a separate discard/action record
before it can ever mean "this was the incoming tile."

## Engineering implementation

On the already-open stacked PR #112:

- `workspace/vision/public_meld_incoming_shade.py`: pure three-face
  appearance detector. For each individual regular face crop, take the
  65th-percentile RGB max (HSV value) within the 15–85% horizontal and
  13–82% vertical interior. Candidate requires one face <=165, its other
  two peers >=178, a gap >=28 (8-bit V units), and peer spread <=20.
  The thresholds were chosen after inspecting this existing data and
  are NOT independently calibrated for other rooms/videos.
- Output includes `shadow_index=0|1|2|None`, three V65 measurements
  and **relative darkness scores in brightness units, not confidence
  probabilities**. `shade_is_confirmed_incoming_tile=false`,
  `incoming_tile_id=UNKNOWN`, `action_kind=UNKNOWN`,
  `actor=UNKNOWN`, `turn_actor=UNKNOWN`,
  `requires_independent_discard_corroboration=true`,
  `formal_promotion_evidence=false`,
  `safe_for_runtime=false` and `safe_for_executor=false` always.
- The existing `public_meld_shadow_bridge.py` now calls this
  appearance probe **only after** verifying an already human-reviewed
  **target=meld** ROI, original-video session/SHA, exact screenshot SHA,
  exactly one matching geometry candidate, and ordinary three-face
  segmentation. A stacked added Kong, four adjacent faces or an
  unreviewed bottom-group / hand / Gold region abstains. The PR #110
  `shadow_proposal` identity classifier is a **different signal**
  from visual `shadow_index` and remains abstained on real fixtures.
  No change to Runtime/Rules/AI/Hint/Executor and no Ledger action
  promotion.

## Existing private source verification (no new recording)

The owner previously confirmed the visible identities of G01–G12 /
36 crops from 8 clips of **one** original match plus the earlier separate
14.mp4 rules replay of a **second** original match. A separate PRIVATE
local audit reverified all 9 original video SHA-256 values and matched
all 36 approved PNGs pixel-for-pixel against the exact decoded source
frames before computing shade statistics. Neither crops nor any
private video IDs/hashes are committed.

The SHA-verified local mirror of the fixed V65 gate (using the exact
central crop proportions/thresholds above) produced:

| Already-confirmed private group | Shade appearance, 0-based | Notes |
| --- | --- | --- |
| G01 | 2 (right) | V65 193 / 190 / 140 |
| G02 | UNKNOWN | 196 / 196 / 196 |
| G03 | UNKNOWN | 197 / 196 / 196 |
| G04 | 2 (right) | 197 / 196 / 139 |
| G05 | UNKNOWN | 197 / 196 / 193 |
| G06 | UNKNOWN | 196 / 197 / 196 |
| G07 | 0 (left) | 139 / 195 / 194 |
| G08 | 1 (middle) | 196 / 138 / 196 |
| G09 | 1 (middle) | 195 / 135 / 188 |
| G10 | 1 (middle) | 194 / 137 / 189 |
| G11 | UNKNOWN | 196 / 196 / 196 |
| G12, other original match | 0 (left) | 137 / 194 / 193 |

**Seven** groups have a strong darkened-slot *appearance* and **five**
abstain. At the original group bbox in adjacent frames sampled
-0.50, -0.25, +0.25 and +0.50 seconds, **6/7** shade candidates
retain the same slot at all four neighbors; the other, **G12**,
has NONE at -0.50 and left-shaded in the other three. All five
original abstentions remain abstentions in all four neighboring frames.

**Important semantic counterexample:** in the separate existing
replay, the same three-face G12 group is already visible unshaded
at an earlier time. The first face then becomes darkened during a
subsequent display/turn transition. This DOES NOT independently prove
a new CHI/PENG/KONG event at the moment shade appears, nor that
the shaded face equals the previous independently observed discard.
Therefore shade appearance and an action/event transition must be
tracked as separate evidence. The original owner-confirmed 36 tile
identities **do not** constitute an owner-confirmed set of 12
incoming-tile positions. Confirmed incoming-tile ground truth: **0**.

All results are on previously inspected, non-independent
development data selected while tuning thresholds. Never report
7/7 "incoming identification accuracy"; only 7/12 candidate
coverage, 5/12 abstention and the measured temporal appearance
consistency. A Gold + concealed-hand lookalike can also have an
uneven brightness profile: the independent reviewed-public-meld
provenance gate, **not** shade alone, rejects it.

## Regression and deployment boundary

The CI suite includes synthetic left/middle/right dim overlays, art-only
brightness differences, uniform screen dim, two dark tiles, invalid
or stacked Kong layouts, fake Gold/hand targets, tiny crop rejection,
and proof that scores are not probabilities. Real already-reviewed
public screenshot fixtures additionally verify integration with
source-locked PR #110/111 while preserving UNKNOWN action and
runtime flags. Source-private crops are not uploaded to GitHub CI.

Run from repository checkout with Vision extras installed:

    python -m unittest discover -s tests -p "test_public_meld_incoming_shade.py" -v
    python -m unittest discover -s tests -p "test_public_meld_shadow_bridge.py" -v

PR #112 remains DRAFT, stacked on PR #110 and holding temporary
copies of PR #111 segmentation files; reconcile after the dependencies
are independently reviewed/merged. Do not merge automatically.

**Next gate using existing footage first:** inspect genuinely
independent discard timing *before* these previously observed groups,
then review each candidate relation `shadow_index ↔ discarded_tile`
and any temporal disappearance of river tile. Mark ambiguous animation
and replay transitions UNKNOWN. Until those source-verified tests pass,
do not emit `CHI incoming=M5`, `PENG`, or any other action from
shade alone.


## Owner-confirmed delayed shade timing correction

**New direct owner observation (2026-09-24):** the visual darkening on the
acquired tile does **not** necessarily appear at CHI/PENG/KONG time. It may
be displayed only **after a perceptible delay following the action**.
Consequently, an existing unshaded meld changing into a shaded meld is
**expected UI behavior**, not evidence that another action just occurred.
The precise delay is not yet measured; do not hardcode an animation duration
or give SHADE_APPEARED the action's timestamp.

The read-only `public_meld_delayed_shade_review.py` now separately records
the first source-qualified visible group frame, the first *stable* shaded
slot observed later, the observed frame difference and (only with independently
verified video FPS) observed seconds. All output explicitly distinguishes
`observed_lag_from_first_meld_observation` from the still-UNKNOWN
`actual_action_to_shade_delay`. There is **no action or incoming tile
promotion**, even when an appearance slot is stable.

- `newly_observed` group + later stable shade: follow-up appearance only;
  source time is the first *observed* group, not the verified CHI/PENG/KONG.
- `pre_existing` group + later stable shade: an unassigned shade change,
  specifically **not a second meld event**; protects the G12 scenario.
- A group already shaded when first seen: left-censored; cannot measure
  onset or delay.
- Shading for only one frame, changing slots, a discontinuous time window,
  source/epoch/track changes, a hand/Gold group, or an unverified source
  frame: fail closed / abstain.
- No fixed game-specific timing window. To admit deliberately sampled frames
  the caller specifies the verified maximum frame gap; otherwise stability
  requires adjacent source frames.

The **next real-footage evidence gate** is still independent: inspect the
actual preceding discard and hand/meld geometry transitions in the original
recording, preserving the ordering `discard → meld visibility →
possibly delayed shade`. The appearance layer must be associated with
the *same* SHA/source/epoch/meld track and cannot independently identify
a true action or tile identity. Existing 7/12 shade-detection coverage
remains appearance-only; 0 verified incoming-tile positions until the
source-verified per-event discard review is completed.


## Seven existing-source upper-discard / new-meld / delayed-shade cross-checks

**2026-09-24 next evidence step; NON-BLIND assistant-reviewed development data.**
No new footage was requested. The same previously approved private 36-face
packet was re-read, all **9/9 original-video SHA-256 checks** were repeated,
and every approved face PNG was compared with its exact decoded source-frame
pixels (**36/36**). Of the previously identified seven uniquely shaded groups,
**7/7 now have three manually viewed source-local observations in sequence**:

1. An enlarged **upper-screen public tile** is visibly presented.
2. A previously absent **lower-screen three-face suited sequence** becomes
   publicly visible; the user's already approved meld-face identity on the
   eventual dark slot equals the previously shown upper tile.
3. The **same** new group remains visible initially unshaded, and the
   expected slot darkens only **later**, in at least five adjacent original
   source frames under the original fixed V65 appearance gate.

Six examined groups come from clips of **ONE original eight-hand match**,
and the seventh from **ONE previously supplied separate replay**, so the
sample contains only **two original matches**, not seven or nine independent
matches. All seven reviewed candidate group layouts are CHI-like suited
sequences; this new audit proves **zero real PENG/KONG cases**. The other
five earlier reviewed groups without a unique detectable shade remain
abstentions: do not assign their incoming-tile position by guessing.

The first stable unique shade after the **selected already-stable meld
screenshot** was observed approximately 0.24–2.19 seconds later across
the seven pre-inspected examples. This is **not** measured time since
the true CHI, and the thresholds/samples were already inspected before
this analysis: no animation delay constant, accuracy estimate, source-
disjoint blind-test claim or generalization evidence follows.

**Important correction to the earlier isolated G12 counterexample:** the
unshaded group already exists *by the time the later shadow appears*,
and consequently the shadow onset itself cannot timestamp a new action.
Looking farther back in its original source video revealed a preceding
matching public display and the earlier appearance of the actual new
three-face group. Thus G12 is also a **development-level prior-discard /
new-group / delayed-shade correspondence**, not proof of an additional
action when darkening occurs.

**Owner-approved facts are the 36 face identities only.** The seven
event-to-discard correspondences are newly **assistant-reviewed** using
frame-referenced private video and a source-verified private visual
review packet. They have NOT been independently approved as event truth
by the owner or validated using *automated* independent RiverSnapshot
and hand/meld-delta tracking. Canonical public action and claimed-tile
fields must remain UNKNOWN. A human visual comparison of selected
examples is not a 7/7 automatic-action recognition score.

### Code and test boundary

New pure read-only
`workspace.vision.public_meld_action_cross_evidence` consumes
independently reviewed preceding public tile, absent→new exposed
meld geometry and a contiguous **same SHA/session/stream_epoch/track**
sequence from `public_meld_delayed_shade_review`.
It requires that the explicit displayed tile identity matches the
**later** shaded position within a legal three-face suited sequence
(or a synthetic triplet PENG-like shape), and requires a source-verified
no-intervening-public-action review. If an old group merely changes
shading, the source/stream changes, time order is reversed, a gap exists,
or the identities conflict, it fails closed. It NEVER turns the shade
onset into the actual action timestamp.

Its only successful output is
`DEVELOPMENT_CORROBORATED_CANDIDATE` with a **CHI_LIKE/PENG_LIKE**
hypothesis and the original preceding-discard→new-group frame interval;
`production_action_kind=UNKNOWN`,
`production_incoming_tile_id=UNKNOWN`,
`formal_promotion_evidence=false`,
`safe_for_runtime=false`, and `safe_for_executor=false`
are unconditional. GitHub CI runs **12 synthetic contracts** (including
seven layouts matching the inspected development examples, a synthetic
PENG, changed source/track/epoch, wrong shaded slot, left-censored shade,
already-existing groups and false new-action prevention). Private
original source hashes, exact clip timestamps, per-face identities,
source stills and event-packet images remain OUTSIDE the public repository.

**Remaining separate gates:** human adjudication of the seven private
event-timeline pairs, a reproducible source-scoped independent
machine river/hand/meld-delta correlation, then genuinely untouched
original-match evaluation. PR #112 stays DRAFT and unmerged;
Executor stays OFF.
