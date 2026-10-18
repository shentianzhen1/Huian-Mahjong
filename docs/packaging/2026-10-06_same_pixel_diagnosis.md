# Same-pixel real-video diagnosis (2026-10-06)

Related: #69, #45, #7. Source UI/runner revision: #126 `969e808`.
Development reader compared against #117 diagnostics at `38ed6b8`.
Machine results: `2026-10-06_same_pixel_diagnosis.json`.

## Observed result

The existing private 1108x512 clip was decoded at source times 0–3s, 0.30s
sampling, yielding eight three-frame windows. Both paths use identical sampled
pixel SHA256 arrays. Both reject all eight complete-hand/Gold snapshots. The
development path accepts P3/P8 in the first burst where the package path abstains,
but this does not make the complete snapshot usable. Recognition abstention
therefore also reproduces outside the Windows installer.

The development first-window geometry is stable but counts 15 concealed tiles.
The bottom-left yellow face at [118,440,48,67] is emitted as `gold`, excluded
from concealed hand, and classified as N at confidence 0.084751 (UNKNOWN).
Visual inspection of the private frame shows this face immediately adjoining
the concealed row and a separate opened-Gold indicator at upper left. The
current `_gold_boxes` intake excludes y < 0.78 * image height; its subsequent
single-yellow policy makes a lone lower yellow face the public Gold candidate.
This is a role/geometry mismatch for this actual layout, not an identity fix.

Two first-window S2 candidates at [715,442,48,65] and [765,442,48,65] remain
UNKNOWN at confidence 0.644122 and 0.724970 under unchanged threshold 0.82.
Correct candidate labels below threshold are not accepted recognition.

Sequential package run on Linux: total 4896.083 ms, Runtime/advisory/hash
1252.614 ms, two OCR calls 3428.881 ms, six OCR-reused windows. OCR is about
70% of total in this short diagnostic only; initialization, tiny sample size
and Linux runtime prevent a Windows/live-latency conclusion. The earlier
parallel development run is not used for latency comparison.

## Next bounded experiment

1. Retain this input's SHA/frame/pixel identity. Do not relabel the source as
   an independent holdout or infer original-match lineage from its filename.
2. Separate upper opened-Gold display observations from lower playable
   yellow-skin tiles, testing their role/count before identity. Include negative
   layouts where a separate lower Gold display must stay outside concealed hand.
3. Keep both S2 faces and Gold identity UNKNOWN until their actual classifier
   confidence/domain evidence passes. Do not lower 0.82.
4. Rerun both paths on the same pixels; report geometry, identities, complete
   capability acceptance and OCR timing separately.

This slice records failure evidence only. No pixel/crop, player/room metadata,
rule change, Vision promotion, Executor action or rebuilt EXE is included.
