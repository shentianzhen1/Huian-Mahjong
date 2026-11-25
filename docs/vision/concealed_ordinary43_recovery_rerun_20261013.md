# Concealed ordinary-43 recovery rerun — 2026-10-13

## Status

**Formal baseline and historical development-only 43/43 candidate are both reproduced.**

This is a recovery rerun from SHA-qualified private 2026-10-03 and 2026-09-26 sources. It is development evidence from already-revealed original matches and is **not** an independent holdout or Runtime promotion result.

Frozen boundaries remain unchanged:
- Runtime identity threshold: **0.82**
- CurrentAgent: **MeldAwareShantenAgent V0.10**
- Hint Alpha: read-only
- Executor: OFF
- PR #126: Draft / unmerged

No Runtime recognition logic was changed.

## Recovered execution inputs

Query source:
- filename: `ScreenRecording_10-03-2026 22-36-10_1.mov`
- SHA-256: `e5b8d8e116f67b13b71a1643c5b7f7b26bb4c1e0848a7ba7407d8c5644b0ed14`
- original-match group: `reviewed_match_2026_10_03_recent_real_game`

Support source:
- filename: `ScreenRecording_09-26-2026 22-26-47_1.mp4`
- SHA-256: `05ef070ea185e7c224126eadd527e77075f8b85e86ed49326d981ead81fb5738`
- original-match group: `reviewed_match_2026_09_26_eight_hand`
- source session: `session_real_20260926_eight_hand`

Runtime payload:
- recovered from the current Windows test installer artifact for PR #126 HEAD `f7bcf623195edb651ff9ad06164c881b49798909`
- installer artifact id: `11760039064`
- artifact digest: `sha256:4fed2dc35f83611a5860c2487bf6cf338a9df67fec3da6522cdce2ac925ed28a`
- extracted Runtime dataset contained 147 template assets plus the packaged reviewed label sidecars

The committed `whole_hand_baseline_export.py` and `whole_hand_tight_fallback_probe.py` were used for the rerun.

## Ordinary 43-tile denominator recovery

Historical correction and frozen fallback evidence identify the three ordinary checkpoints at 20 s, 30 s and 40 s:
- t20: `real_20261003_t20_normal_16`
- t30: `real_20261003_t30_post_peng_13`
- t40: `20261003-seg-shae5b8-t40.0`

Their reviewed visible identities are 16 + 13 + 14 = **43**.

The t20 hand was recovered from the SHA-qualified source and pinned intake/correction evidence. In particular:
- frame 1176 slot 2 = P2
- frame 1176 slot 13 = M2
- frame 1176 slot 15 = M6, not M7
- full reviewed order:
  `P1 P1 P2 P2 P3 P4 P4 P6 P6 S4 S5 S7 M1 M2 M3 M6`

The older 2026-10-12 dependency-audit sentence that described the 43 denominator as 10 s + 30 s + 40 s is stale provenance text. The exact aggregate reproduction and the frozen fallback report both identify the recovered denominator as 20 s + 30 s + 40 s.

## Exact formal Runtime baseline reproduction

Recovered ordinary set:
- truth tiles: **43**
- raw template Top-1 correct: **36/43**
- raw confusions:
  - `S4 -> S6`: **4**
  - `M2 -> M3`: **3**
- confidence-only >= 0.82: **31/43 accepted**
- confidence-only accepted correct: **31/31**
- full Runtime exposed: **25/43**
- full Runtime correct: **25**
- full Runtime wrong accepted: **0**
- full Runtime UNKNOWN/rejected: **18**
- whole hands complete for advice: **0/3**

These values exactly match the corrected historical formal baseline.

## Historical development candidate recovered

Commit `f88171bf762f2c76158a4f7620d8d05aa7122a7a` froze the previously missing candidate recipe. It uses Sep-26 source-qualified development support from:
- `references/vision/2026-10-08/reviewed_tile_intake_staging_20260926_m2.jsonl`
- `references/vision/2026-10-08/reviewed_tile_intake_staging_20260926_support_expansion.jsonl`

Support classes:
- M1
- M2
- P2
- S3
- S4
- S7

The two manifests contain **10 development-only support crops** from the single Sep-26 original match.

All 10 assets were rebuilt directly from the recovered SHA-qualified Sep-26 video using the frozen `source_frame + bbox` values. Every rebuilt PNG matched its historical `asset_sha256` exactly: **10/10 byte-hash matches**.

This proves the recovered support pixels are the same historical candidate inputs, not approximate replacements.

## Reproduced candidate primary path

A development-only dataset copy was built from the current packaged Runtime dataset plus the 10 recovered Sep-26 support crops and frozen staging rows. The formal Runtime dataset itself was not modified.

Running the baseline exporter with that candidate dataset reproduces the frozen historical primary-path result exactly:
- primary accepted correct: **35/43**
- primary wrong accepted: **0**
- primary rejected: **8**
- whole hands complete: **0/3**

Per hand:
- t20: 14/16 correct accepted, 2 rejected
- t30: 11/13 correct accepted, 2 rejected
- t40: 10/14 correct accepted, 4 rejected

Remaining primary rejections:
- M2: **3**
- S3: **1**
- S4: **4**

## Exact primary-first tight-fallback reproduction

The committed `whole_hand_tight_fallback_probe.py` was run against the candidate baseline using support group `reviewed_match_2026_09_26_eight_hand`.

Result:
- truth tiles: **43**
- primary accepted: **35**
- fallback attempted: **8**
- fallback accepted: **8**
- fallback correct: **8**
- fallback wrong: **0**
- final accepted correct: **43/43**
- final wrong accepted: **0**
- final UNKNOWN/rejected: **0**
- whole hands complete: **3/3**

The eight recovered fallback accepts were:
- t20 slot 9: S4 @ 0.939439
- t20 slot 13: M2 @ 0.962027
- t30 slot 7: S4 @ 0.935893
- t30 slot 10: M2 @ 0.960297
- t40 slot 7: S3 @ 0.824358
- t40 slot 8: S4 @ 0.869313
- t40 slot 11: M2 @ 0.822403
- t40 slot 13: S4 @ 0.855793

Every fallback still passed the unchanged 0.82 identity threshold and existing source-support gate. No class-specific threshold or override was introduced.

This reproduces the historical `concealed_source_disjoint_fallback_ab_v0_1` aggregate exactly:
- **43/43 accepted correctly**
- **0 wrong accepted**
- **0 rejected**
- **3/3 complete hands**

## Interpretation

The historical 43/43 result is now reproducible and its missing dependency is resolved.

It came from:
1. source-qualified Sep-26 appearance support added only to a development candidate dataset;
2. current expanded primary classification crop first;
3. tight detector crop only when primary remained UNKNOWN;
4. unchanged 0.82 threshold and existing identity/source-support gates.

It did **not** come from:
- lowering the threshold,
- overriding already accepted Runtime identities,
- training on the Oct-3 query crops,
- changing Runtime production templates,
- changing V0.10,
- enabling Executor.

The negative-control warning still stands: using tight crop as the global classifier input produced high-confidence M3->M2 wrong accepts around 0.842–0.844 on the same revealed batch. Primary-first ordering is therefore part of the candidate definition.

## Evidence boundary and next gate

This exact 43/43 reproduction is still **same-development-set evidence**, not formal promotion evidence:
- Oct-3 was repeatedly inspected during development.
- Sep-26 support and Oct-3 query are different original matches, but the query is not a fresh untouched holdout.
- Same-source adjacent frames never count as independent sessions.

Next product gate:
1. freeze this reproduced candidate without further tuning on Oct-3;
2. evaluate it once on a genuinely new original-match whole-hand batch;
3. measure exact-hand rate, wrong accepted hands, reject rate, source-qualified class coverage and live capture-to-advice p50/p95;
4. only after the separate Issue #7 promotion gate passes consider any Runtime wiring.

No private source video or derived crop pixels are committed by this note.
