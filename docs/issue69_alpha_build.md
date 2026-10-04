# Issue #69 internal Alpha build audit (2026-10-04)

Audited main: `96ee733c8daa13bf5166719c1a3f398f680828c1`.
Initial integration audit: `815e506b39aa0dabdeabeadc2c5dde1d0b21fcea`.
Shared replay boundary `bb80861593a85d2c0cad5773123b72d405fd3e9d` passed
Tests, Vision Regression, Evidence Contracts and CodeQL.
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
python -m workspace.hint_alpha.replay_smoke --video data/issue69_private/source.mp4 --source-sha256 SHA256 --source-session ORIGINAL_SESSION --start 173 --duration 3 --stride 12 --output data/issue69_private/alpha_replay.json --require-accepted --require-recovery
```

A source mismatch, repeated source frame index or non-monotonic timestamps
fails. Bursts spanning more than 0.8 seconds cannot establish live stability.
`--require-accepted` exits unsuccessfully if all windows abstain; it retains the
report rather than relabeling zero accepted windows as successful acceptance.
`--require-recovery` also requires accepted -> blocked -> accepted in this
sequence. Initial blocked -> accepted is acquisition, not recovery. Reports
include consecutive advice runs and rejection-issue window counts. Use the
registered original Runtime session with `--source-session` when known; a
SHA-derived session alone makes no original-match template-exclusion claim.
The replay clock uses source PTS, not inference wall time; this is offline
regression and does not validate live freshness/performance or Windows capture.

The existing public `66fe863f_youjin100/source.json` frame manifest can also be
used with `--frame-manifest`. Its 12 sparse real screenshots produced 10 blocked
windows / zero displayed advice windows. This proves source-checked sparse-frame
abstention only, not contiguous-frame acceptance or independent generalization.
See the frozen metadata report in references/vision/2026-10-04.

Synthetic contract regressions separately cover accepted structural advice,
UNKNOWN-to-trusted recovery, default promotion blocking and old-epoch rejection.
They do not substitute for real-video accepted/recovery evidence.

## Continuous real recovery checkpoint (2026-10-04)

The private exact first-hand source (`fba5f67d...`, registered session
`session_fba5f67d244fb5bd`) was decoded at native 2796x1290, without resizing,
for 173–176 seconds at stride 12. Thirteen overlapping three-frame windows
produced **8 structural advice windows / 5 blocked windows / 1 recovery**.
The first two accepted windows report ordinary shanten 0; after two blocked
windows, six accepted windows report ordinary shanten -1; terminal/transition
frames block again. Unknown public identities keep remaining-copy/danger OFF.
No discard choice was emitted in this checkpoint, so this does not validate
real-video discard suggestions or special Hu eligibility.

See `references/vision/2026-10-04/alpha_continuous_real_recovery_v0_1.json` for
source/session/frame/pixel pins and complete snapshot decisions. A second local
decode reproduced all decisions and pixel hashes (timing excluded). CI
recomputes the saved snapshot decisions; private raw pixels remain local and
are not redecoded by CI. This is same-source development smoke, without a
human tile-accuracy measurement or full-match state-recovery claim.

Windows WGC/PrintWindow live capture, freshness, latency and disconnect/restart
acceptance remain pending. No private raw media should be committed.

## Real structural discard checkpoint (2026-10-04)

The **same original first-hand recording** (not another match) at native
2796x1290, 160–164 seconds, stride 18, yielded 12 overlapping windows:
8 displayed structural advice, 4 blocked, including **2 post-draw discard
windows** at source frames 9608/9626 (162.44/162.75s). Both read the same
11-tile own hand, Gold M6 and two own melds, with four tied minimum-shanten
choices M3/P5/P7/P9. No remaining-copy, danger or special-Hu advice opened.
The UI now displays the actual UNKNOWN reason when inputs fail; the formal
promotion gate is unchanged in default mode.

`--require-discard` accepts only a displayed `POST_DRAW` window with nonempty
structural choices. It correctly rejects the real 173–176s window even though
that sequence has accepted shanten/complete-structure output. Metadata is frozen
at `references/vision/2026-10-04/alpha_real_discard_160_164_v0_1.json`; CI
recomputes the saved snapshots without private media. This is a same-source
automatic-chain smoke, **not** tile identity accuracy, human-confirmed optimal
discards, V0.10 strategy evaluation or live Windows acceptance.
