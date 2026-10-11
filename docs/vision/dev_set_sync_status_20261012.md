# Vision development-set sync status — 2026-10-12

## Scope and source of truth

This note records the current development evidence boundary for concealed-tile recognition. It does not promote any candidate to Runtime. PR #126 remains Draft and must not be merged without explicit approval.

- Branch checked: `codex/hint-alpha-local-test-sync-20261004`
- HEAD checked before this note: `a9e2bd28feee432445a01d22ca6454eb9990fc57`
- Relevant issues: #69 (current hand / own melds / shanten), #7 (independent Runtime Vision promotion gate).
- Runtime identity threshold remains 0.82.
- CurrentAgent remains `MeldAwareShantenAgent V0.10`; Executor OFF; Hint Alpha read-only.

## Evidence already represented in GitHub

PR #126 contains the corrected 2026-10-03 same-match diagnostic in its description and links:
- `docs/whole_hand_real_diagnostic_20261007.md`
- `references/vision/2026-10-08/whole_hand_truth_correction_20261003_v0_1.json`

The current branch contains the development-only evaluator:
- `workspace/vision/tiles_runtime_v0_2/whole_hand_tight_fallback_probe.py`
- `tests/test_whole_hand_tight_fallback_probe.py`

The evaluator explicitly states that it does not change Runtime behavior and that fresh original-match evidence is required before Runtime wiring.

## Development result — do not treat as blind validation

Prior development evaluation reported the primary-first / tight-crop fallback candidate on the same 43 known 2026-10-03 ordinary concealed-tile samples:
- accepted correctly: 43/43
- wrong accepted: 0
- UNKNOWN/rejected: 0
- whole-hand samples complete: 3/3

These samples were already used during development and are **not an independent holdout**. This result is not a real-world generalization claim and does not justify Runtime promotion. The 43/43 summary was not found in the PR description when this note was prepared; this file records the reported summary while clearly marking its evidence limitation. Private source video and image crops are not included.

## Formal Runtime baseline (same-match diagnostic)

The reviewed 2026-10-03 diagnostic currently documented in PR #126 reports:
- concealed/draw geometry: 57/57 truth tiles detected, no misses or extras in that sample
- raw template Top-1: 36/43 (83.72%)
- confidence-only gate >= 0.82: 31/43 accepted, 31/31 correct
- full Runtime after source-support gates: 25/43 identities exposed, 25 correct, 0 wrong accepted
- whole-hand advice eligibility: 0/3 ordinary hands, each containing at least one UNKNOWN

These are sample-specific diagnostic numbers, not independent validation.

## Remaining gaps

1. The development 43/43 summary must be reproducibly regenerable from the evaluator and the private baseline/candidate inputs; do not commit private videos or crops.
2. The candidate is not wired into the formal Runtime path.
3. A fresh, source-disjoint original-match whole-hand batch is still required. The 2026-09-19, 2026-09-26, and 2026-10-03 sessions have already been used for support or development and must not be presented as fresh holdout evidence.
4. Continue to report hand identity, Gold state, and meld structure/identity separately. The hand fallback result does not prove Gold or exposed-meld identity is solved.
5. Issue #7 formal promotion gate remains independent: >=8 sessions, geometry precision/recall >=98%, exact hand count >=95%, zero silent runtime-region errors, 34/34 classes, >=99% high-confidence accuracy and >=100 accepted labels, draw temporal and PublicState gates, Gold >=8 sessions with 100% session-majority accuracy, stress cases and safe policy.

## Next action

Use a genuinely new original match for locked, manually reviewed truth and one-pass evaluation. Until that exists, keep the candidate development-only, preserve threshold 0.82, and do not change Runtime, V0.10, or Executor state.
