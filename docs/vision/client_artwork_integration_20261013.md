# Client artwork intake aligned with current Alpha — 2026-10-13

Issue #69 follow-up to the user's newly supplied mini-program artwork. Source
Draft PR #138, branch `codex/vision-development-asset-intake`, verified head
`5add15835ca8cf3247199e8de4ad0d90e159f3ee`. Its Tests, Vision Regression and
Evidence Contracts workflows passed; 19 focused intake tests also pass locally.

The four development intake tool/test/document/evidence files are copied
unchanged from that verified head into the active PR #126 branch. Neither PR is
merged, and main remains unchanged. This brings the intake tooling to the
current Alpha codebase without admitting artwork to the Runtime classifier.

## What the new material establishes

The upstream private packet records 34 standard + 8 flower artwork classes,
79 recovered real concealed crops and six exact-SHA source files. Five video
files belong to one user-confirmed match; their independence from other
registered matches remains UNKNOWN. The image source is tied upstream to an
existing parent recording, so it cannot be counted as a new match automatically.
Package artwork supplies glyph coverage, not independent real-match support.

The published trial used a historical main bank and 137 revealed development
crops: raw correct 93 -> 99, six improvements, zero regressions; threshold-pass
count stayed 50 and real-support-gated acceptance stayed 42. It did not measure
the current 43-tile whole-hand fallback candidate or an independent holdout.
Do not combine those populations or claim an updated installer accuracy.

## Current bank reconciliation

The current approved bank has 147 labels. Exact source-SHA linkage finds all
79 concealed labels related to the six upstream recovered sources. One existing
Gold-region label has a linked source as well, making 80 linked labels overall;
that Gold label is outside the upstream 79-crop concealed packet. No new labels,
templates or confirmed match claims were written.

The diagnostic records label-file hashes, per-class counts and region-specific
source coverage in
`references/vision/2026-10-13/current_bank_client_intake_reconciliation_v0_1.json`.
Cross-registry independence remains provisional, and package pixels contribute
zero real support. This session did not repeat upstream private pixel recovery.

## Next recognition experiment

Use the existing private package map and recovery manifests with the imported
intake CLI. On the private-source machine, run the current frozen classifier
and the package-artwork candidate on identical current crops, with all clips
from each original match grouped together. Keep baseline and candidate assets
isolated; preserve primary-accepted identities and the fixed 0.82 threshold.
Report per-tile corrections/regressions, confidence/source rejection reasons,
accepted wrongs, exact whole hands and blocked windows separately. Include
actual hand/draw, Gold appearance and detector-path meld crops as separate
domains; clean artwork does not establish shadow or perspective robustness.

Only the tooling and anonymous metadata are in GitHub. The decoded package
images and raw source files remain private upstream, so a new image-based A/B
could not be run from this GitHub-only checkout. No new accuracy is reported by
this integration. Fresh independent-match evaluation is a later promotion gate,
not a prerequisite for using already revealed artwork in development experiments.

Validation on the current Alpha tree: 27 focused intake and concealed-lineage
tests pass. Runtime reader, template bank, threshold 0.82, Rules, V0.10, Hint
policy and Executor OFF are unchanged.
