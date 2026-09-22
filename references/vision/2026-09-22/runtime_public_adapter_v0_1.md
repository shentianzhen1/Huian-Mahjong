# Runtime Public Adapter V0.1

Date: 2026-09-22  
Issue: #69  
Status: read-only bridge

## Goal

Connect the existing Runtime Vision V0.2 report to the Public Observer layer
without adding unverified target-room pixel assumptions.

The bridge currently supports the **player/bottom side** because
`dynamic_geometry.py` already reviews that region.

## Data flow

    Runtime Vision V0.2
      dynamic_geometry + runtime_reader
            |
            v
      runtime_public_adapter.py
        - player_meld_snapshot_from_runtime()
        - player_hand_delta_from_runtime()
            |
            v
      MeldSnapshot / RawObservation(HAND_DELTA)
            |
            v
      MeldSnapshotObserver / Public Match Reconstructor

## Player meld snapshot

The runtime reader already emits components whose
`region_candidate == "meld"`.

The adapter re-groups those flattened components using local normalized
geometry only:

- no absolute screen x/y;
- no semantic left/right meld order;
- no fixed group index;
- small vertical overlap is allowed for reviewed stacked 3+1 layouts.

Only stable clusters of 3 or 4 faces become `MeldGroup`.

### Identity policy

Current Runtime Vision V0.2 does **not** have an independently validated
meld-region identity classifier. The runtime reader therefore currently emits
meld components with `tile_id=UNKNOWN`.

The adapter preserves that truth:

    MeldGroup.tiles = (None, None, None)

rather than reusing concealed-hand templates and pretending the region shift is
solved.

If a future runtime reader explicitly emits trusted meld tile IDs, this adapter
will carry them forward without changing its contract.

## Player concealed-hand delta

The adapter compares two stable runtime reports.

It emits `HAND_DELTA` only when `concealed_tile_count` changes.

Always recorded:

- before concealed count;
- after concealed count;
- removed_count;
- added_count;
- runtime frame provenance.

When both reports declare
`all_concealed_tile_ids_trusted=true`, a multiset difference is also computed:

- removed_tiles;
- added_tiles.

The adapter does not decide why the count changed. It does not label the delta
as CHI, PENG, KONG, discard, draw, flower replacement, or any rule action.
Temporal reconstruction remains downstream.

## Current useful capability

The live/read-only player-side chain is now structurally:

    real frame burst
      -> Runtime Vision report
      -> player MeldSnapshot
      -> stable MeldSnapshotObserver
      -> MELD_DELTA

and:

    stable report before/after
      -> player HAND_DELTA

These facts can later be combined with a public discard observation to
reconstruct CHI/PENG/MING_GANG/ADD_KONG.

## Boundaries

Not solved in this adapter:

- opponent river pixel segmentation;
- player river pixel segmentation;
- opponent meld region;
- meld identity recognition;
- AN_GANG visual signature;
- action timing assembler;
- formal independent Vision promotion.

No Rules, AI, Hint Alpha advice, or Executor behavior changes.
`safe_for_executor=false` remains unchanged.

## Next evidence-driven slice

The next useful work requires reviewed real gameplay frames that show:

1. a new player discard entering the river;
2. a new opponent discard entering the river;
3. opponent exposed meld creation;
4. player exposed meld creation if available.

Those frames should be used to calibrate/validate low-level public tile
segmentation before any target-room ROI is frozen.
