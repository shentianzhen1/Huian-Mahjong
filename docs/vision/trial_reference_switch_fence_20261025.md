# Reference-policy switch observation boundary — 2026-10-25

The manual trial loading integration at d7712ed passed all five CI workflows,
including Windows installer. Review identified one additional live boundary:
a worker started before loading new references or toggling source trial can
return afterward. Resetting hand-confirmation votes alone does not prevent
its two older classified frames from reprising a stale policy.

On the existing trial toggle path (also used after successful reference load),
record a monotonic capture-time floor and clear the old frame buffer. The result
consumer rejects captures at or before that floor, including old error payloads.
Require every sample in a newly scheduled burst to be newer than the floor,
including captures that were still pending in the capture queue at the switch.
Retain the current capture epoch and manually selected Gold. Keep the worker
single-flight: consuming its old result releases the busy flag, then newly
captured frames can launch the next read. No extra worker, old-hand carryover,
threshold change or loosening of freshness checks is introduced.

Four regressions execute the actual UI methods without a GUI: old frames are
cleared while manual Gold/epoch persist; delayed pre-switch success/error cannot
overwrite the waiting state; a boundary capture is rejected and a fresh later
capture can reach evaluation; queued pre-switch captures cannot prime a new
burst. Combined validation:82 tests passed, including
manual packet/cache/coverage, source trial, live stability, freshness, reader,
builtin assets and Gold. Syntax/diff checks passed. No independent video metric
or Windows mirroring timing is inferred from these tests.

The private19-image packet is unchanged. Existing173/237 and42-discard source-
clock replay evidence belongs to the previously verified classifier config;
this fix governs switching policies and does not claim a new recognition gain.
Current-head CI must be checked separately from d7712ed's successful runs.
