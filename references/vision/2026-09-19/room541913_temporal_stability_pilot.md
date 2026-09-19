# Room 541913 temporal stability pilot

Date: 2026-09-19

## Goal

Measure whether the current hand-region template prototype produces temporally consistent tile identities on real target-game video, while keeping this metric separate from recognition accuracy.

## Method

Source videos: room541913 replay set.

For each video, a reviewed seed frame near t=10s supplies the slot-level reference labels. Around that point, frames were sampled at 0.1s spacing and retained only when the whole hand ROI remained visually stable relative to the reviewed seed (mean absolute pixel difference < 2.0).

The classifier used only approved `hand_region` templates and excluded that video's own t=10 seed group from its template pool, so the sequence was not merely matching against the exact reviewed image.

Six videos had at least ten sufficiently stable frames around the reviewed state:

- 3.mp4
- 4.mp4
- 9.mp4
- 10.mp4
- 11.mp4
- 12.mp4

5.mp4 and 13.mp4 changed state too close to the reviewed t=10 frame and were excluded from this pilot rather than mixing game-state transitions into the stability metric.

## Result

- stable sequences: 6
- frames per sequence: 10
- reviewed hand slots: 96
- slots with agreement >= 0.80: 96 / 96
- stable fraction: 100%
- mean per-slot agreement: 100%
- majority-vote identity correct against reviewed seed labels: 92 / 96 = 95.83%

Per video:

- 3.mp4: 16/16 stable; 16/16 majority identity correct
- 4.mp4: 16/16 stable; 14/16 correct
- 9.mp4: 16/16 stable; 14/16 correct
- 10.mp4: 16/16 stable; 16/16 correct
- 11.mp4: 16/16 stable; 16/16 correct
- 12.mp4: 16/16 stable; 16/16 correct

The four stable-but-wrong slots were:

- 4.mp4 slot 1: true P4, voted P2, agreement 100%
- 4.mp4 slot 9: true S4, voted S3, agreement 100%
- 9.mp4 slot 0: true P2, voted S2, agreement 100%
- 9.mp4 slot 1: true P2, voted S2, agreement 100%

## Interpretation

This pilot demonstrates why temporal agreement and recognition accuracy must remain separate gates. The prototype can be perfectly stable across unchanged frames while consistently choosing the wrong class.

The good news is that temporal flicker is not currently the primary problem on static concealed-hand states. The next useful work is class separation / template quality / label coverage, especially known confusions such as P4<->P2, S4<->S3 and P2<->S2.

This is not an Executor gate:

- labels are still first-pass reviewed;
- only six stable early concealed-hand sequences are included;
- exposed meld layouts are not covered;
- draw and gold temporal stability are not yet established;
- safe_for_executor remains false.
