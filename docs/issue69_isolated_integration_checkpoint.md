# Issue #69 isolated integration checkpoint (2026-09-26)

This is a **development-only integration branch**, NOT main and NOT an authorization to merge upstream PRs. It starts from #114's stacked branch, which carries #112/#110 and a temporary copy of #111. The two unchanged #116 scorer/test files are imported here for same-tree CI. No production Runtime/Hint/Executor, Rules, Simulator or AI changes.

## Live open-PR inventory and deduplication
- #104 source lineage/private review intake: **not included**; inspect privacy boundaries and import only after independent review.
- #109 oversized river geometry: **not included**; reconcile detector changes against main and run river negative controls.
- #110 identity shadow: **inherited transitively via #112/#114**; not independently promoted.
- #111 regular meld segmentation: **temporary duplicate inside #112/#114**; compare blob SHA to #111 head and drop duplicate once upstream is reconciled.
- #112 meld shadow bridge, temporal observers, source-scoped prompts: **inherited via #114**. Do not treat optional delayed exposed-meld shade as proof of action; concealed-hand shade is retired.
- #114 independent hand/wall gates and conservative multi-signal join: **branch base**.
- #115 docs-only integration plan: **not imported**, avoid competing authoritative documents.
- #116 offline replay scorer + synthetic tests: **copied unchanged into this branch**. It does not run any detector, and cannot score original footage without adjudicated frame anchors AND real predictions.

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

This branch is a reproducible **partial** code-integration checkpoint (#114 + #116), not full resolution of #69. #104/#109 and upstream PR deduplication remain outstanding. Do not merge into main without explicit owner approval.
