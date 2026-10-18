# Concealed 43/43 candidate reproduction — 2026-10-13

## Status

**Historical development candidate reproduced end-to-end.**

This rerun reconstructs the previously reported 43/43 concealed ordinary-tile development result from SHA-qualified private source videos, hash-pinned support crops, the committed primary-first tight fallback evaluator, and the frozen 0.82 Runtime identity gate.

This remains **development evidence only**, because the 2026-10-03 query match has already been inspected and used during development. It is not a fresh independent holdout and is not Runtime promotion evidence.

Frozen boundaries remain unchanged:
- Runtime identity threshold: **0.82**
- CurrentAgent: **MeldAwareShantenAgent V0.10**
- Hint Alpha: internal/read-only
- Executor: OFF
- PR #126: Draft / unmerged
- no Runtime classifier or fallback wiring change in this rerun

## Query batch

Query source:
- original match group: `reviewed_match_2026_10_03_recent_real_game`
- source SHA-256: `e5b8d8e116f67b13b71a1643c5b7f7b26bb4c1e0848a7ba7407d8c5644b0ed14`
- ordinary checkpoints: 20 s, 30 s, 40 s
- reviewed identities: 16 + 13 + 14 = **43**

The formal packaged Runtime baseline was first reproduced exactly:
- raw Top-1 correct: **36/43**
- raw confusions: `S4 -> S6` x4, `M2 -> M3` x3
- confidence-only >=0.82 accepted: **31/43**, all correct
- full Runtime exposed: **25/43**, all correct
- wrong accepted: **0**
- UNKNOWN/rejected: **18**
- complete whole hands: **0/3**

## Recovered Sep-26 support

Support source:
- original match group: `reviewed_match_2026_09_26_eight_hand`
- source SHA-256: `05ef070ea185e7c224126eadd527e77075f8b85e86ed49326d981ead81fb5738`
- source session: `session_real_20260926_eight_hand`

The exact source video was recovered and re-hashed locally. Its SHA-256 matches the historical support manifest exactly.

Ten development support crops were regenerated from the pinned source frames/bboxes and verified byte-for-byte by SHA-256 against the historical staging manifests:

- M2 x2 from frame 148
- support expansion: S3 x1, S4 x1, S7 x1, P2 x1, M1 x4

All ten regenerated crop SHA-256 values matched their historical `asset_sha256` records.

Relevant historical manifests:
- `references/vision/2026-10-08/reviewed_tile_intake_staging_20260926_m2.jsonl`
- `references/vision/2026-10-08/reviewed_tile_intake_staging_20260926_support_expansion.jsonl`
- `references/vision/2026-10-08/concealed_source_disjoint_fallback_ab_v0_1.json`

No private source video or crop pixels are committed by this note.

## Candidate rerun

A candidate dataset was reconstructed by adding only the ten hash-verified Sep-26 development support crops to the recovered packaged Runtime dataset.

The committed primary-first tight fallback policy was then rerun on the reproduced 43-tile baseline:

1. Run the normal primary Runtime classification path first.
2. Never override an already accepted primary identity.
3. Only when the primary identity is UNKNOWN, classify the tight detector `pixel_bbox`.
4. The fallback must independently pass the unchanged 0.82 gate and the same identity/source-support rules.
5. No class-specific override and no lower threshold.

### Reproduced aggregate

- truth tiles: **43**
- primary accepted correct after Sep-26 support: **35**
- primary wrong accepted: **0**
- fallback attempted: **8**
- fallback accepted: **8**
- fallback correct: **8**
- fallback wrong: **0**
- final accepted correct: **43/43**
- final wrong accepted: **0**
- final UNKNOWN/rejected: **0**
- complete whole hands: **3/3**

Per hand:
- 20 s: **16/16**, complete
- 30 s: **13/13**, complete
- 40 s: **14/14**, complete

This exactly reproduces the historical development result frozen in `concealed_source_disjoint_fallback_ab_v0_1.json`.

## Interpretation

The missing historical dependency has now been recovered sufficiently to reproduce the full candidate chain:

`formal Runtime 25/43 -> Sep-26 support primary 35/43 -> UNKNOWN-only tight fallback 43/43`

Therefore the earlier 43/43 report is no longer only a historical claim; it is reproducible from SHA-qualified source material and hash-pinned support assets.

However, this does **not** establish real-world generalization:
- the Oct-3 query match was repeatedly inspected during development;
- the candidate is still development-only;
- the fallback is not wired into Runtime;
- no threshold change is justified;
- no claim of 100% live recognition should be made.

The historical negative control also remains important: replacing the primary crop globally with the tight crop is unsafe because it produced high-confidence `M3 -> M2` wrong accepts around 0.842-0.844. The safe candidate remains **primary-first, UNKNOWN-only fallback**.

## Next gate

Use a genuinely fresh original match that has not been used for support, tuning, or prior inspection:

1. lock reviewed whole-hand truth before candidate evaluation;
2. run the exact same primary-first fallback once;
3. report exact-hand rate, accepted/wrong accepted tiles, reject rate, acquisition/recovery, and end-to-end capture-to-advice latency;
4. keep Runtime unchanged until the source-disjoint gate is passed.

This rerun changes no Rules, AI, Runtime behavior, Hint write capability, or Executor state.
