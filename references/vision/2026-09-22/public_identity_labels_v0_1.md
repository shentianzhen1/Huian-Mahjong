# Public Identity Labels V0.1

Date: 2026-09-22  
Issue: #69  
Status: separate development-only public-region data loop

## Why this exists

Public Identity Shadow V0.1 rejected direct reuse of the existing concealed
hand / draw / global template domains for public tile identity.

The project therefore now has a separate identity-label contract for:

- `public_action` — enlarged/focused public tile;
- `public_single` — smaller standalone public tile;
- `public_meld` — one individually reviewed exposed meld face.

This does not modify the existing hand/draw/gold label schema.

## Initial reviewed labels

The first development manifest is:

`references/vision/2026-09-22/public_identity_labels_v0_1.json`

It contains 17 approved labels:

- public_action: 4
- public_single: 1
- public_meld: 12

The 5 standalone public labels are:

- P1
- S9
- N
- M4
- P7

The 12 exposed meld face labels come from four groups that can be reviewed
without ambiguous overlap:

- P1 P1 P1
- S7 S8 S9
- M4 M5 M6
- P6 P7 P8

The reviewed stacked P1 added-Kong sample is intentionally **not** face-approved
in V0.1 because the 3+1 presentation contains overlap/occlusion. It remains
useful group-geometry evidence, but it cannot be silently converted into four
identity crops.

## Provenance rules

Every label stores:

- source calibration sample ID;
- source session;
- source video SHA256;
- source image path;
- source image SHA256;
- frame index / time;
- public identity region;
- tile ID;
- normalized face bbox;
- review status / annotator.

The label validator cross-checks these fields against the locked Public Detector
Calibration rows.

For public_action/public_single labels, the tile bbox must match the reviewed
detector target bbox.

For public_meld labels, the face bbox must be contained inside the reviewed
exposed-group bbox, and the face tile ID must be one of that group's reviewed
expected tiles.

## Current coverage

This first slice covers only 11 of 34 standard classes.

It also has **zero classes independently represented across two source
sessions**.

Therefore:

- runtime_identity_ready = false
- formal_promotion_eligible = false

This is a data-loop proof, not a recognition baseline.

## Local validation / crop export

Validate:

    python -m workspace.vision.public_identity_labels

Export reviewed crops:

    python -m workspace.vision.public_identity_labels \
      --export-crops local_public_identity_crops

The export layout is deterministic:

    local_public_identity_crops/
      public_action/
        P1/
        S9/
        ...
      public_single/
        N/
      public_meld/
        P1/
        S7/
        ...

The exported crops are local working data. They are not a formal promotion
batch.

## What is deliberately NOT done

V0.1 does not:

- train or promote a public classifier;
- lower existing Runtime Vision thresholds;
- reuse hand templates;
- fabricate stacked-Kong face labels;
- call a geometry candidate a discard by position alone;
- mark machine identity as confirmed rule evidence;
- enable Hint or Executor.

Public runtime candidates stay `tile_id=UNKNOWN`.

## Next label/data work

The next useful additions are:

1. more public_action/public_single identities from additional reviewed sessions;
2. cross-session repeats of the same tile class;
3. dedicated face segmentation/review for stacked/tilted public_meld layouts;
4. negative crops and confusing near-neighbor classes;
5. only then freeze a public-region identity evaluation gate.

A future classifier should be evaluated separately by region and source lineage,
not by mixing these labels back into the hand/draw template pool.
