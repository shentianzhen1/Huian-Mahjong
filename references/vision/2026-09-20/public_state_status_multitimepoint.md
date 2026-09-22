# PublicState status-line multi-timepoint baseline — 2026-09-20

## Scope

This closes the old "eight seed frames only" blind spot for the existing
`match_evidence_001` replay batch.

The same eight anonymized hand sessions were sampled at:

`5 / 10 / 15 / 20 / 25 / 30 / 40 / 50 seconds`

That produces 64 timepoints.  The first hand at 5 seconds does not yet show a
stable status line, so remaining-wall accuracy has 63 scorable samples.  Hand
number remains a 64-sample field.

Truth is archived in
`match_evidence_001_public_state_multitimepoint_truth.json`.

This is **same-batch** evidence.  It does not replace the independent-session
validation requirement and never makes Vision Executor-safe.

## Existing primary Status Reader

Using the current normalized ROIs and current Tesseract parser without any
fallback:

| field | readable | correct | readable coverage | accuracy when readable | exact rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| remaining wall | 53 / 63 | 44 | 84.13% | 83.02% | 69.84% |
| hand number | 50 / 64 | 46 | 78.13% | 92.00% | 71.88% |

The earlier ~10-second seed check remains true (remaining 8/8, direct hand
7/8), but it was not representative of the full recordings.

The full-timepoint audit exposes two different failure classes:

1. **unreadable/invalid OCR** — safest failure; the parser returns `None`.
2. **false-valid OCR** — more important; the parser returns a physically
   allowed integer, but it is wrong.

Examples of false-valid remaining-wall reads:

| session / time | OCR | parsed | truth |
| --- | --- | ---: | ---: |
| session_01 / 30s | `107` | 107 | 101 |
| session_04 / 25s | `17` | 17 | 101 |
| session_04 / 40s | `90` | 90 | 96 |
| session_06 / 25s | `17` | 17 | 101 |
| session_06 / 30s | `107` | 107 | 101 |
| session_06 / 50s | `20` | 20 | 96 |
| session_08 / 15s | `109` | 109 | 105 |
| session_08 / 40s | `17` | 17 | 101 |
| session_08 / 50s | `35` | 35 | 99 |

Examples of false-valid hand-number reads include session_06 6/8 → 2/8 and
session_08 8/8 → 5/8.  This is why a parser-range check alone is not a sufficient
Executor gate.

## Conservative remaining-count fallback

Visual inspection showed a repeatable narrow failure: the primary
`remaining_tiles` ROI sometimes includes the leading edge of the following
Chinese glyph.  Tesseract then appends a spurious final digit, e.g. `98 → 985`.

An **always-tightened** ROI was rejected because it regressed some previously
correct samples.  The accepted change is narrower:

- run the existing primary ROI first;
- if and only if the primary value is unparseable, trim the rightmost 14% of
  that already-normalized ROI and retry once;
- never replace a valid primary parse.

On this same 64-timepoint batch, all 10 previously unreadable remaining-wall
samples recover correctly under this fallback:

- session_01/40s: `` → `9/` → 97
- session_02/50s: `985` → `98`
- session_03/40s: `985` → `98`
- session_03/50s: `985` → `98`
- session_04/30s: `` → `99`
- session_04/50s: `` → `94`
- session_05/40s: `995` → `99`
- session_05/50s: `985` → `98`
- session_06/40s: `` → `99`
- session_07/50s: `975` → `9/` → 97

Because the fallback is gated on primary parse failure, all 53 primary-readable
samples remain untouched.

Same-batch result after the fallback:

| field | readable | correct | readable coverage | accuracy when readable | exact rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| remaining wall | 63 / 63 | 54 | 100.00% | 85.71% | 85.71% |

The nine false-valid primary reads remain intentionally unresolved.  No
character-specific hard map is added for them.

## Score context

The score reader is not newly re-benchmarked here.  Its existing benchmark
already uses the same 64 timestamps and remains 64/64 constrained score pairs
on this same replay batch.  This document must not be read as independent score
generalization evidence.

## Engineering decision

- Keep the new fallback because it only activates on primary failure and has a
  clear UI-crop explanation.
- Do **not** force-repair false-valid values from hand-written substitutions.
- Keep `safe_for_executor=false`.
- Use the merged multi-timepoint evaluator to track raw versus fused behavior.
- Next useful work is to make temporal invariants reject/suppress false-valid
  reads, then verify on a completely new recording session.

