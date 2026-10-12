# Live Gold M6 normalization experiment — 2026-09-30

Issue: #69  
Status: **diagnostic only / NOT promoted**

A private real-game recording was reviewed locally. Around 110 seconds, two
yellow Gold-skinned copies of M6 (六万) are simultaneously visible in the
player concealed area. The source frame/video is not committed.

Using the current 142-template Runtime V0.2 bank:

- clean Gold copy 1: M6 top-1, confidence **0.440951**;
- clean Gold copy 2: M6 top-1, confidence **0.446763**;
- runtime threshold remains **0.82**.

So the classifier is now directionally correct on the clean crops, but the
confidence gap is still large. The correct behavior remains UNKNOWN/BLOCKED.

An offline Gold-only glyph-normalization prototype was also tested. It ignores
most background/border color and emphasizes the tile glyph. Clean M6 crops
improved to roughly **0.65–0.70**, but Ting-overlay crops were not stable enough
and still did not reach the acceptance threshold. The experiment is therefore
**not merged**.

This result changes the diagnosis:

1. M2/Wan class completeness is no longer the M6 blocker.
2. M6 has two stored logical concealed sessions, so the stored cross-session
   count is no longer the blocker.
3. The remaining M6 blocker is visual generalization / Gold-skin normalization
   and crop robustness.
4. Lowering the confidence threshold is explicitly rejected.

Next work should improve Gold crop/feature normalization and validate it against
the whole held-out bank before any runtime change.

`safe_for_hint=false`; `safe_for_executor=false`.
