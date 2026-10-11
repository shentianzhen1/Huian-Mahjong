# Concealed-hand development result reproducibility audit — 2026-10-12

## Status

**BLOCKED: this session cannot reproduce the reported 43/43 result.** This is an input-availability finding, not a failed recognition run. No synthetic replacement result has been generated, and no Runtime code was changed.

Audited branch: `codex/hint-alpha-local-test-sync-20261004`
Audited parent HEAD: `aad261a58d60aa574ed34b3ada7264c834c10c02`
The audit must be appended to the PR branch only; do not merge PR #126.

## Public source and truth metadata verified

Truth seed:
- Path: `references/vision/2026-10-07/whole_hand_truth_seed_20261003_v0_1.json`
- Blob SHA: `ec8c294661718884b9acda139896039857c437ab`
- Schema: `vision_whole_hand_truth_seed_v0_1`
- Original-match group: `reviewed_match_2026_10_03_recent_real_game`
- Private source video: `ScreenRecording_10-03-2026 22-36-10_1.mov`
- Expected source SHA-256: `e5b8d8e116f67b13b71a1643c5b7f7b26bb4c1e0848a7ba7407d8c5644b0ed14`
- Truth seed has five timestamp samples: 3, 10, 30, 40 and 46 seconds. The 46-second sample is Gold-skinned and explicitly out of scope for the concealed-only fallback probe.
- The reported 43-tile ordinary result aligns with the 10-, 30- and 40-second samples (17 + 13 + 13 visible concealed/draw identities). All are from the same original match and therefore are development evidence, not independent sessions.

Truth correction:
- Path: `references/vision/2026-10-08/whole_hand_truth_correction_20261003_v0_1.json`
- Blob SHA: `b1e17bc73fa6a1716e3c998a8a874f90647da140`
- It explicitly marks the correction as development evidence, keeps threshold 0.82 unchanged, and says same-match evidence is not an independent holdout.

## Evaluator and exact dependencies

Committed evaluator:
- `workspace/vision/tiles_runtime_v0_2/whole_hand_tight_fallback_probe.py`
- Blob SHA at audited HEAD: `9417a2705ee20318006bae5681d3178013103b41`

Focused tests:
- `tests/test_whole_hand_tight_fallback_probe.py`
- Blob SHA at audited HEAD: `ea112d54d4a9eca4733cae362ea19257a2173abc`
- The five tests exercise crop geometry, bounds rejection, primary-accepted identity preservation, UNKNOWN fallback semantics, and rejection of a threshold change. They do **not** execute the private 43-tile evaluation.

To rerun the actual probe, all of these are needed:
1. The exact private source video matching the SHA above, if rebuilding the baseline export.
2. The private `baseline_export.json` generated from that source and the frozen truth seed, including its `crops/<sample_id>/...` image files. The probe reads these crops; metadata alone is insufficient.
3. The exact Runtime dataset tree used for the historical run, including label sidecars and assets, or a verified commit/tree hash that reproduces it.
4. The exact support `original_match_group` argument(s) and the actual command/environment used for the historical run.
5. A saved per-tile output report to reconcile every truth label, primary result, fallback result, confidence, final status, and whole-hand aggregate.

## Availability check in this session

- The current conversation has no uploaded files.
- GitHub contains the truth seed, correction, evaluator and tests, but the private source video and private baseline export/crop directory are not committed (correctly, for privacy).
- No connected live Drive file-download tool is available in this session.
- Library search did not locate the required source video, `baseline_export.json`, or its crop directory.
- Consequently, this session did not execute the 43-tile probe and cannot attest that 43/43 is reproducible here.

## Reported results retained as reported—not rerun

| Measurement | Reported value | Evidence status |
|---|---:|---|
| Candidate correctly accepted | 43/43 | Prior development report; not rerun in this session |
| Candidate wrong accepts | 0 | Prior development report; not rerun in this session |
| Candidate UNKNOWN/rejected | 0 | Prior development report; not rerun in this session |
| Candidate whole hands complete | 3/3 | Prior development report; not rerun in this session |
| Formal Runtime accepted correctly | 25/43 | Same-match diagnostic |
| Formal Runtime wrong accepts | 0 | Same-match diagnostic |
| Formal Runtime UNKNOWN/rejected | 18/43 | Same-match diagnostic |
| Formal Runtime whole hands complete | 0/3 | Same-match diagnostic |

These are not independent blind-test results. The candidate remains development-only and is not wired into formal Runtime. Keep the identity threshold at 0.82, MeldAwareShantenAgent V0.10 unchanged, Hint Alpha read-only and Executor OFF.

## Next reproducible step

Restore the exact private video and baseline export/crops to a local private workspace, verify the video SHA-256, record the dataset tree/commit and support-group arguments, then run the committed evaluator once and archive the complete JSON report locally. Only aggregate metrics and non-sensitive provenance should be synchronized to GitHub; do not commit private video or image crops. If the historical export or its invocation cannot be recovered, rebuild from the pinned truth seed and manually re-review the exported crops before reporting new metrics. A newly rebuilt run must be labeled as a rerun, not represented as the missing historical run.
