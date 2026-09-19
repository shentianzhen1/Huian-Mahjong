# Room 541913 Vision seed-8 baseline

Date: 2026-09-19

## Source material

Google Drive room-541913 replay set:

- 3.mp4
- 4.mp4
- 5.mp4
- 9.mp4
- 10.mp4
- 11.mp4
- 12.mp4
- 13.mp4

The eight videos were downloaded successfully and decoded locally. Two exact frame geometries occur:

- 1046x480: 3 / 9 / 11 / 13
- 960x448: 4 / 5 / 10 / 12

Total video duration is about 16m33s.

## Intake

A 0.5 s candidate sampling pass was de-duplicated using mean absolute difference over the lower tile band (threshold 5.0).

- sampled videos: 8
- de-duplicated key frames: 379
- generated ROI crops: 1137 (hand / draw / gold)
- executor gate: CLOSED

Per-video kept key frames:

- 3.mp4: 34
- 4.mp4: 58
- 5.mp4: 70
- 9.mp4: 42
- 10.mp4: 52
- 11.mp4: 37
- 12.mp4: 47
- 13.mp4: 39

Raw frames and ROI images remain local and are not committed.

## Seed labels

One stable early frame around t=10s was visually reviewed from each video to bootstrap the real-label loop.

- approved seed labels: 136
- source groups: 8
- observed tile classes: 31 / 42
- all 31 observed classes have >=2 independent source groups
- all three ROI types have at least one label
- leakage-safe holdout evaluator can run

Currently unseen classes in this seed set:

- S7
- S9
- SOUTH
- F1..F8

These labels are a first-pass visual review by ChatGPT and must be re-reviewed before being treated as final ground truth.

## First leakage-safe template baseline

Method: leave one source group out. The held-out frame never enters the template set.

Overall:

- scorable labels: 136 / 136
- exact tile accuracy: 87.50%
- category accuracy: 94.85%
- confidence >= 0.80 accepted: 125 / 136
- accepted exact accuracy: 90.40%

By region:

- hand_region: 118 / 127 correct = 92.91%
- hand_region at confidence >= 0.80: 113 / 117 correct = 96.58%
- draw_region: 1 / 1 correct, sample too small to interpret
- gold_region: 0 / 8 correct

## Important finding: gold-region domain shift

The prototype NCC template classifier works reasonably on the normal hand tile rendering, but fails completely when a tile is rendered inside the highlighted gold display. Gold crops have a different border/background/scale presentation; matching them directly against ordinary hand templates produces high-confidence wrong answers.

This means overall accuracy must NOT be used as an executor gate. The next Vision work should separate two issues:

1. keep expanding/reviewing normal hand/draw labels;
2. add gold-region-specific normalization or region-specific templates/model data instead of pretending hand templates transfer directly.

## Layout finding

The videos include exposed-meld states. A single fixed 16-slot concealed-hand geometry is suitable for early/unmelded frames, but cannot be blindly applied to every mid-hand frame once exposed meld groups change the bottom-row layout.

For the first reproducible baseline, use stable early/unmelded frames. Melded states should either get separate reviewed profiles/layout states or a future dynamic tile-segmentation layer.

## Next actions

1. re-review the 136 seed labels and freeze them as ground truth;
2. add more draw_region examples from the 379 key frames;
3. collect S7, S9, SOUTH and flower examples;
4. implement/test gold-region normalization or region-aware classification;
5. then run cross-source accuracy plus continuous-frame stability together;
6. keep safe_for_executor=false.
