# Trial discard scheduling diagnostic — 2026-10-27

At 1024437, replayed the same SHA-locked de1d21b2… recording and manually reviewed draw inventory `references/vision/2026-10-25/draw_opportunity_inventory.development.json`. Fifteen ordinary/kong draw episodes; the flower episode is excluded. The last sampled visible draw frame is only a conservative deadline, not a verified click deadline. This is one revealed match, not independent accuracy or Windows capture validation.

The simulation sequentially decodes frames at 30 fps, captures at 10 Hz even while the worker is busy, uses three latest captures, the actual UI worker with 19-reference bundle 2026.10.25.6, edge seams and source trial enabled, LiveSnapshotStability, current/prior identity freshness and no manual Gold. Single-flight completion advances source time by measured worker duration rounded up to a 100 ms UI tick. An earlier debugging run accidentally omitted captures while busy and did not enable edge seams; its output is invalid and excluded.

| Minimum launch interval | Timely visible draw episodes | Ever produced within episode | Completed bursts | Median host worker time |
| --- | ---: | ---: | ---: | ---: |
| 0.4 s | 11/15 | 15/15 | 199 | 306 ms |
| 0.3 s | 14/15 | 15/15 | 243 | 286 ms |

The first run missed episodes 0, 6, 7 and 12 by 0.1–0.5 s; the second missed episode 12 by 0.1 s. Different captured frame sequences and run-to-run timing prevent causal attribution of the entire difference to the interval; the counts are not per-window ground-truth correctness. First-use classifier initialization is expensive. Captures are replayed on a host, with no Windows mirror, actual UI rendering cost or full game-state/turn validation. No independent match was evaluated. Faster sampling may increase CPU usage; only a real Windows capture can assess it.

Change: the existing explicit hand-source trial uses a 0.3 s minimum launch interval; normal mode retains 0.4 s. Single-flight, three-frame sampling, identity confirmations, freshness, 0.82 threshold, UNKNOWN behavior, AI V0.10 and Executor OFF remain unchanged. The change may improve timeliness; it does not promote the experimental classifier or prove discard safety or accuracy. UI scheduler tests cover both intervals and no overlapping workers; confirmation and switch-boundary tests remain in the focused run.
