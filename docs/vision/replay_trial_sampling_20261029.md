# Reference replay sampling — 2026-10-29

Compared current trial video replay at explicit 0.3 and 0.2 second source sampling, on the same de1d21b2… recording with bundle 2026.10.25.6, reviewed training exclusions, edge seams, persistent trial pipeline and fresh within-burst identity confirmation. Both modes process alternating windows. OCR was deliberately excluded from this identity/advice diagnostic. This is revealed development data, not independent accuracy or Windows latency validation.

| Source sample spacing | Processed windows | Discard windows | Visible ordinary/kong draw episodes with candidates |
| --- | ---: | ---: | ---: |
| 0.3 s | 158 | 23 | 9/15 |
| 0.2 s | 237 | 42 | 15/15 |

Episode intervals and flower exclusion are from the existing `draw_opportunity_inventory.development.json`. At 0.3 s, episode indices 0,1,5,9,10,12 have no displayed candidate within their visible interval. Coverage is measured at source-frame endpoints; inference completion time is not scheduled. Candidate coverage does not prove candidate correctness, exact-hand accuracy, legal turn attribution or independent generalization. The 0.2 s result reproduces the previously observed 42-discard configuration, rather than establishing a new model improvement.

Only automatic sampling for explicitly selected reference trials is capped at 0.2 s. Explicit caller intervals, ordinary replay, live capture, thresholds and identity freshness remain unchanged. Trial replay now launches every 0.4 s of source time, using three samples spanning 0.4 s. More frames increase offline computation but avoid losing short stable draw appearances.
