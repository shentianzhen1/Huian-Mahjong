# Runtime Vision V0.2 Closeout Audit — 2026-09-22

## Scope

Audit target: `feat/vision-dataset-recovery-v02-20260921` against `main`.

The branch introduces dynamic geometry, transient `draw_visual` tracking, reviewed runtime assets, temporal draw-event tracking, blind-holdout tooling, and a read-only runtime smoke reader.

## Findings

### Passed / acceptable

- Runtime geometry is resolution-normalized and does not use an absolute X coordinate or target concealed-hand count as the semantic decision rule.
- `draw_visual` is explicitly transient and cannot silently merge into hand without the draw/discard state machine.
- Ambiguous multiple draw components fail closed.
- Runtime output remains `safe_for_hint=false` and `safe_for_executor=false`.
- Dataset assets are tile-only reviewed crops; the tracked audit reports contain no absolute source paths.
- Tile validation uses `leave_source_session_or_group_out_same_region`.
- The fail-closed tile gate accepts only high-confidence, cross-session-supported classes.

### Blocking findings discovered during audit

1. **Runtime V0.2 tests were not executed by Vision CI.**
   - The workflow only ran `workspace/vision/tiles_v0_1` tests.
   - `dataset/tiles_runtime_v0_2/**` was not a workflow path trigger.

2. **Known-session runtime smoke could use templates from the same source session.**
   - This is acceptable only as a functional smoke, not as accuracy evidence, but it unnecessarily permits same-session leakage.

3. **Phase 5C blind holdout did not pass every formal promotion gate.**
   - component precision: 0.9946949602
   - component recall: 0.9868421053
   - hand-count exact match: 0.9565217391
   - one runtime-region semantic misclassification gate failed
   - report result: `phase6_formal_tile_labeling_allowed=false`

   Phase 5C is revealed and cannot be reused as generalized evidence. Existing Phase 6 reviewed assets are therefore development/prototype assets only.

4. **Tile identity remains coverage-limited.**
   - 33/34 standard classes covered; M2 missing.
   - leakage-safe exact accuracy: 79.49% on 117 scorable labels.
   - at threshold 0.82: 50/117 accepted, accepted accuracy 100% in the current development set.
   - this is a conservative prototype gate, not production readiness.

## Fixes applied in closeout

- Vision CI now triggers on `dataset/tiles_runtime_v0_2/**`.
- Vision CI now runs both V0.1 and Runtime V0.2 unit tests.
- Runtime reader excludes the supplied current `session` from template training, making replay smoke closer to an unseen-session test.
- Unit tests cover current-session template exclusion.
- Manifest, dataset README, PROJECT_STATUS and TODO now explicitly mark formal Runtime V0.2 promotion as blocked pending a new source-disjoint blind holdout.
- Executor remains closed.

## Merge decision

**Mergeable as experimental read-only infrastructure, not promotable as the project’s formal Vision baseline.**

After merge, the next promotion gate is a new source-disjoint blind holdout that passes every acceptance gate. No tuning may use that holdout after it is revealed.
