# Room 541913 region-aware Vision baseline

Date: 2026-09-19

## Why this follow-up exists

The first seed report used the original `evaluate_tiles` behaviour, where held-out hand/draw/gold tiles could be matched against one shared template pool. Real target-game recordings show that these three UI regions use different render domains: especially the gold display has a highlighted background/border/scale. Mixing domains makes region shift look like tile-recognition error.

The evaluator now supports `template_scope="same_region"`. This report uses that stricter real-UI baseline.

## Dataset state

Source: room541913 eight-video replay set (3/4/5/9/10/11/12/13.mp4).

Local intake remains:

- 379 de-duplicated key frames
- 1137 ROI crops
- raw frames/ROI images not committed
- safe_for_executor=false

After adding visually reviewed draw-region candidates:

- approved first-pass labels: 168
- source groups: 40
- observed tile classes: 34 / 42
- hand labels: 127
- draw labels: 33
- gold labels: 8
- missing classes: F1, F3, F4, F5, F6, F8, S7, S9
- single-source-only classes: F2, F7

The labels are still first-pass visual review and should be re-reviewed before being frozen as final ground truth.

## Same-region leave-source-group-out baseline

Method:

- hold out one source group at a time;
- never place the held-out group in the template set;
- only compare a test tile against templates from the same UI region;
- if the true class has no same-region example outside the held-out group, report it as unscorable instead of forcing a wrong prediction.

Overall:

- total approved labels: 168
- scorable: 151
- unscorable: 17
- exact tile accuracy: 92.7152%

By region:

### hand_region

- scorable: 126
- unscorable: 1
- exact accuracy: 93.6508%
- confidence >= 0.80 accepted: 117
- accepted exact accuracy: 96.5812%

### draw_region

- scorable: 25
- unscorable: 8
- exact accuracy: 88.00%
- confidence >= 0.80 accepted: 25
- accepted exact accuracy: 88.00%

### gold_region

- scorable: 0
- unscorable: 8

This is the correct current conclusion. The seed set contains eight gold displays, but not enough repeated same-class gold examples across independent source groups to measure gold-region recognition without cross-domain leakage. Therefore gold accuracy is **unknown**, not 0%.

## Interpretation

This is the first useful target-game baseline for the fixed-ROI template prototype:

- normal concealed-hand rendering is already reasonably separable;
- draw rendering is promising but still data-limited;
- gold rendering needs more same-region repeated classes and likely its own normalization/model path;
- exposed-meld states still require reviewed alternate layout profiles or future dynamic segmentation.

These numbers are **not production accuracy** and do not justify Executor activation. They are an offline first-pass baseline over visually reviewed replay frames.

## Next data priority

1. Re-review/freeze current labels.
2. Add draw-region examples, prioritizing classes with only one draw source.
3. Find S7, S9 and missing flower classes F1/F3/F4/F5/F6/F8.
4. Collect repeated same-class gold displays across independent hands/videos.
5. Run continuous-frame stability only after region-aware classification has enough data.
6. Keep Executor closed until accuracy + stability + postprocess gates are reproducible.
