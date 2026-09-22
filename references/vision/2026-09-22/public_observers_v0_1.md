# Public Observers V0.1 — river and meld snapshot delta

Date: 2026-09-22  
Issue: #69  
Status: read-only development observer layer

## Purpose

This layer converts **already detected public tile geometry / identity candidates**
into stable visual facts:

- one new public discard;
- one new exposed meld group;
- one existing exposed Peng changing from 3 visible faces to 4 visible faces;
- ambiguous / missed transitions that must not be guessed.

It sits between low-level pixel detectors and
`public_match_reconstruction.py`.

## Pipeline

    frame / video
      -> low-level tile / geometry detector
      -> RiverSnapshot / MeldSnapshot
      -> DiscardRiverObserver / MeldSnapshotObserver
      -> RawObservation(DISCARD / MELD_DELTA)
      -> Public Match Reconstructor
      -> CHI / PENG / MING_GANG / ADD_KONG / UNKNOWN
      -> UNKNOWN-only Hand Timeline draft

## Why snapshot delta instead of fixed coordinates

The archived UI review does **not** yet establish:

- exact opponent river ROI;
- river growth direction / wrap direction;
- exact opponent meld-area coordinates;
- absolute meld group ordering.

Therefore V0.1 does not hard-code any of those.

Each public tile/group carries a normalized bounding box. Previous and current
stable snapshots are matched by local geometry. A new discard is emitted only
when:

1. all previous river tiles can still be matched;
2. current stable river count = previous count + 1;
3. exactly one current tile remains unmatched.

The observer does not care whether the river grows left-to-right, right-to-left,
or wraps rows.

## Stability gate

Default `settle_frames=3`.

One animation/transient frame never produces a public action.

The pending snapshot must remain geometrically/identity compatible for the
configured number of frames before it becomes an accepted state transition.

This is intentionally separate from tile-classification accuracy. Stable
identity can still be wrong, so later identity confidence / source-disjoint
gates remain necessary.

### Stream continuity

RiverSnapshot and MeldSnapshot carry a nonnegative stream_epoch.

When the epoch changes, the corresponding observer:

- discards its old accepted baseline;
- clears pending stability state;
- does not compare the first new-epoch snapshot with the old epoch;
- requires the new epoch to settle into a fresh baseline before emitting any
  public action.

This is used by the Public Candidate Tracker when a source-session changes or
the capture gap exceeds its configured maximum.

## Discard river behavior

### New discard

Stable +1 public tile:

    old: [A B C]
    new: [A B C D]

with A/B/C spatially matched

=> emit:

    RawObservation(
      kind=DISCARD,
      tile=D or UNKNOWN,
      actor=player/opponent
    )

If D's identity is unreadable, the discard fact is still retained with
`tile=None`; downstream reconstruction remains UNKNOWN-friendly.

### Claimed / removed tile

A stable river contraction may happen after a claim or UI transition:

    old: [A B C]
    new: [A B]

This does **not** prove CHI/PENG/KONG by itself.

V0.1 records `river_tile_removed_or_claimed`, rebases the public river
baseline, and emits no fake action.

### Missed multi-event transition

If the observer jumps from:

    old: [A]
    new: [A B C]

it cannot recover the exact order of two missed discards.

It emits no discard action, records `river_transition_ambiguous`, and rebases
so future events remain observable.

## Meld snapshot behavior

A MeldSnapshot contains stable public meld groups. Group ordering is not
semantic; matching is geometry-first and tile identities are compared as
multisets rather than display order.

### New group

Stable transition:

    old groups: [G1]
    new groups: [G1, G2]

=> emit one `MELD_DELTA` for G2.

If all tile identities in G2 are readable, `tiles=(...)` is populated.
Otherwise the observation keeps:

- group size;
- bounding box;
- partial tile candidates;
- `tile_identity_complete=false`;

and leaves semantic tiles empty rather than guessing.

### Existing 3 -> 4 group

Stable transition:

    old: XXX
    new: XXXX

=> emit `MELD_DELTA` with `previous_meld=XXX` when identities are complete.

This is only a **visual group transition**. The downstream reconstructor still
needs concealed-hand delta evidence before classifying ADD_KONG.

### Multiple simultaneous group changes

Multiple unmatched/new groups or incompatible changes are
`meld_transition_ambiguous`.

The observer rebases and emits no fabricated action.

## Player / opponent asymmetry

The observer layer does not invent opponent concealed identities.

For later action reconstruction:

- player claim may use exact `removed_tiles`;
- opponent claim may use only `removed_count`;
- newly exposed meld tiles become public after the claim.

This supports reconstruction without violating information visibility.

## End-to-end regression

The V0.1 tests include a minimum public action chain:

    player river +S6
      -> RawObservation(DISCARD S6)

    opponent meld +[S4 S5 S6]
      -> RawObservation(MELD_DELTA)

    opponent concealed count -2
      -> RawObservation(HAND_DELTA removed_count=2)

    reconstruct_claimed_meld(...)
      -> opponent CHI S4 S5 S6, claimed=S6

The resulting action is machine-CORROBORATED but still enters Hand Timeline as
`evidence_level=unknown` until explicit review.

## Non-goals

This PR does not yet:

- locate river pixels directly from a raw screenshot;
- freeze opponent/player river ROIs;
- freeze opponent meld ROI;
- classify AN_GANG;
- infer Hu subtype;
- infer Youjin state from Jin count;
- create rule truth;
- enable Hint advice or Executor.

## Next detector slice

Use reviewed real frames to add the low-level adapters that populate these
snapshots:

1. public discard candidate segmentation / identity;
2. player exposed-meld grouping from current dynamic geometry;
3. opponent public meld grouping;
4. real-video replay evaluation of observer precision/recall;
5. only after that, temporal action assembler and full hand ledger generation.

`safe_for_executor=false` remains unchanged.
