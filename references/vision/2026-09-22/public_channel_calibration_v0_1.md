# Public Channel Calibration V0.1

Date: 2026-09-22  
Issue: #69  
Status: development-only channel narrowing

## Goal

Public Tile Detector V0.1 intentionally has broad recall. On the 16 locked
development-context images it produces many tile-like candidates from hands,
public tiles, exposed groups, replay UI, and other bright components.

This slice narrows those candidates into **evidence-backed geometry channels**
without pretending the channels are Mahjong actions.

Profiles are stored in:

`references/vision/2026-09-22/public_channel_profiles_v0_1.json`

Loader/audit code is:

`workspace/vision/public_channel_profiles.py`

## Development profiles

### central_action_focus_dev

Geometry:

- `upper_protrusion`
- reviewed zone approximately centered on the upper-middle enlarged action tile

Evidence includes the reviewed opponent:

- P1 offer/discard
- S9 offer/discard
- M4 offer/discard
- P7 offer/discard

However the same channel also appears in reviewed frames where the target fact
is **not** an opponent discard:

- fourth P1 visible;
- winning M5 visible.

Therefore:

    actor_policy = external
    action_policy = external

This profile means only:

> a stable public action-focus tile candidate is present.

It must never mean "opponent discarded this tile" without independent temporal
actor/action evidence.

### upper_public_single_dev

Geometry:

- `single_face`
- reviewed upper public small-tile zone

The reviewed N target is captured here.

But the same stable-looking component also appears in opening / hand-reference
contexts. Sparse screenshots are insufficient to prove whether each appearance
is a newly added river tile, persistent public row item, or another public UI
state.

Therefore actor/action both remain external.

### player_exposed_group_dev

Geometry:

- `bottom_group`
- reviewed lower player public-group area

Evidence covers:

- P1 P1 P1 Peng;
- stacked P1 P1 P1 P1 added-Kong display;
- S7 S8 S9 Chi;
- M4 M5 M6 Chi;
- P6 P7 P8 Chi.

All reviewed group evidence is player-side, so:

    actor_policy = player

But:

    action_policy = external

because a stable group does not itself distinguish CHI/PENG/KONG or prove when
the transition happened. The existing MeldSnapshot/Action Assembler layers own
that temporal semantic reconstruction.

## Context audit

The current detector was run on every image in the locked 16-sample development
manifest.

Current measured candidate totals:

- raw full-frame geometry candidates: **279**
- central_action_focus selections: **6**
- upper_public_single selections: **2**
- player_exposed_group selections: **18**
- total selected across all three channels: **26**

That is roughly a 90.7% reduction in candidate volume on this development
context set.

Per-frame maxima:

- central_action_focus: **1**
- upper_public_single: **1**
- player_exposed_group: **2**

CI locks the per-frame maxima and requires total selected candidates to remain
<=15% of raw candidate volume.

## What these numbers do NOT mean

They are **not**:

- precision;
- recall on continuous gameplay;
- false-positive rate;
- source-disjoint generalization;
- action classification accuracy.

The 16 frames are already-reviewed development evidence and were used to design
the channels.

The purpose of this audit is only to prove that a broad detector can be narrowed
to a manageable candidate stream before temporal tracking.

## Relationship to Candidate Tracker

Each profile can be converted to the existing `CandidateChannel`.

The safe flow is:

    full-frame detector
      -> development channel filter
      -> Public Candidate Tracker
      -> stable geometry track
      -> external actor/action evidence
      -> RiverSnapshot / other public snapshot
      -> Observer
      -> Action Assembler

For profiles whose actor/action policy is external, callers must not bypass the
external-evidence step.

## Formal promotion boundary

All profiles are:

    development_only = true
    excluded_from_formal_promotion = true

They do not affect Issue #7 formal promotion evidence. A future production
channel must be checked against untouched source-disjoint recordings.

## Next slice

The next evidence need is **continuous real frame sequences**, not more isolated
screenshots.

Use them to measure:

1. stable-channel APPEARED false tracks;
2. disappearance behavior;
3. actor/turn correlation for central action focus;
4. whether upper_public_single represents a persistent row/river and how it
   grows;
5. RiverSnapshot continuity and DiscardRiverObserver precision/recall;
6. public-region tile identity.

Until then, central_action_focus stays action/actor UNKNOWN and Executor stays
off.
