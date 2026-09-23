# Hand 1 (12–25 s): source-qualified public river baseline V0.1

**Status: reviewed development replay only. NOT an independent holdout, Vision promotion,
or an Executor-safety result.** Source: the same SHA-locked hand-1 recording and the
**already frozen** four-event development truth; no truth events enter detector,
tracker, channel qualification, river observers or action assembler.

## Executable private-local reproduction

With the exact SHA-matching original video already held locally (never put the
recording or private Drive reference in the public repository):

```bash
python -m workspace.vision.real_video_river_replay \
  --video /path/to/private/recording.mp4 \
  --manifest references/vision/2026-09-23/hand01_river_geometry.development.json \
  --first-frame 348 --last-frame 725 \
  --truth references/vision/2026-09-23/hand01_12_25_action_truth.development.frozen.json \
  --output /path/outside/public/repo/private-full-trace.json
```

The video SHA is checked before decoding. The full machine trace is assembled
before the optional frozen truth is opened. CI uses synthetic replay only; it
never needs, downloads, or retains the private recording.

## Actual full 378-frame machine run

- Existing full-frame detector: **5,720** tile-like candidate-frame instances.
- SHA-locked, actor-reviewed ROI + visible-seam filter: **739** qualified
  candidate-frame instances; track: **6** APPEARED and **2** DISAPPEARED
  geometry events (these are **not** action events).
- Both actor-specific DiscardRiverObserver instances established a baseline and
  emitted **2 upper/opponent + 2 lower/player** river-growth observations. The
  assembler produced **4** DISCARD-kind outputs, all with tile and independent
  turn **UNKNOWN**. One untrusted player frame (685) was withheld when touching
  tiles initially lacked a confirmed seam.

| Machine time (s) | Side, source-specific only | Geometry-level kind | Identity/turn | Strict evaluator |
|---:|---|---|---|---|
| 14.068967 | opponent (upper) | DISCARD candidate | UNKNOWN/UNKNOWN | abstain |
| 17.034478 | player (lower) | DISCARD candidate | UNKNOWN/UNKNOWN | abstain |
| 20.413789 | opponent (upper) | DISCARD candidate | UNKNOWN/UNKNOWN | abstain |
| 23.793100 | player (lower) | DISCARD candidate | UNKNOWN/UNKNOWN | abstain |

All four geometry-level events fall within the existing **0.35-second**
development-evaluator window around the four frozen events, with matching
source-scoped screen sides. This is NOT independent tile/turn identification.

## Strict frozen-truth action evaluation (no optimistic relabeling)

- Frozen truth: **4**. Machine predictions: **4**, all **4 abstentions**.
- Verified end-to-end true positives **0**, false negatives **4**.
- Concrete false positives **0** because there were **no concrete predictions**;
  this must not be quoted as a false-alarm accuracy rate.
- actor_accuracy_on_aligned = null; event_precision = null;
  event_recall = 0.0 under strict acceptance; turn accuracy is **unmeasured**.
- Each frozen event has a nearby machine abstention, but no verified action.

## Remaining #69 blockers

1. Independent public-discard tile identity; never substitute hand/global
   templates or assign the known human labels to machine output.
2. A separately observed turn signal and robust ambiguous/overlay suppression.
3. New source-disjoint recording needed for eventual Vision promotion.

Only anonymous reviewed zones and sanitized counts in this directory may
be public. The SHA/actor mapping is valid **only** for this recording; the other
seven hands and special recording cannot inherit these ROIs or frozen truth.
Executor remains disabled.
