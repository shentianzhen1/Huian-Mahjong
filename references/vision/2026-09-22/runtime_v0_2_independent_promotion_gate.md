# Runtime Vision V0.2 Independent Promotion Gate V0.1

Date: 2026-09-22

## Purpose

This contract defines when Runtime Vision V0.2 may move from **experimental read-only prototype** to the project's **formal read-only Vision baseline**.

It does **not** authorize Executor, automatic clicks, or post-action control.

The thresholds are frozen **before** collecting/evaluating the next untouched holdout. If the project changes a threshold after seeing holdout outcomes, that holdout becomes development evidence and a fresh untouched holdout is required.

## Required evidence bundle

The new batch must be source-disjoint from all Phase 5 / Phase 5C truth and from the templates used to classify it. It must contain at least 8 independent source sessions.

The machine gate in `workspace/vision/tiles_runtime_v0_2/promotion_gate.py` requires all of the following:

| Area | Gate |
|---|---|
| Provenance | independent batch=true; holdout locked before evaluation; no tuning after lock; >=8 sessions |
| Dynamic geometry | precision >=98%; recall >=98%; exact hand-count >=95%; **0 silent runtime-region errors** |
| Tile identity | all 34 standard classes covered; 0 missing; high-confidence accepted accuracy >=99%; >=100 accepted labels |
| Draw temporal | >=30 reviewed draw events; precision >=98%; recall >=98%; 0 duplicate draw events |
| PublicState score | >=64 independent points; score-pair accuracy >=99% |
| PublicState status | >=40 points; remaining-tiles >=98%; hand-index >=98% |
| Gold | >=8 sessions; per-session majority accuracy =100% |
| Stress | >=20 scale/move/occlusion/transition cases; 0 unsafe acceptances |
| Safety | `safe_for_executor=false` must remain true as a policy condition |

A missing metric is a failure, not UNKNOWN-as-pass.

## Why the gate is stricter than the current development results

The existing Phase 5C holdout is revealed and one semantic-region gate failed. The current Phase 6 identity assets also have incomplete standard-class coverage and limited high-confidence accepted sample count. Those results remain useful development evidence but cannot be reused to prove generalization.

## Next data-collection run

Record a new full real match/session batch under conditions not used for template tuning. Preserve original videos locally; only anonymized hashes, reviewed tile crops, geometry truth, and aggregate reports may enter the public repository.

The review order is:

1. lock source hashes and sampled timepoints;
2. complete manual truth without model suggestions;
3. freeze truth;
4. run detector/classifier/temporal/PublicState exactly once;
5. run `evaluate_promotion_bundle()`;
6. if any gate fails, mark the batch revealed and return it to development evidence;
7. after fixes, collect a fresh untouched holdout for another promotion attempt.

## Result semantics

- **PASS**: Runtime Vision V0.2 may be named the formal read-only observation baseline.
- **FAIL**: V0.2 remains experimental; failures become development targets.
- In both cases: **Executor remains disabled** until a separate post-action safety validation exists.
