# Public Detector Calibration V0.1

Date: 2026-09-22  
Issue: #69  
Status: real-frame development intake locked; 10 detector bboxes pixel-reviewed

## What is locked

Two previously reviewed target-room replay sessions are now registered as a
development calibration set:

- 66fe863f_youjin100
- b3892b34_zimo68

The manifest stores:

- source video SHA256;
- committed evidence image path;
- image SHA256;
- frame index;
- replay timestamp;
- actor;
- detector target;
- expected public tile / exposed meld identity when directly reviewed;
- annotation status;
- notes about replay overlay / evidence limits.

The file is:

`references/vision/2026-09-22/public_detector_calibration_v0_1.json`

## Current detector-target inventory

Public Tile / Meld calibration facts:

- 5 opponent discard frames across 2 source sessions:
  - P1
  - S9
  - N
  - M4
  - P7
- 5 player exposed-meld frames across 2 source sessions:
  - P1 P1 P1 Peng
  - P1 P1 P1 P1 stacked added-Kong display
  - S7 S8 S9 Chi
  - M4 M5 M6 Chi
  - P6 P7 P8 Chi

Supporting non-bbox facts:

- 3 player hand references;
- 1 Youjin animation reference;
- 2 settlement references.

## Pixel bbox review completed

The 10 detector targets were exported from the locked repository images through
a one-time GitHub Actions artifact, then verified against the manifest SHA256
values before review.

All ten source JPGs are 1046 x 480.

The review used the actual pixels, not textual descriptions. The normalized
bbox convention is:

    [x / 1046, y / 480, width / 1046, height / 480]

The manifest now marks the 5 discard and 5 meld targets:

    status = bbox_reviewed

The review also exposed an important detector fact: opponent discard visuals are
not a single fixed ROI.

- P1 / S9 / M4 / P7 appear as a large upper-middle response tile in the
  reviewed frames.
- N is a much smaller public tile near the upper area.
- Player meld groups are in the lower public area, with the added-Kong sample
  using a true stacked 3+1 display.

Therefore Public Tile Detector V0.1 must remain geometry-first and cannot freeze
one absolute discard box.

## Re-review workflow

The existing helper still supports future pending samples:

    python -m workspace.vision.public_detector_calibration \
      --manifest references/vision/2026-09-22/public_detector_calibration_v0_1.json \
      --repository-root . \
      --bbox-template local_bbox_review.json

For the current manifest, the generated template is empty because all detector
targets have already been reviewed.

## Readiness gate

The development Public Tile Detector calibration gate requires, at minimum:

- 5 bbox-reviewed discard samples;
- discard samples from >=2 source sessions;
- 5 bbox-reviewed meld samples;
- meld samples from >=2 source sessions.

The current manifest now passes this **development** bbox-readiness gate.

This does not make the detector formally promoted.

## Formal promotion separation

Every sample in this manifest is:

    excluded_from_formal_promotion = true

Reason: these recordings have already been reviewed and have influenced project
design and rule analysis.

Even after bbox annotation and detector tuning, they remain development
evidence.

Runtime Vision formal promotion still requires the separate untouched
source-disjoint batch defined by Issue #7 / independent_batch_lock.py.

## Why this matters for #69

The reconstruction architecture is no longer blocked by an undefined data
collection task.

The next low-level work is now concrete:

1. run Public Tile Detector V0.1 against the 10 reviewed target bboxes;
2. add more development frames for failure modes and non-target negatives;
3. add public tile identity only with region-appropriate evidence;
4. evaluate real replay sequences through:
   detector -> River/Meld Observer -> Action Assembler -> Hand Timeline -> Match Ledger.

No Rules, AI, Hint Alpha advice, or Executor behavior changes.
