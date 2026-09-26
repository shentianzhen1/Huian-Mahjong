# Issue #69 isolated integration checkpoint (2026-09-26)

This is a **development-only integration branch**, NOT main and NOT an authorization to merge upstream PRs. It starts from #114's stacked branch, which carries #112/#110 and a temporary copy of #111. The two unchanged #116 scorer/test files are imported here for same-tree CI. No production Runtime/Hint/Executor, Rules, Simulator or AI changes.

## Live open-PR inventory and deduplication
- #104 source lineage/private review intake: **privacy-scoped partial import** (pure lineage, private-only sample exporter and synthetic tests). Original-source SHA manifests, source-specific tests and private pixel/audit modules remain excluded.
- #109 oversized river geometry: **integrated** detector trust/rebaseline changes and three regression test files; integration CI passed at commit 9c408c4.
- #110 identity shadow: **inherited transitively via #112/#114**; not independently promoted.
- #111 regular meld segmentation: **temporary duplicate inside #112/#114**; compare blob SHA to #111 head and drop duplicate once upstream is reconciled.
- #112 meld shadow bridge, temporal observers, source-scoped prompts: **inherited via #114**. Do not treat optional delayed exposed-meld shade as proof of action; concealed-hand shade is retired.
- #114 independent hand/wall gates and conservative multi-signal join: **branch base**.
- #115 docs-only integration plan: **not imported**, avoid competing authoritative documents.
- #116 offline replay scorer + synthetic tests: **imported and corrected on this branch** (original test syntax and nonfinite-FPS validation). It does not run any detector, and cannot score original footage without adjudicated frame anchors AND real predictions.

## One-direction data contract for later code integration
1. Source identity: `video_id, source_sha, session, stream_epoch, frame, fps` and independently attested upper/lower actor mapping; do not infer actor from screen side.
2. Detector/tracker: public tile and river candidates with per-region/frame provenance; UNKNOWN identity allowed.
3. Independent observers: prior discard, new exposed meld onset, visible hand-count delta; optional wall change and delayed **exposed meld** shade. No concealed-hand shadow feature.
4. Conservative join: only same-source, continuous, non-overlapping attested evidence; output development candidate or UNKNOWN. UI prompt means an option was offered, NOT selected.
5. Offline scorer: accept only human-adjudicated action frame anchors and actual machine predictions from the SAME video. Keep detection and actor+kind metrics separate; complete action reconstruction remains unscored.

## Integration acceptance gates
- This branch CI green at **its own head**: Vision regression and core Tests. Old green runs on component PRs are not evidence for this integration head.
- Diff #111 temporary copy against #111 HEAD, check #110/#112/#114 stack base and reconcile #113 main CI workflow.
- Integrate #109 and #104 only after conflict/privacy review and run their targeted negative tests.
- Verify no duplicated competing implementation for hand count or action assembly; keep source-scoped adapter boundaries.
- Original 14.mp4 owner-adjudicated CHI windows 58–60s opponent 3W and 81–83s self 2S are approximate time windows, NOT exact frames or detector outputs. Run actual pipeline, then score; 14.mp4 is development replay, not source-disjoint holdout.
- No real-video recall, precision, actor accuracy or formal promotion until original-footage machine replay and exhaustive event review exist.
- Private footage, screenshots, SHA registry and player/room identifiers must remain outside public GitHub.

This branch is a reproducible **partial** code-integration checkpoint (#114 + #116 + #109 + privacy-scoped #104), not full resolution of #69. Private #104 review, original-footage replay scoring and upstream PR deduplication remain outstanding. Do not merge into main without explicit owner approval.

## 2026-09-26 integration progress
- The #116 imported test had a literal escaped newline causing SyntaxError; corrected only on this integration branch. CI at commit 78697cc: Vision Regression SUCCESS, Tests SUCCESS.
- #111 segmentation module and its test file have exact matching blob SHAs in #111 and the #114-derived integration tree. No duplicate implementation was added; stacked PR diff cleanup is still required when upstream is merged.
- #109 detector oversized-bbox reporting, actor-specific river trust/rebaseline and three matching test files were copied into the integration branch unchanged. Its post-import CI must pass at the new integration HEAD before any merge.
- #104 privacy review found existing public development JSON manifests contain original-video SHA256 and frame-coordinate provenance. These manifests and private audit/probe modules are **not imported** here. Only the pure source-lineage gate, private-only sample export module and synthetic sample tests are imported. The source-lineage original test requires the excluded public real-source manifest; replace it with sanitized synthetic tests before any formal integration of that test. Review existing #104 public files separately for potential exposure; do not reproduce hashes in this branch.
- No real source footage or original frame pixels were committed. All scoring remains development-only; production action fields remain UNKNOWN.

## Latest integration verification
- Commit 9c408c4: **Tests SUCCESS**, **Vision Regression SUCCESS**, including synthetic-only source lineage and cross-module fail-closed contract tests.
- Offline scorer now rejects NaN/infinite/boolean FPS before computing duration and rates. Added corresponding synthetic negative controls; CI for these latest edits must be checked independently.
- Integration modules have one-way dependencies: independent hand-count gate → multi-signal review; the replay scorer consumes only explicitly adjudicated ground truth and actual machine predictions. No automatic candidate-to-prediction promotion is allowed.
