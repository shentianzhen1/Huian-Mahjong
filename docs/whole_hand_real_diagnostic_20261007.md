# Real whole-hand diagnostic — 2026-10-07

Status: **same-match development diagnostic only; not a formal holdout**.

This audit uses four reviewed checkpoints from one 2026-10-03 real match segment. Adjacent frames and checkpoints from this source remain one `original_match_group`; they must not be counted as independent validation sources. Raw video and derived crops remain private/local and are not committed.

## Frozen conditions

- Runtime Vision V0.2 detector/crop/template path
- identity threshold: **0.82**, unchanged
- Executor: OFF
- no classifier promotion or Runtime behavior change

## Checkpoints

The four checkpoints cover:

1. ordinary 16-tile concealed hand;
2. post-PENG 13-tile concealed hand;
3. 13 concealed + independent draw with Ting prompt decoration;
4. 13 concealed + yellow Gold draw while the hand uses the shadowed UI appearance.

Across all four checkpoints the detector count matched reviewed truth exactly: **57/57 truth tiles detected, 0 missed detections, 0 extra detections**. The exported classification crops were visually reviewed; the normal checkpoints did not show systematic crop displacement. This batch therefore points first to identity/appearance robustness rather than concealed-hand geometry.

## Ordinary appearance baseline

The first three checkpoints contain 43 truth tiles under the ordinary hand appearance.

- raw top-1 correct: **34/43 = 79.07%**
- dominant raw confusion pairs:
  - `S4 -> S6`: 4
  - `M2 -> M3`: 3
  - `M5 -> M6`: 1
  - `M7 -> M6`: 1
- threshold-only accepted predictions: 31/43; 29/31 accepted predictions correct
- the full current Runtime is stricter because it also enforces source-support gates: 25/43 identities are exposed as accepted, 23 correct and 2 wrong
- **0/3 ordinary whole hands are advice-eligible**, because every hand still contains at least one rejected/UNKNOWN identity

`P2` is a useful distinction: the classifier predicts it correctly at about 0.90–0.92 confidence in these checkpoints, but Runtime keeps it UNKNOWN because concealed-domain cross-source qualification is incomplete. That is a sample/support gap, not evidence that the P2 visual classifier itself is failing.

## Central-edge trim development A/B

A development-only candidate named `central7` adds one step **after** the existing bright tile-face normalization: trim 7% from each horizontal edge and 4% from each vertical edge before the same grayscale/equalization/template comparison. The production `TemplateTileClassifier` is unchanged.

On the same 43 ordinary real-match crops, central7 improved raw top-1 from **34/43 (79.07%)** to about **37/43 (~86%)** and removed the four observed `S4 -> S6` raw errors. However, the result that matters for Hint Alpha did not improve at the frozen gate: it remained **31/43 accepted, 29 correct, 2 wrong**, and **0/3 exact whole hands** were advice-eligible.

A second historical leave-`source_session`-out diagnostic was run on the tracked Runtime V0.2 reviewed crops. This is only a regression check; a `source_session` is explicitly **not** counted as independent-original-match evidence.

| Scope | Variant | Raw top-1 | Accepted @0.82 | Correct accepted | Wrong accepted |
| --- | --- | ---: | ---: | ---: | ---: |
| pooled concealed | baseline | 95/142 (66.90%) | 51 | 51 | 0 |
| pooled concealed | central7 | 98/142 (69.01%) | 52 | 52 | 0 |
| same region | baseline | 95/142 (66.90%) | 50 | 50 | 0 |
| same region | central7 | 98/142 (69.01%) | 51 | 51 | 0 |

Decision: **do not promote central7 into Runtime yet**. It is not a regression on this historical diagnostic and gains one safe accepted crop, but it does not reduce the two current real-match wrong accepts, does not improve whole-hand exact eligibility, and does not address the shadow/Gold appearance collapse. Keep it as a reproducible candidate rather than treating raw top-1 improvement as product progress.

The reproducible runner is `workspace/vision/tiles_runtime_v0_2/template_preprocess_ab.py`. It fixes the comparison threshold at 0.82, uses identical query crops for baseline and candidate, and marks `source_session` evaluation as development-only.

## Shadow + Gold appearance checkpoint

At the fourth checkpoint the reviewed hand is structurally detected correctly (13 concealed + 1 draw), but the displayed appearance changes: the concealed row is shadowed and the drawn P9 uses the yellow Gold skin.

- raw top-1 correct: **4/14 = 28.57%**
- Runtime accepted identities: **0/14** at the frozen 0.82 gate
- every identity is therefore blocked, as intended by the fail-closed policy

This is a separate appearance-domain problem and should not be averaged away as ordinary template noise. Training/evaluation needs explicit shadow and Gold-skin coverage.

## Priority from this diagnostic

1. Keep concealed-hand geometry unchanged for now; this batch does not show a count/crop bottleneck.
2. Diagnose the **two high-confidence ordinary wrong accepts** first; improving raw top-1 without removing them is not enough.
3. Treat the shadowed-hand / yellow-Gold appearance state as an explicit robustness domain; test normalization/augmentation while keeping 0.82 frozen.
4. Recover or collect an independent concealed P2 source so correct high-confidence P2 predictions can pass the existing support gate without lowering 0.82.
5. Continue strengthening `M2/M3` and `M5/M7/M6`; central7 alone is insufficient even though it helped the raw `S4/S6` boundary.
6. Compare template vs learned candidate on the **same reviewed crops**, grouped by `original_match_group`; only promote after an independent match shows better whole-hand exact/coverage without increasing wrong accepts.
7. Capture-to-advice p50/p95 remains a separate acceptance item; this offline diagnostic does not claim end-to-end live latency.

The dedicated `whole_hand_error_analysis.py` helper reports all raw confusion pairs, including wrong top-1 predictions later rejected below 0.82, so classifier selection cannot hide weak boundaries behind abstention.
