# Independent exposed-meld crop coverage — development audit

Issue #69 / Draft PR #117. This is a source-locked counterexample to promoting
the Hand 8 `body_context + two-pixel seam` crop as a universal FLAT-meld path.

## Source and comparison

- Independent original match: `reviewed_recording_14`, `14.mp4`, exact source
  SHA-256 `f24898ecee56803c09bead267150a590143c043941d3287f436ed6e89930f51d`.
- Reviewed S2–S3–S4 group-only crop: repository
  `special_14_s234.jpg`, SHA-pinned in detector calibration. At frames
  2549/2552/2555, image-match scores are 0.995550/0.998594/0.998266, and
  the reviewed crop locates at `[95,410,229,475]` (xyxy).
- The public detector independently emits `[97,403,130,73]` (xywh) on all
  three frames. The reviewed crop locates the audit target and scores output;
  its boundaries do **not** construct detector/candidate crop edges.
- Metric: fraction of each *equal-third reviewed-crop rectangle* covered by
  the candidate face rectangle. This is a coarse geometry proxy, **not**
  pixel-exact tile-body coverage or identity accuracy.

| Candidate | Three-frame per-face coverage, min–max | Observation |
| --- | --- | --- |
| Detector raw thirds | 0.9556–1.0000 | Wide original crop preserves most reviewed rectangle. |
| Detector raw + 2-pixel seam | 0.9556–1.0000 | Seam context cannot restore outer boundaries. |
| Tight body + vertical context | 0.7990–0.8379 | Outer faces/vertical border lose coverage. |
| Tight body + vertical context + seam | 0.7990–0.8769 | Seam helps middle face but not outer edges. |

The tight-body context crop is `[99,414,225,471]` on frame 2549 and
`[99,414,227,471]` on 2552/2555. Thus the Hand 8 fix has an independent-source
geometry regression relative to the reviewed crop. No claim is made that the
missing pixels contain discriminative glyphs; actual source-disjoint identity
performance remains unmeasured because S2/S3 lack other-match reference coverage.

## Decision and next gate

Do not promote this candidate into Runtime or replace the existing FLAT
splitter. Before another identity A/B, define a geometry-only outer-border
retention check on reviewed groups and require the detector-derived crop to
preserve all three visible tile bodies. Re-evaluate Hand 8 S789 and this
independent S234 side by side, plus tilted/opponent/STACKED cases with explicit
abstention. Choose no new parameter from this inspected pair as formal holdout
evidence. UNKNOWN/Hint-read-only/Executor-OFF policy remains unchanged.

Reproduction: run `python -m workspace.vision.audit_independent_meld_crop_coverage
--video <private exact-SHA 14.mp4> --output <private output.json>` from the
repository root. Raw video and decoded frames remain private. This result is
development-only, not a measured public-meld accuracy or promotion threshold.
