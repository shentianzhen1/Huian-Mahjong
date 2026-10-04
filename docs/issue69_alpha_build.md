# Issue #69 internal Alpha build audit (2026-10-04)

Audited main: `96ee733c8daa13bf5166719c1a3f398f680828c1`.
Audited integration head: `815e506b39aa0dabdeabeadc2c5dde1d0b21fcea`.
Issue #69 is execution truth; PR #117 remains Draft, unmerged.

## Existing runnable chain

`START_HINT_ALPHA.bat --experimental` -> Windows capture -> three-frame Runtime
Vision (identity threshold 0.82) -> CurrentTableSnapshot -> capability gate ->
ordinary structural shanten / minimum-shanten discard choices -> read-only UI.
Install with `INSTALL_HINT_ALPHA.bat`; check with `CHECK_HINT_ALPHA.bat`.
The explicit experimental flag labels unpromoted internal advice; default mode
retains the formal promotion gate. This does not connect development dark-face
fallback, promote Vision, change CurrentAgent V0.10, or enable Executor.

Own meld identities may remain UNKNOWN while trusted own meld count permits
structural analysis. Public rivers and opponent melds are currently absent from
the live shell; remaining-copy and danger outputs stay blocked. Ordinary
structural completion is not confirmed special-Hu eligibility.

## Minimal gaps and order

1. **Capture/result lifecycle protection (implemented in this slice):** stop,
   black frame, capture error, changed window rectangle, sequence restart and
   stale capture/result clear visible advice. Old workers retain their original
   output queues and generation, preventing a restarted capture from receiving
   old results. A new epoch must collect fresh stable frames. Snapshot timestamps
   use capture time rather than result-consumption time. Two-second freshness
   is a configurable internal deployment limit, not a Vision promotion threshold.
2. **Windows live acceptance:** verify WGC/PrintWindow with the actual mirrored
   game, supported geometry and DPI; record accepted and UNKNOWN snapshots,
   disconnect/black-screen/restart recovery, timing and evidence output. Linux
   core tests cannot establish this acceptance.
3. **Real-frame end-to-end repeatable smoke:** freeze source-qualified frame
   sequences and test both accepted advice and abstention/recovery through the
   same shell pipeline; keep private media outside GitHub. No independent-match
   accuracy claim follows from same-source smoke.

EXE packaging, complete public identity/danger and V0.10 live action integration
are later work, not prerequisites for this internal structural Alpha.

## Shared replay boundary (2026-10-04)

The UI and headless replay both call `evaluate_runtime_report()`; the replay
uses the real `read_stable_frames()` reader at threshold 0.82. It records source
SHA, frame indices, source PTS, pixel SHA, elapsed inference time, snapshot,
capability issues and displayed/blocked advice. No images/video are in the report.
Default UI promotion gating is unchanged. Replay explicitly uses internal
experimental structural advice and never enables Executor.

Run a **private local original video** (replace SHA with its frozen SHA256):

```powershell
python -m workspace.hint_alpha.replay_smoke --video data/issue69_private/source.mp4 --source-sha256 SHA256 --start 173 --duration 3 --stride 3 --output data/issue69_private/alpha_replay.json --require-accepted
```

A source mismatch, repeated source frame index or non-monotonic timestamps
fails. Bursts spanning more than 0.8 seconds cannot establish live stability.
`--require-accepted` exits unsuccessfully if all windows abstain; it retains the
report rather than relabeling zero accepted windows as successful acceptance.
The replay clock uses source PTS, not inference wall time; this is offline
regression and does not validate live freshness/performance or Windows capture.

The existing public `66fe863f_youjin100/source.json` frame manifest can also be
used with `--frame-manifest`. Its 12 sparse real screenshots produced 10 blocked
windows / zero displayed advice windows. This proves source-checked sparse-frame
abstention only, not contiguous-frame acceptance or independent generalization.
See the frozen metadata report in references/vision/2026-10-04.

Synthetic contract regressions separately cover accepted structural advice,
UNKNOWN-to-trusted recovery, default promotion blocking and old-epoch rejection.
They do not substitute for real-video accepted/recovery evidence. Still pending:
continuous source-locked real accepted/abstained/recovered sequences and Windows
WGC/PrintWindow acceptance. No private raw media should be committed.
