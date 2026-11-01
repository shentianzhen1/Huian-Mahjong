# PROJECT_STATUS — Current Snapshot

Snapshot date: 2026-11-01 (Asia/Shanghai). Execution truth: GitHub Issues.
Rule truth: RULE_STATUS.md / RULE_EVIDENCE_MATRIX.md. This page is a snapshot.

## Source and delivery

Active integration: Draft [PR #126](https://github.com/shentianzhen1/Huian-Mahjong/pull/126),
branch `codex/hint-alpha-local-test-sync-20261004`, unmerged.
Audited baseline: `adc4fc1e72319fda5b121a2ddf909161f3fce87e`.
The current source includes the integration fixes described below;
inspect CI on its exact HEAD rather than reusing baseline results.

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

The current source fixes two reproduced adc4fc1 integration defects: trial-off
workers now omit experimental references, and unresolved live hand boundaries
suppress Gold-dependent advice. Public OCR errors also pause advice after an
initial trusted hand. Confirmation fences buffered/queued results and their
prior-identity votes; same-hand recovery preserves Gold, next-hand confirmation
clears it. Manual Gold does not bypass a pending hand boundary. The Python
console now uses the same live entry as the installer/source launcher.
With fresh capture, advisory expiry now withdraws the hint and resets identity
confirmation without clearing hand/Gold memory or replacing worker queues.
Actual capture loss still invalidates the generation and clears session facts;
stale results cannot revive advice and pending-hand blocks remain in force.
Live and reference replay now share the same two-vote pending-boundary policy.
Replay pauses opening/identity memory updates before evaluation, preventing
unconfirmed Gold from leaving a conflict that blocks same-hand recovery.
[Development replay comparison](docs/vision/replay_boundary_memory_regression_20261101.json):
34 identical-pixel windows from an already revealed 14-second clip retain the
same 9 display decisions; 11 pending windows no longer carry old Gold. This
does not measure independent accuracy or actual Windows performance.
Replay summaries now separate prioritized structural blockers from public-identity
context, preserving raw issue counts. An [existing-source diagnostic](docs/vision/advice_blocker_diagnostic_20261101.json)
has 39 windows / 25 displays; the 14 blocked windows bucket as geometry 10,
hand boundary 2, hand identity 1 and stability 1. These are diagnostics, not accuracy.
The low-score draw was manually reviewed as a 兰 flower and correctly rejected
from ordinary identity. [All 25 displayed current frames in this clip](references/vision/2026-11-01/hand2_reviewed_advisory_anchors_v0_1.json)
have 255/255 reviewed tile instances and matching manual-input structural outputs.
They comprise only four distinct hand states in one revealed original match;
prior identity frames and blocked windows were not fully truth-reviewed.
This does not qualify flower recognition or independent generalization.
An [oct09 source diagnostic](references/vision/2026-11-01/oct09_gold_s5_development_diagnostic_v0_1.json)
now verifies one other visible table context against prior PR #131's source SHA.
At two stable current frames, 24/26 identities are accepted correctly; two
concealed Gold S5 tiles lack real-skin qualification. Manual indicator Gold alone
still cannot enable advice. The third, raised-tile frame is geometry-blocked.
An explicit reference-supported concealed-Gold trial path now consumes matching
appearance support while preserving strict raw rejection and default behavior.
A private 30-image pack (28 existing + 2 S5 crops), `2026.11.01.private1`, enables
both stable checkpoints; one is the donor positive control and one is a later
same-match query. Raised-tile geometry still blocks. New crop pixels are not in
GitHub; default bundled references and installer remain unchanged. This is
revealed development with corrected manual truth, not a fresh holdout.
Focused regressions exercise the actual worker and live consumer. These are
synthetic wiring checks, not independent recognition or Windows acceptance.

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
