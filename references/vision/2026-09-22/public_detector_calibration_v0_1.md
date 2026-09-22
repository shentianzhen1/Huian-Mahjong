# Public Detector Calibration V0.1

Date: 2026-09-22  
Issue: #69  
Status: real-frame development intake locked; bbox review pending

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

## Why bbox is still null

The archive proves **what is visible** in these frames, but the current ChatGPT
execution environment cannot retrieve the committed JPG bytes into the local
pixel-analysis container.

Therefore V0.1 deliberately stores:

    status = fact_locked_bbox_pending
    bbox = null

for discard/meld detector targets.

No normalized coordinates are invented from textual descriptions.

## Manual/local review workflow

Run from a normal repository checkout:

    python -m workspace.vision.public_detector_calibration \
      --manifest references/vision/2026-09-22/public_detector_calibration_v0_1.json \
      --repository-root . \
      --bbox-template local_bbox_review.json

The tool:

1. validates schema;
2. verifies each committed image SHA256;
3. reports target/source coverage;
4. writes a small bbox-review template containing only the 10 detector targets.

A reviewer then fills normalized:

    [x, y, width, height]

around the reviewed discard tile or exposed meld group.

After review, the manifest can mark that row `bbox_reviewed`.

## Readiness gate

The development Public Tile Detector calibration gate requires, at minimum:

- 5 bbox-reviewed discard samples;
- discard samples from >=2 source sessions;
- 5 bbox-reviewed meld samples;
- meld samples from >=2 source sessions.

The current manifest meets source/fact coverage but intentionally fails bbox
readiness until real pixel boxes are reviewed.

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

1. fill 10 normalized bboxes on already reviewed committed screenshots;
2. use them to test public tile/meld segmentation;
3. add more development frames if failure modes appear;
4. then evaluate real replay sequences through:
   detector -> River/Meld Observer -> Action Assembler -> Hand Timeline -> Match Ledger.

No Rules, AI, Hint Alpha advice, or Executor behavior changes.
