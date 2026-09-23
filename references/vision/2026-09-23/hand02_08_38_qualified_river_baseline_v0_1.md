# Issue #69 — Hand-2 early river replay, development V0.1

**Read-only, source-locked development replay.** This second hand belongs to the **same original recorded match** as hand 1. It is **not** an independently sourced Vision holdout. Original video, Drive identifiers, screenshots, private crops, proposed tile names and private traces are not stored in GitHub.

## Reviewed evidence and procedure

- Session `match_evidence_001_hand_02`; source SHA256 `1597ef429288ad50ce26340fcda580c17c735cf3875845c4c309db5652853b22`; resolution 960 × 448.
- Independently checked source-local opponent/player river zones for **frames 250–1100** (851 continuous frames). Outside this span, the manifest fails closed. Later river reflow remains unreviewed; never generalize the ROIs to another recording.
- Frozen manual *development* truth at frame **299 opponent, 491 player, 690 opponent, 987 player**. The preceding development runs had already explored frames 450–1100, so this expanded replay is **not blind**. Human truth leaves tile and independent turn UNKNOWN.
- Machine run decodes all 851 SHA-verified frames, full-frame detector → source-qualified river geometry → tracker → dual RiverObserver → action assembler, then separately loads frozen truth only for evaluation.

## Reproduced machine results

| Measurement | Count |
|---|---:|
| Decoded continuous source frames | 851 |
| Full-frame candidate-frame instances | 12,588 |
| Qualified river candidate-frame instances | 1,934 |
| Stable track-frame instances | 1,924 |
| Stable tracks appeared / disappeared | 6 / 2 |
| Opponent / player river-growth observations | 2 / 2 |
| DISCARD-kind machine geometry candidates | 4 |
| UNKNOWN-graded candidates / strict abstentions | 4 / 4 |
| Known machine tile identities | 0 |
| Strict verified true positives / false negatives | 0 / 4 |

Machine-only candidate times: approximately **10.448 s opponent, 17.103 s player, 23.966 s opponent, 34.207 s player**. They occur near the four frozen visual river changes. These are **not** four verified end-to-end actions. With zero concrete strict predictions, precision and actor accuracy are undefined; do not claim a perfect hit rate or a zero false-positive rate.

The private unlabeled review queue exported **six crops**, including **two potential repeated physical tiles** due to adjacent-face splitting. Separate SHA and pixel comparison against the actual source decoded frames passed **6/6**. All six crop identities remain **proposed, zero approved**; none is permitted to feed the runtime public classifier.

## Next gate

Review the six private crops alongside source frames and adjudicate repeats; obtain truly independent recording sources, broaden approved public tile classes and separate turn cues. No Rules/AI changes, no Vision promotion and **Executor remains off**.

Private-only reproduction (never check in video or output trace):

    python -m workspace.vision.real_video_river_replay --video /private/second-hand.mp4 --manifest references/vision/2026-09-23/hand02_early_river_geometry.development.json --first-frame 250 --last-frame 1100 --truth references/vision/2026-09-23/hand02_08_38_action_truth.development.frozen.json --output /private/hand02_trace.json
