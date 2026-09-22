# Public Tile Detector V0.1

Date: 2026-09-22  
Issue: #69  
Status: development geometry intake

## Goal

Find tile-like **public visual candidates** that can later feed the existing:

    Public Tile Detector
      -> River / Meld Observer
      -> Temporal Action Assembler
      -> UNKNOWN-only Hand Timeline
      -> Chinese Match Ledger

V0.1 is deliberately not an action detector.

It does not decide:

- who discarded;
- whether a tile is in a river;
- whether a group is CHI/PENG/KONG;
- tile identity;
- Mahjong legality.

Those semantics remain downstream.

## Real-frame calibration

The development set contains:

- 2 already-reviewed source sessions;
- 5 opponent discard targets;
- 5 player meld targets;
- SHA256-locked committed JPGs;
- pixel-reviewed normalized bboxes.

All ten images are development-only and remain excluded from formal Runtime
Vision promotion.

### Reviewed visual signatures

The bbox review disproved a single-discard-ROI design.

Four opponent discard samples:

- P1
- S9
- M4
- P7

use a large upper-middle response tile.

The N sample is a substantially smaller upper public tile.

Player meld samples show:

- first lower-left 3-tile exposed group;
- a second exposed group farther right;
- stacked 3+1 added-Kong geometry.

## Detector strategy

V0.1 uses a full-frame, low-saturation bright tile-body mask:

- HSV saturation < 105;
- HSV value > 115;
- 3x3 close to reconnect small artwork holes.

Connected components are filtered only by broad normalized geometry.

### Single-face intake

A component with normalized width <= 0.085 and reviewed tile-like height can
become:

    geometry_kind = single_face

This captures the smaller N development target without assuming its absolute
position.

### Bottom group intake

A compact wide component in the reviewed lower public presentation can become:

    geometry_kind = bottom_group

The detector expands the brightness-only box by scale-relative padding because
the mask trims pale/slanted tile borders.

This is a visual group candidate only. It is not automatically a meld action.

### Upper protrusion recovery

In response frames, the large public tile can touch the smaller row below in the
brightness mask and become one oversized connected component.

V0.1 therefore detects:

1. a strong horizontal occupancy jump inside the oversized component;
2. a dense vertical segment in the upper lobe;
3. a scale-valid single-tile candidate.

The result is:

    geometry_kind = upper_protrusion

No fixed x/y ROI or expected tile count is used in the recovery.

## Calibration gates

Vision regression checks the real 10-target set.

Development thresholds:

- discard reviewed bbox coverage >= 0.75;
- meld reviewed bbox coverage >= 0.90;
- <= 30 geometry candidates per calibration frame;
- all 10 reviewed signature classes remain stable.

Expected reviewed signature classes:

- 4 upper_protrusion discard targets;
- 1 single_face discard target;
- 5 bottom_group meld targets.

These are development regression gates, not generalization metrics.

## Identity policy

Every detector candidate currently emits:

    tile_id = UNKNOWN

This is intentional.

The existing hand-region template classifier is not silently reused for public
meld / discard regions. Region-appropriate identity evidence is a later stage.

## Safety / evidence

- `safe_for_hint=false`
- `safe_for_executor=false`
- candidate confidence describes geometry intake only;
- machine candidate geometry never becomes rule evidence automatically;
- reviewed calibration sources remain excluded from formal promotion.

## Next slice

After this geometry intake is stable:

1. collect negative/non-target public frames to measure false candidate load;
2. add temporal candidate tracking so newly appearing public tiles can populate
   RiverSnapshot without a fixed river direction;
3. add region-appropriate public tile identity coverage;
4. replay real sequences end-to-end through Observer -> Assembler -> Ledger.

Do not connect Executor.
