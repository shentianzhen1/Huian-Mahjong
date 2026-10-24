# Real whole-hand diagnostic — 2026-10-07

Status: **same-match development diagnostic only; not a formal holdout**.

This audit uses reviewed checkpoints from one 2026-10-03 real match segment. Adjacent frames and checkpoints from this source stay in one source group and must not be counted as independent validation sources. Raw video and derived crops remain private/local and are not committed.

> 2026-10-08 truth correction: direct re-review of the original source frames and frozen detector crops corrected two Wan labels (`M7 -> M6` at the 20 s ordinary checkpoint and `M5 -> M6` at 30 s) plus a bamboo label (`S7 -> S5` at 40 s and the same visible tile at 46 s). The previous two high-confidence `M6` “wrong accepts” were therefore correct recognitions. Machine-readable authority: `references/vision/2026-10-08/whole_hand_truth_correction_20261003_v0_1.json`.

## Frozen conditions

- Runtime Vision V0.2 detector/crop/template path
- identity threshold: **0.82**, unchanged
- Executor: OFF
- no classifier promotion or Runtime behavior change

## Checkpoints and geometry

Across the selected four baseline checkpoints the detector count matched reviewed truth exactly: **57/57 truth tiles detected, 0 missed detections, 0 extra detections**. The exported ordinary crops did not show systematic crop displacement. This batch therefore points first to identity/appearance robustness rather than concealed-hand geometry.

## Corrected ordinary appearance baseline

The three ordinary-appearance hands contain 43 reviewed tiles. After the 2026-10-08 truth correction:

- raw top-1 correct: **36/43 = 83.72%**
- remaining raw confusion pairs:
  - `S4 -> S6`: 4
  - `M2 -> M3`: 3
- threshold-only accepted predictions: **31/43**, with **31/31 accepted predictions correct** and **0 wrong accepts**
- full current Runtime after source-support gates: **25/43 identities exposed, 25 correct and 0 wrong**
- **0/3 ordinary whole hands are advice-eligible**, because every hand still contains at least one rejected/UNKNOWN identity

The prior `M7 -> M6` and `M5 -> M6` high-confidence error claims are invalidated. Direct source-frame review shows both queried tiles are `M6`. The unresolved `781b...` M6 template still lacks reviewed `original_match_group` lineage and therefore cannot count as independent promotion evidence, but these two samples are not evidence that the template causes wrong accepts.

`P2` remains a separate support problem: the classifier can predict it correctly at high confidence in these checkpoints, but Runtime keeps it UNKNOWN when concealed-domain cross-source qualification is incomplete.

Machine-readable detail: `references/vision/2026-10-07/high_confidence_concealed_wrong_accepts_v0_1.json`.

## Central-edge trim development A/B

`central7` remains development-only and production `TemplateTileClassifier` is unchanged. On the same 43 ordinary crops after truth correction:

- raw top-1: **39/43 = 90.70%**
- accepted at 0.82: **31/43**
- correct accepted: **31/31**
- wrong accepted: **0**
- remaining raw confusions: `M2 -> M3` x3 and `S4 -> S6` x1
- whole-hand advice eligibility remains **0/3**

So the useful product metric still does not improve. **Do not promote central7 into Runtime.**

The historical leave-`source_session`-out development table remains only a development check; `source_session` is explicitly not independent-original-match evidence.

| Scope | Variant | Raw top-1 | Accepted @0.82 | Correct accepted | Wrong accepted |
| --- | --- | ---: | ---: | ---: | ---: |
| pooled concealed | baseline | 95/142 (66.90%) | 51 | 51 | 0 |
| pooled concealed | central7 | 98/142 (69.01%) | 52 | 52 | 0 |
| same region | baseline | 95/142 (66.90%) | 50 | 50 | 0 |
| same region | central7 | 98/142 (69.01%) | 51 | 51 | 0 |

## Shadow + Gold appearance checkpoint

The 46 s source frame was also directly re-reviewed: the concealed tile previously labeled `S7` is `S5`. The shadow/Gold checkpoint remains a revealed same-match development diagnostic, not promotion evidence. Existing handcrafted shadow experiments remain non-promoted; any metric that depended on the old `S7` label must be interpreted through the correction record above and re-derived before reuse.

The core engineering conclusion is unchanged: do not wire one-source shadow thresholds, glyph masks, vertical trims or other handcrafted corrections into Runtime. Learned candidates, if revisited, must use whole-`original_match_group` separation and a different original-match whole-hand validation set.

## Priority after truth correction

1. Keep concealed-hand geometry unchanged for now; this batch does not show a count/crop bottleneck.
2. Focus ordinary identity work on the **real** remaining confusion families: `S4/S6` and `M2/M3`.
3. Do not train or sync the 10/3 frame-1176 slot-15 crop as `M7`; it is `M6`. Recover or collect a genuine second reviewed M7 original-match source.
4. Keep the `781b...` M6 source as unresolved-lineage development data until its original match is recovered; do not quarantine it based on the invalidated M5/M7 examples.
5. Run any candidate classifier on identical reviewed crops grouped by `original_match_group`, and keep the Runtime threshold fixed at 0.82.
6. Add a separate real-match whole-hand holdout and measure exact-hand rate, wrong accepted hands, reject rate and capture-to-advice p50/p95 before classifier promotion.

The dedicated `whole_hand_error_analysis.py` helper should continue to report raw confusion pairs even when later rejected, so classifier selection cannot hide weak boundaries behind abstention.
