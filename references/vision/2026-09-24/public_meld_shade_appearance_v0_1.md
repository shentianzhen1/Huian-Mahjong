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
