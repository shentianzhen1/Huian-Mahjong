# PublicState V0.1 — target-room replay baseline

Date: 2026-09-19

## Scope

PublicState is intentionally separate from tile recognition. It reads only
public UI information needed by the 8-hand match state:

- top-right player score;
- bottom-left player score;
- remaining wall count;
- current hand index `N/8`.

Player avatar/nickname content is not recognized. All outputs remain
`safe_for_executor=false`.

Evidence is anonymized as `match_evidence_001`.

## Score Reader V0.1

Existing score reader benchmark on the same 8 replay sessions:

- sample times: 5/10/15/20/25/30/40/50 seconds;
- 64 score pairs / 128 individual score ROIs;
- raw single-threshold OCR: **125/128 = 97.66%**;
- constrained score-pair result: **64/64 = 100%** on this replay batch;
- 63/64 were direct conserving pairs;
- 1/64 inferred the missing side from the unique readable score;
- every accepted pair obeyed `score_a + score_b = 2000`.

The 64/64 result is a same-batch system result, not a claim of external OCR
generalization.

The validated threshold path remains the default. A grayscale/autocontrast OCR
pass exists only as an explicit diagnostic fallback and is not the default gate.

## Remaining-wall and hand-index seed baseline

Dedicated normalized ROIs were added for the yellow numeric fields inside the
status line. Tesseract uses only `0123456789/`.

The target UI font has a repeatable quirk: glyph `7` is often OCR'd as `/`.
The parser therefore treats `/` as `7` only in the tightly scoped numeric
positions where that ambiguity is structurally valid.

Stable ~10-second seed frames:

| session | score pair | remaining raw -> value | hand raw -> direct |
| --- | --- | --- | --- |
| session_01 | 1000 / 1000 | `10/` -> 107 | `1/8` -> 1 |
| session_02 | 1026 / 974 | `108` -> 108 | `2/8` -> 2 |
| session_03 | 958 / 1042 | `10/` -> 107 | `3/8` -> 3 |
| session_04 | 980 / 1020 | `105` -> 105 | `4/8` -> 4 |
| session_05 | 1004 / 996 | `106` -> 106 | `0/8` -> unreadable |
| session_06 | 1080 / 920 | `105` -> 105 | `6/8` -> 6 |
| session_07 | 1105 / 895 | `105` -> 105 | `//8` -> 7 |
| session_08 | 1077 / 923 | `105` -> 105 | `8/8` -> 8 |

Seed results:

- remaining-wall count: **8/8 correct** after the scoped `7 -> /` font correction;
- direct hand index: **7/8 correct**;
- session_05 does not silently map `0/8` to 5.

For the one missing hand index, PublicState allows exactly one conservative
repair: if the previous accepted hand is known, the trusted 2000-conserving
score pair changed, and the next hand is at most previous+1, the missing hand may
be inferred as the next hand. Therefore session_05 is recovered as hand 5 from:

```text
previous = hand 4, scores 980/1020
current scores = 1004/996
hand OCR = unreadable
=> infer hand 5
```

With this sequential transition rule, the 8 seed frames become **8/8 complete
(score pair + remaining wall + hand index)**.

## Unified PublicStateReader

`public_state_reader.py` now combines:

1. `public_state_scores.py`
2. `public_state_status.py`
3. `fuse_public_state()`

A frame read stays advisory. A nearby-frame window is accepted only through the
same physical/temporal guards:

- score total = 2000;
- multi-frame consensus;
- optional `MatchScoreState` cross-check;
- same-hand scores cannot change;
- hand index cannot regress or jump;
- remaining wall count cannot increase inside the same hand.

## CI / packaging

- Vision CI installs Tesseract OCR explicitly.
- Vision module and PublicState imports work outside the repository root after
  project installation.
- Current Vision regression includes score preprocessing, status parsing,
  target-font 7/slash correction, score-transition hand inference, and unified
  candidate composition.

## Remaining gaps

This is still same-batch evidence. Before Executor can use PublicState:

1. run remaining-wall / hand-index evaluation across more timepoints, not only
   one seed frame per hand;
2. test a completely independent recording session;
3. stress-test window scale, move and partial occlusion;
4. confirm behavior around settlement/opening transitions where the status line
   may be absent or changing;
5. keep any unreadable/inconsistent state advisory rather than forcing a value.

Executor remains disabled.
