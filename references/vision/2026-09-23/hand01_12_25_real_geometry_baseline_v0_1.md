# #69 — first actual offline machine pass on a real continuous recording

**Development only, read-only, source-hashed.** On 2026-09-23 the existing
`public_tile_detector.py` and `public_candidate_tracker.py` from
`main` (`7e486c3a9d30225b9998b834d76579fb8014ddb1`) were executed
on **every source frame 348–725 (12–25 s, 378 frames)** from the exact original
first-hand `3.mp4` (SHA256
`1560c1e04a632f07dc5f53947ba3080ed93ff927a7bd028a457f3415b0bc69a3`).
The separate frozen manual truth was **not loaded during detection/tracking**.
Source PTS was used, with no frame gaps and one continuous tracking epoch.

Run on the locally retained original (the raw recording stays out of GitHub):

```bash
python -m workspace.vision.real_video_public_probe \
  --video /private/path/to/3.mp4 \
  --source-session match_evidence_001_hand_01 \
  --source-sha256 1560c1e04a632f07dc5f53947ba3080ed93ff927a7bd028a457f3415b0bc69a3 \
  --first-frame 348 --last-frame 725 \
  --profile-manifest references/vision/2026-09-22/public_channel_profiles_v0_1.json \
  --output /private/path/hand01_machine_geometry.json
```

This tool deliberately exports **geometry and track events**, **not** machine
Mahjong actions. It does not load manual truth, use replay progress to predict
actions, silently assign upper=opponent on a new source, or convert
`APPEARED` into `DISCARD`. It fails if the video SHA differs, a source frame
is unreadable, or source timestamps go backwards.

## Actual machine-only counts

| Measure | Observed |
|---|---:|
| Decoded source frames | 378 |
| Detector tile-like candidate frame-instances | 5,720 |
| Peak detector candidates in one frame | 30 |
| Stable track frame-instances | 5,627 |
| Stable `APPEARED` events | 61 |
| Stable `DISAPPEARED` events | 46 |
| `central_action_focus_dev` selected appearances | 0 |
| `upper_public_single_dev` selected appearances | 3 |
| `player_exposed_group_dev` selected appearances | 0 |
| Approved actor-qualified river channels for this source | **0** |
| Reconstructed Mahjong actions | **not attempted** |
| Action/actor precision and recall | **not measurable yet** |

The three `upper_public_single_dev` matches occur on the **upper concealed
hand row** at ~frame 350, 500 and 696, not the public river; this profile
cannot be reused as a general opponent-DISCARD channel for the first-hand
capture. In particular **61 candidate track appearances do not mean 61
discards**. The frozen truth has four public DISCARD events, not 61.

## Post-run visual diagnostic only (not a model benchmark)

After locking the independent manual event set, visual checks of the machine
trace found stable public-region candidates shortly after each event anchor.
The detector/tracker **does locate tile-like geometry near all four manual
events**, but it simultaneously creates many non-action tracks and lacks any
approved way to assign river ownership.

| Manual public event frame | Candidate stable appearance frame | Public geometry bbox (normalized x,y,w,h) | Issue |
|---:|---:|---|---|
| 404 opponent 中 | 406 | .617591,.231250,.025813,.062500 | separate first tile |
| 490 player 白板 | 492 | .306883,.535417,.033461,.056250 | separate first tile |
| 587 opponent 北 | 590 | .591778,.229167,.051625,.064583 | **merged with adjacent earlier 中** |
| 685 player 發 | 687 | .307839,.535417,.063098,.056250 | **merged with adjacent earlier 白板** |

These associations were made **post hoc using the same already-reviewed
development video**, and are not independent detection recall. The two merged
2-tile river components reveal a specific current detector problem: treating
one newly expanded component as one track cannot safely yield a one-tile river
delta. The raw local trace SHA256 is locked in the companion JSON; the public
repo includes only anonymized aggregate statistics and geometry bboxes.

## Required next implementation slice

1. Create explicit **source-SHA-qualified upper and lower public river
   profiles**, independently reviewed against original frames and including
   no-action negative examples. Confirm source-specific upper=opponent and
   lower=player, without inferring simulator seat numbers.
2. Detect **tile boundaries inside adjacent 2+ public river tile groups**
   before converting stable track geometry into `RiverSnapshot`. A growing
   component cannot be promoted directly to an additional discarded tile.
3. Only when both actors have trustworthy river snapshots, run
   `DiscardRiverObserver` → `TemporalActionAssembler` and export independent
   machine predictions. Compare those against the **already-frozen**
   `hand01_12_25_action_truth.development.frozen.json` with
   `action_attribution_eval.py`. Report false positives from quiet intervals
   and known actor/turn coverage separately, not just event matches.

This is a genuine machine pass on the real source, **not** a real end-to-end
DISCARD precision result. A new untouched recording is still required for
source-disjoint formal Vision promotion. Executor remains OFF.
