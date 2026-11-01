# PROJECT_STATUS — Current Snapshot

Snapshot date: 2026-11-01 (Asia/Shanghai). Execution truth: GitHub Issues.
Rule truth: RULE_STATUS.md / RULE_EVIDENCE_MATRIX.md. This page is a snapshot.

## Source and delivery

Active integration: Draft [PR #126](https://github.com/shentianzhen1/Huian-Mahjong/pull/126),
branch `codex/hint-alpha-local-test-sync-20261004`, unmerged.
Runtime source inspected: `adc4fc1e72319fda5b121a2ddf909161f3fce87e`.
This snapshot update changes documentation only; inspect CI on its exact new HEAD.

Latest verified installer delivery uses source
`7f1a86e9205cbdad7462e5ea2525206e2e427b63`:
[Windows run 40916853368](https://github.com/shentianzhen1/Huian-Mahjong/actions/runs/40916853368).
Its bundled development reference version is `2026.10.30.1`: 28 tile images
(20 ordinary concealed, 7 opened-Gold, 1 concealed-Gold SOUTH).
The user authorized these reviewed tile-only assets in GitHub and the installer;
raw private videos are not included. See [bundle manifest](dataset/tiles_runtime_v0_2/reference_pack/bundle.json).
Later source changes are not automatically in that installer.

At inspected source adc4fc1, Tests, Vision Regression, Evidence Contracts and
CodeQL succeeded. Windows run 41274587409 passed release_request and skipped
the installer job. A green workflow does not imply a new EXE.
Small changes do not request a new installer.

## Capability and validation

[Issue #45](https://github.com/shentianzhen1/Huian-Mahjong/issues/45) owns
read-only complete-hand + visible Gold + own-meld-count structural shanten and
minimum-shanten discards. [#69](https://github.com/shentianzhen1/Huian-Mahjong/issues/69)
is closed; its replay records remain historical evidence. Unknown public
identities still block remaining-copy/danger capabilities.

Source adc4fc1 has two outstanding reproduced integration risks: trial-off
worker reference loading and live pending-hand-boundary handling with carried
Gold. Existing focused tests passing does not resolve those findings.
This documentation update does not fix runtime behavior.

[Issue #7](https://github.com/shentianzhen1/Huian-Mahjong/issues/7) formal
promotion remains blocked. Same-match replay and bundled-reference self-matches
are development evidence. The [source inventory](docs/vision/validation_readiness_20261101.md)
records 37 accessible video files, with no newly certified blind original-match
batch in this audit; file count is not match count. Actual Windows capture-to-hint
p50/p95, wrong accepted hands and recovery acceptance remain unmeasured here.

## Review and architecture

The [review split record](docs/pr126_review_slices_20261101.md) separates the
665-path audited source diff by area. Draft [#147](https://github.com/shentianzhen1/Huian-Mahjong/pull/147)
extracts 10 exact-blob historical evidence files onto main for separate review;
it is not merged and has not reduced #126's diff yet.

Rules / Environment / Simulator / AI / Vision / Hint / Executor stay separate.
CurrentAgent is MeldAwareShantenAgent V0.10; identity threshold 0.82;
Hint is internal/read-only and Executor OFF. UNKNOWN stays explicit.
Rule implementation/installer claims require their own versioned evidence;
confirmed-rule facts and migration status stay in their rule documents and Issues.
Preserve 144 tiles, no fifth copies, at most three playable Gold copies and
zero-sum settlement.
