# Real whole-hand diagnostic — 2026-10-07

Status: **same-match development diagnostic only; not a formal holdout**.

This audit uses reviewed checkpoints from one 2026-10-03 real match segment. Adjacent frames and checkpoints from this source stay in one source group and must not be counted as independent validation sources. Raw video and derived crops remain private/local and are not committed.

## Frozen conditions

- Runtime Vision V0.2 detector/crop/template path
- identity threshold: **0.82**, unchanged
- Executor: OFF
- no classifier promotion or Runtime behavior change

## Checkpoints

The reviewed checkpoints cover ordinary full hands, a post-PENG shortened hand, a separate draw/Ting state, and a shadowed concealed row plus yellow-Gold draw.

Across the selected four baseline checkpoints the detector count matched reviewed truth exactly: **57/57 truth tiles detected, 0 missed detections, 0 extra detections**. The exported ordinary crops did not show systematic crop displacement. This batch therefore points first to identity/appearance robustness rather than concealed-hand geometry.

## Ordinary appearance baseline

The first three ordinary-appearance hands contain 43 truth tiles.

- raw top-1 correct: **34/43 = 79.07%**
- dominant raw confusion pairs:
  - `S4 -> S6`: 4
  - `M2 -> M3`: 3
  - `M5 -> M6`: 1
  - `M7 -> M6`: 1
- threshold-only accepted predictions: **31/43**; **29/31** accepted predictions correct
- full current Runtime after source-support gates: **25/43** identities exposed, 23 correct and 2 wrong
- **0/3 ordinary whole hands are advice-eligible**, because every hand still contains at least one rejected/UNKNOWN identity

The two ordinary wrong accepts above the frozen 0.82 confidence gate are now pinned exactly:

| Scene | Truth | Prediction | Baseline confidence | central7 confidence |
| --- | --- | --- | ---: | ---: |
| ordinary 16-tile checkpoint | `M7` | `M6` | **0.9200869** | 0.8735002 |
| post-PENG 13-tile checkpoint | `M5` | `M6` | **0.9267217** | 0.8657265 |

Both errors therefore collapse neighboring Wan identities into `M6`. `central7` lowers confidence but still leaves both above 0.82, so it does not fix the product-level error.

`P2` is a separate issue: the classifier predicts it correctly at about 0.90–0.92 confidence in these checkpoints, but Runtime keeps it UNKNOWN because concealed-domain cross-source qualification is incomplete. That is a sample/support gap, not evidence that the P2 visual classifier itself is failing.

Machine-readable detail: `references/vision/2026-10-07/high_confidence_concealed_wrong_accepts_v0_1.json`.

## M6 max-exemplar risk

The current template classifier scores a candidate class by the **maximum** normalized cross-correlation over that class's available exemplars. This means one unusually similar `M6` template can dominate the class confidence even if other sources do not agree.

A development-only provenance probe now reports the winning exact template, per-source-session maxima, second-source score, top-two-source mean and top1/top2 class margin: `workspace/vision/tiles_runtime_v0_2/template_source_consensus_probe.py`.

This probe deliberately does **not** treat two `source_session` values as two independent original matches. Exact original-match lineage remains required before source consensus can become an acceptance rule.

## Central-edge trim development A/B

A development-only candidate named `central7` adds one step **after** the existing bright tile-face normalization: trim 7% from each horizontal edge and 4% from each vertical edge before the same grayscale/equalization/template comparison. The production `TemplateTileClassifier` is unchanged.

On the same 43 ordinary real-match crops, central7 improved raw top-1 from **34/43 (79.07%)** to about **37/43 (~86%)** and removed the four observed `S4 -> S6` raw errors. However, the useful result at the frozen gate did not improve: it remained **31/43 accepted, 29 correct, 2 wrong**, and **0/3 exact whole hands** were advice-eligible.

A historical leave-`source_session`-out diagnostic on the tracked Runtime V0.2 reviewed crops also showed no regression, but it is only a development check; a `source_session` is explicitly **not** independent-original-match evidence.

| Scope | Variant | Raw top-1 | Accepted @0.82 | Correct accepted | Wrong accepted |
| --- | --- | ---: | ---: | ---: | ---: |
| pooled concealed | baseline | 95/142 (66.90%) | 51 | 51 | 0 |
| pooled concealed | central7 | 98/142 (69.01%) | 52 | 52 | 0 |
| same region | baseline | 95/142 (66.90%) | 50 | 50 | 0 |
| same region | central7 | 98/142 (69.01%) | 51 | 51 | 0 |

Decision: **do not promote central7 into Runtime**. Keep it as a reproducible candidate rather than treating raw top-1 improvement as product progress.

## Shadow + Gold appearance checkpoint

At the shadow checkpoint the hand remains structurally correct (13 concealed + 1 draw), but the UI changes appearance: the concealed row gains a strong gray horizontal shadow band near the tile bottoms and the drawn `P9` uses the yellow Gold skin.

Current baseline:

- raw top-1 correct: **4/14 = 28.57%**
- Runtime accepted identities: **0/14** at the frozen 0.82 gate
- every identity is therefore blocked by the fail-closed policy

The shadow is not merely a vague brightness shift. A paired development measurement computes, after the existing face normalization, the side-background grayscale difference `bottom(y=82–100%) - middle(y=35–55%)`:

- ordinary checkpoints: medians about **-3.5 to -6.5**; worst observed ordinary value about **-35**
- shadow checkpoint: median **-68**, range **-73 to -67** across all 13 concealed tiles

A development threshold of `-50` cleanly separates this one revealed source, but it is **not** promoted to Runtime.

### Handcrafted shadow probes

Three same-match 40s→46s paired feature probes were compared on the identical 13-tile truth sequence:

- current grayscale-style reproduction: about **6/13** exact
- simple vertical trim removing the bottom band: **9/13** exact
- glyph-focused binary mask: **12/13 = 92.31%** exact, with only `M3 -> M2` remaining

The 12/13 number initially looked promising, but a tracked cross-source check disproved its suitability as an identity classifier. On **142 tracked non-Gold concealed labels** under leave-`source_session`-out development evaluation:

- ordinary baseline raw top-1: **95/142 = 66.90%**
- glyph-mask raw top-1: **10/142 = 7.04%**

Many unrelated classes collapse toward `P5`/`P3`-like binary shapes. Therefore the 12/13 paired result measures **same-source style invariance**, not cross-source tile-identity separability.

Additional handcrafted attempts — bottom-band brightness compensation, affine/gain correction, edge/HOG/Sobel/Canny/CLAHE/adaptive-threshold variants — topped out around **9/13** on the same revealed pair and did not justify more Runtime preprocessing complexity.

**Decision:** reject glyph-mask as a standalone classifier/general template bank. Keep the explicit shadow-state measurement only as a development diagnostic candidate. Do not wire the `-50` appearance threshold, glyph mask, vertical trim, or any handcrafted correction into Runtime.

Machine-readable detail: `references/vision/2026-10-07/concealed_shadow_pair_diagnostic_v0_1.json`.

## Learned shadow candidate

The next shadow-identity experiment reuses the existing development-only `MobileNetV3-Small` feasibility path rather than introducing another classifier architecture. Its training augmentation should explicitly include the observed bottom-shadow band in addition to the existing brightness, slight translation/scale and yellow-Gold variants.

Boundaries remain strict:

- pretrained features only; do not substitute randomly initialized weights
- whole `original_match_group` is the independence unit when reviewed lineage exists
- unresolved-lineage sources remain excluded in strict evaluation
- candidate cosine scores are **not** calibrated Runtime confidence and must not be compared to 0.82 as an acceptance rate
- Runtime template path, 0.82 gate, Hint Alpha behavior and Executor remain unchanged
- promotion requires a different original-match whole-hand validation set and no increase in wrong accepted hands

## Priority from this diagnostic

1. Keep concealed-hand geometry unchanged for now; this batch does not show a count/crop bottleneck.
2. Audit the `M5/M7 -> M6` high-confidence collapse with exact winning-template provenance and reviewed original-match source consensus; do not solve it by ad-hoc threshold changes.
3. Add the real observed bottom-shadow appearance as deterministic **training augmentation** to the existing pretrained-MobileNet development runner; do not create another handcrafted Runtime branch.
4. Run template vs pretrained-MobileNet on the same reviewed crops, grouped by `original_match_group`, once lineage coverage and pretrained weights permit a valid A/B.
5. Validate the shadow appearance state and any learned candidate on a **different original match** before any Runtime switch.
6. Recover or collect independent concealed sources for remaining support/lineage gaps, including P2.
7. Add a separate real-match whole-hand holdout and measure exact-hand rate, wrong accepted hands, reject rate and capture-to-advice p50/p95 before classifier promotion.

The dedicated `whole_hand_error_analysis.py` helper reports raw confusion pairs even when later rejected, so classifier selection cannot hide weak boundaries behind abstention.
