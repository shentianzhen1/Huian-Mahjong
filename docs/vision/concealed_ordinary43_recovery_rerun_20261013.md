# Concealed ordinary-43 recovery rerun — 2026-10-13

## Status

**Baseline reproduced exactly; historical 43/43 candidate still not reproduced.**

This is a recovery rerun from the SHA-qualified private 2026-10-03 source. It is development evidence from one already-revealed original match and is **not** an independent holdout or Runtime promotion result.

Frozen boundaries remain unchanged:
- Runtime identity threshold: **0.82**
- CurrentAgent: **MeldAwareShantenAgent V0.10**
- Hint Alpha: read-only
- Executor: OFF
- PR #126: Draft / unmerged

No Runtime recognition logic was changed.

## Recovered execution inputs

Source video:
- filename: `ScreenRecording_10-03-2026 22-36-10_1.mov`
- SHA-256: `e5b8d8e116f67b13b71a1643c5b7f7b26bb4c1e0848a7ba7407d8c5644b0ed14`

Runtime payload:
- recovered from the current Windows test installer artifact for PR #126 HEAD `f7bcf623195edb651ff9ad06164c881b49798909`
- installer artifact id: `11760039064`
- artifact digest: `sha256:4fed2dc35f83611a5860c2487bf6cf338a9df67fec3da6522cdce2ac925ed28a`
- extracted Runtime dataset contained 147 template assets plus the label sidecars used by the packaged Runtime

The committed `whole_hand_baseline_export.py` was run against this recovered Runtime payload and the exact source video.

## Ordinary 43-tile denominator recovery

Historical correction evidence explicitly names the three ordinary checkpoints at 20 s, 30 s and 40 s:
- t20: `real_20261003_t20_normal_16`
- t30: `real_20261003_t30_post_peng_13`
- t40: `20261003-seg-shae5b8-t40.0`

Their reviewed visible identities are 16 + 13 + 14 = **43**.

The t20 hand was recovered from the SHA-qualified source and the pinned intake/correction evidence. In particular:
- frame 1176 slot 2 = P2
- frame 1176 slot 13 = M2
- frame 1176 slot 15 = M6, not M7
- the full t20 reviewed order is:
  `P1 P1 P2 P2 P3 P4 P4 P6 P6 S4 S5 S7 M1 M2 M3 M6`

This denominator reproduces every corrected historical aggregate below.

The older 2026-10-12 dependency-audit sentence that describes the 43 denominator as “10-, 30- and 40-second samples” is inconsistent with the correction/intake evidence and with the exact aggregate reproduction below. Treat that sentence as stale provenance text, not as the recovered ordinary-43 definition.

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

These values exactly match the corrected historical report. This establishes that the source video, detector geometry, packaged Runtime dataset and ordinary-43 truth denominator have been recovered sufficiently to reproduce the formal baseline.

## Tight-fallback rerun on current packaged Runtime dataset

The committed `whole_hand_tight_fallback_probe.py` was then run on the regenerated baseline export using the packaged Runtime dataset.

Result:
- primary accepted correct: **25**
- fallback attempted: **18**
- fallback accepted: **0**
- final accepted correct: **25/43**
- wrong accepted: **0**
- rejected: **18**
- whole hands complete: **0/3**

Therefore the previously reported development-only **43/43** result is **not** explained by tight cropping alone against the current packaged Runtime dataset.

The historical evaluator accepts a caller-provided candidate dataset. The missing dependency is now narrowed to the exact historical development candidate dataset / private support assets (and its invocation), not the source video, baseline geometry or formal Runtime dataset.

Do not recreate that missing candidate by adding these same 43 query crops as support and then describe the result as historical reproduction. Any such experiment would be a new tuned development run.

## Next gate

1. Continue tracing the exact candidate dataset/support assets and invocation used for the reported 43/43 development run.
2. If they cannot be recovered, retain 43/43 only as a historical reported development result.
3. Use the newly reproducible 25/43 formal baseline as the recovered baseline anchor.
4. For product progress, follow Issue #69 and collect/evaluate a genuinely source-disjoint whole-hand batch before any Runtime promotion.

No private source video or derived crop pixels are committed by this note.
