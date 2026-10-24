# Vision V0.2 recovered CI evidence triage — 2026-10-13

## Scope and provenance

This note summarizes existing tracked CI artifact reports recovered from Vision Regression run `38174847492` at branch HEAD `32fdf5b50a1415f242352cab0291fba72d74d124`. It is a report re-read, **not a new detector run**. The recovered artifact does not contain the private original video, `baseline_export.json`, or private crop directory, so it does not reproduce the 43-tile same-match whole-hand diagnostic.

Runtime confidence threshold remains 0.82. This note does not change Runtime behavior, promote Hint Alpha, or enable Executor.

## Concealed tile template evidence

From `phase6_concealed_identity_validation_v0_2.json`:

- 144 approved labels; scorable coverage 90.28%.
- Exact Top-1 accuracy 74.62%; category accuracy 94.62%.
- Frozen-gate accepted accuracy 100%, but only 44 labels accepted by the runtime gate (33.85% of 130 scorable labels).
- The gate rejected 79 for confidence below 0.82 and 7 for missing standard-class coverage in the candidate category.
- The 100% accepted accuracy is conditional on the conservative gate and must not be described as 100% overall recognition accuracy.
- Highest-priority weak identity classes include S3/S4/S6 and M6, where raw exact accuracy is low or zero in this artifact. Some classes have no accepted examples; absence of accepted samples is not evidence of good accuracy.

From `phase6_tile_dataset_audit_v0_2.json`, leakage-safe validation has 82.88% scorable coverage, 80.17% exact accuracy, 94.21% category accuracy, and 50 accepted labels at 100% accepted accuracy. This is dataset/template validation evidence, not an end-to-end live screen accuracy claim.

## Gold identity evidence

From `phase6_gold_identity_validation_v0_2.json`:

- 147 approved labels; 91.16% scorable coverage.
- Exact Top-1 accuracy 80.60%; category accuracy 95.52%.
- 46 labels accepted by the runtime gate; accepted accuracy 100% (conditional subset).
- Gold-skin-only subset has just one accepted label (1/1). This is insufficient evidence for broad Gold-skin robustness or safe opening-state inference.

Opening identity must continue to come from the visible Gold/flower UI and verified state transitions; do not infer hidden opening position or RNG state.

## Public meld identity blocker

From `opponent_meld_real_public_eligibility_v0_1.json`:

- S4/S5/S6 real-public references: S4 has 2 independent match groups; S5 and S6 each have only 1. The S456 probe is development-only, not promotion evidence.
- M1/M2/M3 cross-match real-face counts are all 0 and independent match-group counts are all 0. Their real-public probe is blocked by missing cross-match real references.
- S1/S2/S3 are also blocked as a group: S1 has 0 independent groups, S2 and S3 each have 1.
- The S456 diagnostic explicitly reports 15/15 formal identities UNKNOWN because S5 and S6 each lack the required additional independent match-group support. This is a fail-closed outcome, not a false-positive identity success.

The public meld MobileNet/template experiments and synthetic transfers remain diagnostic only. Synthetic variants do not substitute for reviewed real public meld faces.

## Next actions, ordered by impact

1. Restore or rebuild a private baseline export from a source-qualified video, then manually review crops and alignment before scoring whole-hand metrics. The uploaded MP4 SHA differs from the pinned original MOV SHA, so any rerun must be labeled as a new source/rerun.
2. Collect reviewed real public-meld face samples from independent original match groups, prioritizing M1/M2/M3 first, then S5/S6/S4 and S1/S2/S3. Preserve source SHA and original-match lineage.
3. Keep geometry/segmentation, meld structure (peng/kong/added kong), and tile-face identity as separate metrics. A correct meld count does not prove correct tile identity.
4. Keep UNKNOWN for under-supported faces; do not infer unseen tile counts, opponent danger, or structural advice from uncertain public faces.
5. Require the established promotion gate (at least 8 independent sessions and all geometry, identity, draw timing, PublicState, Gold and safety gates) before formal promotion.

## Safety boundary

- Runtime confidence threshold: unchanged at 0.82.
- MeldAwareShantenAgent V0.10: unchanged.
- Hint Alpha: read-only.
- Executor: OFF.
- No raw video, crops, or private frame-derived images are included in this document.
