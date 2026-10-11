# Issue #69: meld localisation and scale-sensitive region classification on the 2796-wide layout

Date: 2026-10-12. Status: **diagnostic only, no capability gained.**

This records two things:

1. why own-side exposed-meld localisation is still blocked, what was measured,
   and which approaches were falsified — so the same four dead ends are not
   re-explored;
2. why `region_candidate` for gold must be computed at the original capture
   resolution, which rules out downscaling the detector input as a blanket
   frame-rate optimisation.

Nothing here changes Runtime behaviour, the 0.82 identity threshold, the frozen
detector gates, or Executor state. No raw private pixels enter the repository.

## What was being attempted

Recovering exposed-meld candidate groups from the 2026-10-09 session so that the
15 classes currently short of a second independent original-match group
(`M4 M5 M6 P1 P4 P5 P7 P8 S2 S3 S5 S6 S7 S8 S9`) could be lifted to the
new-match support threshold.

## Measured facts

### Source material

Eight clips, `ScreenRecording_10-09-2026*.mp4`, room 736260, 56,106 frames,
2796x1290, 49.8-59.2 fps. All eight SHA256 values were compared against the 201
known hashes recorded under `references/`; there were **no duplicates**, so this
is genuinely new inventory. It is a single already-opened match, so it is
**not** an Issue #7 blind holdout and cannot support formal promotion.

### Resolution scaling works

Two independently reviewed ROI profiles, `huian_1046x480_v0_2` and
`huian_960x448_v0_2` (a 9% scale difference), yield near-identical normalised
region coordinates:

| profile | hand_region normalised |
| --- | --- |
| 1046x480 | (0.428, 0.852, 0.395, 0.144) |
| 960x448 | (0.428, 0.853, 0.395, 0.143) |

Projected onto a 2796x1290 frame, `hand_region` lands exactly on the concealed
hand and `draw_region` exactly on the drawn tile. **Normalised coordinates carry
across capture resolutions for this layout family**, so a new resolution does
not require re-calibration on its own.

### The detector's meld gates are row-position based

`public_tile_detector` decides whether a blob is a meld group partly from its
row: opponent groups need `y < 0.18 * height`, own groups need
`y > 0.72 * height`. On this layout the opponent meld row sits at roughly
`y = 0.44 * height`, so real groups match neither gate. The opponent meld blob
was measured at `y=690, w=175, h=107`, aspect `1.64`, which is also below the
`1.75` group-aspect gate, so it collapses to `single_face`.

Measured `geometry_kind` distribution over eight sampled frames:

```
single_face  85
top_group     9
bottom_group  5
```

The `bottom_group` hits are a **false positive**: the 1901x141 hint banner at
`y ~ 0.55 * height` satisfies the size window.

### Layout structure

Own exposed melds are **not** on a separate row. They share the concealed-hand
row, occupy roughly its left third, render at a different tile scale than the
smaller opponent row, and grow horizontally as the hand progresses. Gold-
eligible melds additionally carry a corner tag; own-side tiles carry a circular
badge, but that badge is present on hand tiles too, so it does not delimit
individual melds.

### The existing profiles have no meld region

Both reviewed profiles define only `hand_region`, `draw_region` and
`gold_region`. There is **no `meld_region` and no `river_region`**, and the
template inventory under `dataset/tiles_runtime_v0_2/templates/` covers only
`hand`, `draw` and `gold`. Template matching therefore cannot be reused to
locate melds: the asset that would make it work does not exist.

## Approaches falsified

Each was implemented and measured; none produced a usable meld group.

1. **Per-tile x-gap segmentation.** Bright tiles are contiguous; seams are
   narrow while face artwork is dark, so the column profile split each tile into
   fragments. 99 candidate groups were emitted across 24 sampled frames with
   **zero** valid three-face rows.
2. **Morphological closing then block detection.** Median bright-run width
   measured fragments rather than tile faces, so blocks merged up to 206 tiles
   and every candidate was rejected.
3. **Brightness plus warm-chroma masking.** Workable on the opponent row
   (block estimates 16/8/7/20) but collapsed the own row to a 1-3 px sliver.
   Real tile faces range from warm ivory to near-white with cool grey artwork,
   so no single chroma-plus-threshold pair separates tile faces from the UI's
   own white elements.
4. **Manual slot calibration.** Assumed a regular tile pitch. Measured pitch
   across 32 frames gave a coefficient of variation of **0.47-1.39**, where a
   regular grid would be below 0.1, and 33-64 bright runs per frame against
   14-17 actual tiles. There is no stable pitch to calibrate against.

One measurement was also found to be invalid: using the absolute tile-pixel area
of a strip just outside a proposed rectangle as an "overflow" signal. That
quantity is non-zero even when nothing crosses the boundary, so it cannot
distinguish a mis-placed region from a correct one. It was discarded in favour
of direct frame review.

## Invariant: `region_candidate` for gold is resolution-dependent

Found while evaluating whether geometry detection could run on a downscaled
frame to raise frame rate. **It cannot, as a blanket change**, and the reason is
specific enough to record as a constraint.

`detect_dynamic_geometry` classifies each component into a region. Spatial
results are scale-stable: across four probe frames, all 58 detected components
matched between 1.0x and both 0.75x and 0.5x with IoU >= 0.5 and **zero misses**.
Region assignment is not:

```
frame 8600   full   region=gold   gold_skin=False  conf=0.900   nbbox=(0.3752,0.8574,0.0447,0.1333)
            0.75x   region=hand   gold_skin=False  conf=0.920   nbbox=(0.3758,0.8595,0.0439,0.1302)
            0.50x   region=hand   gold_skin=False  conf=0.920   nbbox=(0.3755,0.8605,0.0443,0.1302)
            IoU full vs 0.50x = 0.969
```

The same physical element is detected at the same place, but classified as
`hand` once downscaled. The cause is that the gold region test uses an absolute
pixel height: observed gold components are about `124x172` px at 2796x1290
(aspect 0.721, normalised `0.0443 x 0.1333`). At 0.75x the height falls to about
126 px and crosses the region boundary.

This matters because `runtime_public_adapter` routes a component into the
concealed-hand pool when `region_candidate` is `hand` or `draw_visual`, and
treats gold only when `region_candidate == "gold"` **or** `gold_skin is True`.
On these frames `gold_skin` was `False` for every component at every scale, so
there is no second signal that would recover the classification. A gold tile
routed into the concealed-hand pool would be counted as a hand tile, which
breaks the confirmed physical accounting that the opened gold is one reserved
copy outside the hand and would corrupt structural shanten.

### Consequences

- **The authoritative gold signal must be computed at the original capture
  resolution.** Downscaling the input for the whole detector silently loses it.
- Geometry *position* may be computed at reduced scale; geometry *region
  classification for gold* may not.
- Equivalence between two capture scales must never be assumed from normalised
  coordinates alone. Those carry over, as the ROI-profile comparison shows, but
  absolute-pixel classifiers do not.
- Any future frame-rate work should therefore use a mixed pipeline: locate at
  reduced scale, then re-classify gold at full resolution. The gold region is
  about 0.7% of frame area, so the added cost is negligible.

This document does not implement that pipeline, and no detector threshold was
changed.

## What would actually unblock this

Either path requires human-provided truth, which is consistent with how every
existing ROI profile was produced. Detector or threshold output must not be
substituted for it.

1. **Human-annotated meld boxes.** Box a sample of exposed melds across the
   session and use those to calibrate or learn a locator.
2. **A private slot profile.** The repository already accepts this pattern for
   dense river slots (`source_dense_river_slots_dev_v0_1`, supplied through
   `--dense-profile`, never committed). The same mechanism fits melds, but the
   profile still has to be produced by hand first.

Once a locator exists, face splitting should reuse the reviewed
`prepare_public_meld_faces` / `segment_regular_meld_faces` path rather than new
geometry, and the frozen detector gates should be left unchanged.

## Boundaries

- `formal_promotion_evidence`: false. The session is revealed development data.
- `changes_runtime_behavior`: false. No production module was modified; the
  experimental module written during this work was removed.
- `safe_for_runtime`, `safe_for_hint`, `safe_for_executor`: false.
- Raw footage and crops remain outside the repository.

Session metadata, hashes and the measured region table are recorded separately
in the local intake artifact (not committed).
