# Issue #69 — Hand 1 full machine-replay checkpoint

Status: **PARTIAL_RIVER_SIGNAL_ONLY**

This privacy-safe checkpoint records one complete, no-frame-skipping replay of
Hand 1 through the current source-qualified river pipeline. It is a development
diagnostic, not formal promotion evidence, a blind holdout, or a real-video
accuracy claim. Private source hashes, frame indexes, timestamps, screenshots,
and geometry remain outside the repository.

## Run summary

| Item | Result |
|---|---:|
| Frames decoded | 10,922 |
| Stream epochs | 1 |
| Player river-growth observations | 8 |
| Opponent river-growth observations | 7 |
| Assembled actions | 15 |
| UNKNOWN-graded actions | 15 |
| Known-tile actions | 0 |
| Player untrusted frames | 6,137 |
| Opponent untrusted frames | 2,838 |
| Safe for Executor | no |

The assembled candidates contain only `DISCARD`-shaped river-growth events.
They do not identify the tile, do not establish the turn actor independently,
and do not reconstruct draw, CHI, PENG, KONG, flower, Youjin, Hu, or settlement
events.

## Diagnostic comparison boundary

The machine output was compared privately with the latest corrected Hand 1
evidence only to locate gaps. Approximate time/side proximity was not treated as
an exact-frame match, and the result is not reported as precision or recall.
The machine sequence stops well before the reviewed terminal flow and misses
most of the known public-action ledger.

The current recognizer therefore **cannot reconstruct the complete Hand 1
flow**. It can presently surface a partial set of river-growth candidates while
failing closed on identity and unsupported semantics. Keeping all 15 actions at
`UNKNOWN` is the correct safety behavior.

## Required next increments

1. Add scene/phase segmentation so river tracking is initialized only after a
   stable table state and survives dense-row/reflow transitions.
2. Add source-qualified exposed-meld and action-area observers to the full-hand
   orchestrator instead of running the river observer alone.
3. Add terminal and settlement observers with independent evidence contracts.
4. Join observer outputs through the temporal assembler while preserving
   abstentions and conflicts.
5. Add periodic progress reporting for long full-resolution replays.

Executor remains OFF. No result in this checkpoint changes runtime promotion,
Rules, AI, Simulator, or Hint behavior.
