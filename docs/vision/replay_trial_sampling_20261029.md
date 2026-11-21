# Reference replay sampling — 2026-10-29

Compared current trial video replay at explicit 0.3 and 0.2 second source sampling, on the same de1d21b2… recording with bundle 2026.10.25.6, reviewed training exclusions, edge seams, persistent trial pipeline and fresh within-burst identity confirmation. Both modes process alternating windows. OCR was deliberately excluded from this identity/advice diagnostic. This is revealed development data, not independent accuracy or Windows latency validation.

| Source sample spacing | Processed windows | Discard windows | Visible ordinary/kong draw episodes with candidates |
| --- | ---: | ---: | ---: |
| 0.3 s | 158 | 23 | 9/15 |
| 0.2 s | 237 | 42 | 15/15 |

Episode intervals and flower exclusion are from the existing `draw_opportunity_inventory.development.json`. At 0.3 s, episode indices 0,1,5,9,10,12 have no displayed candidate within their visible interval. Coverage is measured at source-frame endpoints; inference completion time is not scheduled. Candidate coverage does not prove candidate correctness, exact-hand accuracy, legal turn attribution or independent generalization. The 0.2 s result reproduces the previously observed 42-discard configuration, rather than establishing a new model improvement.

Only automatic sampling for explicitly selected reference trials is capped at 0.2 s. Explicit caller intervals, ordinary replay, live capture, thresholds and identity freshness remain unchanged. Trial replay now launches every 0.4 s of source time, using three samples spanning 0.4 s. More frames increase offline computation but avoid losing short stable draw appearances.

## 2026-11-21 check with PublicState OCR

Ran the first 90 seconds of the revealed Sep26 source (SHA-256
`9709fdc3aa464bf2e4f111554931e2ae9867c5270cf384fcaae7811da5b97c8b`) at
`a6cec184c2b857077ce1a337a8b21cf8e224618f`. Both runs used the bundled
`2026.10.30.1` reference packet, local dark-meld trial, automatic visual Gold,
the standard PublicState OCR reader, and the 0.82 identity threshold. Linux
OpenCV 5.1.0 was limited to one OpenCV thread per run. The processes overlapped,
so wall times describe this comparison environment only.

| Source sample spacing | Processed windows | Shanten displayed | Discard windows | First display | Wall time |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0.3 s | 149 | 92 | 42 | 2.4 s | 114.3 s |
| 0.2 s | 224 | 151 | 68 | 2.0 s | 152.0 s |

Of 74 shared endpoint frames, 46 displayed advice in both runs, two only at
0.2 s, and 26 in neither. The 21 shared endpoints with discard candidates
were the same at both cadences. These counts measure display availability per
sampled window. They do not count independent draw opportunities or verify
advice correctness.

Primary blocked-window categories at 0.2 s were geometry (39), hand-boundary
confirmation (20), hand identity (12), and stability (2). The denser run spent
89.1 seconds in OCR across 62 sampled reads and 60.4 seconds in Runtime. No
decode interruptions or OCR exceptions occurred in either run. This remains
a revealed offline development comparison, with no Windows live latency or
independent promotion claim.

### Exact-crop OCR reuse

At 0.2 s the 62 sampled OCR windows consumed 124 distinct source frames.
Frame ordinal caching would yield zero hits. A replay-local cache instead
reused 250 of 896 OCR crop requests by exact prepared pixels, shape, and
dtype. The separate score and status caches made 646 backend calls.

On the same 90-second run, all 224 windows' OCR observations, Runtime
observations, hints, and timeline matched the uncached report after removing
timing fields. Two-frame fusion still runs for each fresh OCR window. The
uncached run overlapped the 0.3 s benchmark and the cached run ran alone, so
their wall-time difference is not a controlled speed estimate.

### Where geometry fusion blocked advice

Re-decoded the 100 distinct frames used in the 39 primary geometry blockers
from the 0.2 s run, using the same byte-verified Sep26 source, local meld trial
detector and OpenCV 5.1.0. All 39 reproduced the recorded fusion rejection
reason. The burst-level results were:

| Trusted detector frames out of three | Blocked windows |
| --- | ---: |
| 3, with differing region counts | 24 |
| 2 | 4 |
| 1 | 4 |
| 0 | 7 |

For the 24 windows where all frames were trusted, region counts varied for
`draw_visual` in 15, `unknown` in 9, `hand` in 8 and `meld` in 3. Categories
overlap. These are detector observations; they do not identify which frame is
correct or distinguish actual game motion from unstable region classification.
For windows with rejected per-frame geometry, `component_count_outside_reviewed_range`
appeared in 13 windows and `component_size_inconsistent` in two.

Failed-fusion reports now retain the real frame ordinal, trust flag, detector
issues and per-region counts for each member of the burst. The three-frame
agreement rule and all decision thresholds are unchanged.

### Visible draw transitions and a short dense replay

Reviewed all three frames for the 15 bursts whose draw-region counts differed
while all frames passed single-frame geometry. Eight spanned a tile arriving
or becoming fully visible in the draw slot (endpoints 84, 300, 684, 1332, 1836,
2028, 2136, 2268). Seven spanned a tile leaving the slot or rearrangement after
an action (36, 144, 528, 1452, 2052, 2196, 2304). Six arrivals had a discard
suggestion at the next 0.2 s sampled burst endpoint, 0.4 s later. Frame 2136
was the flower sequence; the later suggestion was on the replacement draw.

The ordinary P4 draw around frame 2268 had no discard suggestion during its
visible opportunity at 0.2 s. On a new 72–79 s replay of the same SHA-verified
source with the same 2026.10.30.1 references and OCR, 0.1 s produced a
single P4 discard candidate at frame 2292 (76.4 s, structural shanten 0).
The 0.2 s replay reached the same endpoint with P4 accepted in its current
frame but insufficient prior identity confirmation. The neighboring 0.1 s
endpoints still rejected a P5 top candidate. This is one recovered display
in a revealed clip, with no change to the deployed cadence or identity gate.

| Sample spacing | Processed windows | Shanten displayed | Discard windows |
| --- | ---: | ---: | ---: |
| 0.2 s | 17 | 10 | 2 |
| 0.1 s | 34 | 22 | 5 |

Reproduce with `python -m workspace.hint_alpha.video_cli VIDEO --output REPORT --start 72 --duration 7 --sample-interval 0.1 --reference-packet MANIFEST`
and repeat with `0.2`. Use the same video, reference manifest and dataset in
both runs. The 0.1 s replay is a targeted diagnostic and its three-frame
burst spans 0.2 s.

### 90-second dense replay comparison

Expanded 0.1 s to the first 90 seconds of the same Sep26 development source
at `99a2811`. Compared against the cached 0.2 s run from the same source,
start, duration, reference manifest, identity threshold and advice policy.
The intervening code changes added diagnostic output and CLI options.
Both runs used Linux OpenCV 5.1.0 and the default PublicState reader.

| Sample spacing | Processed windows | Shanten displayed | Discard windows | Wall time |
| --- | ---: | ---: | ---: | ---: |
| 0.2 s | 224 | 151 | 68 | 126.4 s |
| 0.1 s | 449 | 325 | 150 | 201.4 s |

All 224 baseline endpoints had matching endpoint RGB hashes in the dense
report. On those shared endpoints, the dense run gained 10 advice windows
including seven discard windows. No existing shared-endpoint advice was
lost. When both runs displayed advice, the shanten values, phases and discard
candidate sets matched. The other 225 endpoints accounted for 164 advice
windows and 75 discard windows. The P4 discard at frame 2292 also reproduced
in the longer run. These counts describe advice output on one revealed
recording. They do not validate new suggestions or measure independent draw
recall. The default remains 0.2 s for the reference trial.

Compare JSON reports with
`python -m workspace.hint_alpha.replay_compare BASELINE.json CANDIDATE.json`.


### Oct12 cross-recording check

Ran both cadences on the first 45 seconds of the already revealed Oct12
recording, SHA-256 `de1d21b2a722d02f0866e03caf595d1d706551e689c313c9f413553e466ee81c`,
using replay code `99a2811`, the same bundled 2026.10.30.1 references, default
PublicState OCR, and identity threshold 0.82. Both processes overlapped, so
their wall times describe this run only.

| Sample spacing | Processed windows | Shanten displayed | Discard windows | Wall time |
| --- | ---: | ---: | ---: | ---: |
| 0.2 s | 112 | 75 | 21 | 73.2 s |
| 0.1 s | 224 | 164 | 46 | 103.6 s |

All 112 baseline endpoints matched candidate endpoint pixel hashes. Five
shared endpoints recovered advice from geometry rejection, including two
discard candidates (frames 324 and 924). No baseline advice was lost. On the
75 shared endpoints displaying in both runs, the concealed-hand multiset,
Gold, shanten, phase and discard candidates matched. The 112 additional
endpoints contributed 84 advice windows and 23 discard windows.

The comparison now checks concealed-hand and Gold agreement where both
reports display advice, and counts the primary blocker on gained or lost
shared endpoints. Across the two revealed sources, 14 of 15 shared gains
came from baseline geometry rejection and one from identity stability.
This is display availability on development footage. It does not validate
the newly recovered hands or establish independent draw-level recall.


### Visual review of newly displayed endpoints

Re-decoded and verified the RGB hash of every one of the 15 shared endpoints
that gained advice at 0.1 s. Current-frame visual review agreed with the
Runtime concealed tile multiset, opened-gold indicator and own meld group count
at all 15 endpoints. The same shanten engine on manual inputs matched all
phases, shanten values and candidate sets, including the nine discard windows.
The P4 at Sep26 frame 2292 is an ordinary draw, with S8 as the opened Gold;
the earlier description of P4 as Gold-skinned was incorrect.

The [reviewed frame records](../../references/vision/2026-11-21/dense_replay_reviewed_gains.development.json)
bind transcriptions to source and frame SHA-256. Review followed prediction
inspection and covers endpoint frames only. It does not confirm all earlier
burst frames, hand-action legality, exposed meld identities, or blind accuracy.

Use the reviewed endpoints as a local regression check by adding
`--reviewed references/vision/2026-11-21/dense_replay_reviewed_gains.development.json`
to the comparison command. The check selects the reviewed frames by source
SHA-256 and checks the candidate report's endpoint hashes, concealed hand,
opened Gold, own meld count, phase, shanten, and discard set. Missing or
blocked endpoints and value mismatches are reported by ordinal and return a
nonzero exit status. The two original dense reports match 10/10 and 5/5
reviewed endpoints respectively.

### Initial hand confirmation and opened Gold

Rechecked the first eight seconds of the revealed Oct12 recording. The
visible opened Gold is M4. At 0.1 s, the old policy first confirmed hand 1
at frame 126, resetting earlier experimental Gold just as the raw Gold
classifier returned a below-threshold M1 candidate. M4 regained the trial
gate at frame 156. Visual re-review of the relevant endpoint frames showed
M4 throughout that dropout. Earlier windows before the Gold appeared or
before its geometry stabilized still abstain.

In reference replay, the initial unconfirmed hand now gets the same
hand-only two-distinct-frame reads available during a pending transition.
Initial or sequential consensus is still required for a reset.

| Cadence | First confirmed hand frame, before → after | Displayed windows, before → after | Discard windows, before → after |
| --- | ---: | ---: | ---: |
| 0.2 s | 132 → 84 | 7 → 9 | 2 → 2 |
| 0.1 s | 126 → 72 | 15 → 20 | 4 → 4 |

The 0.2 s baseline is the opening slice of the previous 45-second replay.
Endpoint RGB hashes and the already displayed phases, shanten values and
discard candidates matched in both comparisons. This is a short, revealed
development check scoped to reference replay. Live capture is unchanged.

### Longer regression after initial hand retry

Re-ran the Sep26 90 s and Oct12 45 s sources at 0.1 s on `7316be1`. All
673 shared endpoint RGB hashes matched the prior reports. Sep26 retained
325 advice and 150 discard windows. Oct12 increased from 164 to 169 advice
windows and retained 46 discard windows. All five gains were previously
blocked by opened Gold at frames 126–150. Previously displayed phases,
shanten values and discard sets matched on both sources, and all 15 reviewed
endpoints passed the automated check. OCR backend calls were unchanged on
Sep26 (640) and increased from 403 to 443 on Oct12.

Reference replay reports now include `public_rows[].gold_hand_boundary`,
with the prior and current confirmed hand, pending state and reset reason
(`initial_hand`, `sequential_hand`, or null). A separate 0.2 s Oct12
opening run confirmed the first-hand reset at frame 84 on a fresh hand-only
read, with unchanged advice summary and timeline after adding this trace.

### Full Oct12 draw-episode coverage

Replayed the complete 94.9 s Oct12 development recording at `c28cdb0`,
with the same 28-reference packet and real PublicState OCR. Checked each
reviewed draw interval from the source-matched inventory, excluding its
flower interval. A qualifying display has a POST_DRAW discard candidate
at a sampled endpoint inside the inclusive reviewed frame interval.

| Cadence | Replay windows | Discard windows | Reviewed draw episodes covered | Wall time |
| --- | ---: | ---: | ---: | ---: |
| 0.2 s | 237 | 41 | 15/15 | 156.0 s |
| 0.1 s | 474 | 90 | 15/15 | 226.0 s |

The denser replay had its first discard endpoint six source frames earlier
in 11 episodes and 12 frames earlier in four (0.2–0.4 s at 30 fps).
Neither cadence added a reviewed episode over the other. At shared
frame 2664, 0.1 s lost one existing discard window because the fresh
hand-only read had no reliable hand index. That episode already had a
discard candidate at frame 2598. Both processes overlapped. The earlier
source-frame positions do not measure live completion latency or candidate
correctness. Retain the 0.2 s reference replay default.

Use `--draw-inventory references/vision/2026-10-25/draw_opportunity_inventory.development.json`
with the replay comparison command to reproduce the episode counts.

### Frame 2664 hand-index dropout

Re-decoded the eight OCR input frames around the lost shared endpoint.
A game overlay crosses the top of the visible hand number in all six
samples at 2655, 2658, 2661, 2664, 2667 and 2670. Tesseract returned
empty text on both existing crops for each sample. After the overlay
cleared, the existing expanded crop read 1/8 at both 2673 and 2676.
Advice resumed at frame 2676 without a Gold reset. The 0.2 s replay did
not run a fresh OCR read at 2664 and was still using its earlier result.
This is a temporary occlusion, so the pending-hand gate is retained.

The hand-boundary trace now records the latest OCR vote count and hand
value, and distinguishes an unreadable hand, insufficient confirmation,
an unexpected hand index, and an OCR error.

Replay summaries now group consecutive pending windows under
`public_state.hand_boundary_pause_intervals`. Each interval records the
sampled endpoints, observed pause reasons, and the first endpoint where
the boundary clears. Clearance time is measured in source video seconds;
a cleared boundary can still leave advice blocked by a different gate.
An interval ending with the recording has no measured clearance.

Applied to the saved 0.1 s Oct12 full report, this yields two cleared
pauses (0.2 s and 0.6 s, both without a Gold reset) and one interval
unresolved at the end of the recording. The 0.6 s pause spans three
pending windows, with the boundary clearing at frame 2676.
