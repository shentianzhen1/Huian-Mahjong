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
