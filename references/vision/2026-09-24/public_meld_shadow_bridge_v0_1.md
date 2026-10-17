# Issue #69 — public meld per-face shadow bridge (development only)

This feature is a **read-only evidence diagnostic**, not a Runtime Vision
promotion, player-action prediction or 8-hand reconstruction.

## Dependency / integration policy

PR #110 contains the separate original-match-gated public-face template
classifier. PR #111 contains regular three-face public meld segmentation and
rejects the reviewed stacked 3+1 Kong. This stacked integration branch starts
from PR #110 and temporarily includes the unchanged production/test files
from PR #111, so the entire pipeline can be tested by GitHub CI **before**
either dependent PR is merged. Once #110 and #111 are merged separately,
reconcile/rebase this branch against updated main and keep only the bridge
module, its tests, CI and this evidence note in the final integration PR.

The pipeline uses only **SHA-verified already-reviewed screenshots** and
**approved, separate public_meld face templates**:

1. Require an approved development-only calibration group, exact source
   session/video SHA, verified screenshot bytes, reviewed frame and group bbox.
2. Run the unchanged public geometry detector over that exact screenshot.
   Select exactly one overlapping bottom_group; missing or duplicated groups
   abstain without selecting a nearby unrelated group.
3. Split the group only when it looks like an ordinary horizontal three-face
   row. The stacked added-Kong returns no face candidates.
4. Crop each face separately and call the PR #110 classifier with
   region=public_meld, excluding the complete original match group.
5. Preserve tile_id, evidence_grade, actor, turn_actor and action_kind as
   **UNKNOWN**, including when a future shadow model returns a tentative
   shadow_proposal. Reject any model output that claims direct evidence,
   safe runtime inference, promotion or executor safety.

The existing hand/draw/Gold recognizer and all Rules/AI/Simulator/Hint/
Executor modules are untouched. No model proposal enters RiverSnapshot,
MeldSnapshot, ActionAssembler or the match ledger.

## Frozen development audit

Run from the repository root with Vision extras installed:

    python -m workspace.vision.public_meld_shadow_bridge

The already-reviewed evidence set contains four ordinary exposed three-face
groups (Peng P1×3, Chi S789, M456, P678) and one overlapped added-Kong.
The geometry test requires coverage of all 12 previously approved face boxes
at >=0.80 **target coverage**; the Kong must be rejected. The public
identity bank has 17 approved labels and only two previously inspected
original-match groups; it has no cross-match same-class coverage. Therefore
the expected real shadow result is 12/12 identity abstentions and zero
proposals, NOT 100% recognition accuracy. Synthetic classifier tests separately
cover supported proposals and unsafe-output rejection.

This audit is not a source-disjoint blind test. The next evidence requirement
is independent review of new faces from truly different original matches,
including opponent melds, tilted stacks and negative lookalikes, then a
frozen per-region test and independent public turn evidence.
