# Hand Context Assembler V0.1

Date: 2026-09-22  
Issue: #69  
Status: read-only opening-context bridge

## Goal

Build the opening header of a reconstructed hand from already-observed public
facts:

- hand index (1/8 ... 8/8);
- local player seat mapping;
- initial score pair in canonical seat order;
- dealer seat when independently observed;
- Gold/Jin tile when independently observed;
- room options supplied by the caller.

The output is the canonical `huian.evidence.timeline.HandContext` used by the
Hand Timeline and Chinese Match Ledger.

## Inputs

### PublicStateObservation

Provides:

- hand number;
- top-right score;
- bottom-left score;
- remaining count / PublicState issues.

The UI score order is **not** the canonical seat order.

The assembler only converts it after the caller supplies `player_seat`.
Bottom-left is treated as the local-player UI score; no seat number is guessed
from screen position.

### DealerEvidence

A separate small contract:

- timestamp;
- dealer seat 0/1;
- confidence;
- evidence refs.

Dealer is accepted only after configurable consensus.

The assembler never infers dealer from:

- who acts first;
- current score;
- score magnitude;
- Mahjong convention;
- current dealer base.

### Gold observations

Uses existing `RawObservation(kind=GOLD)`.

Gold is accepted only after configurable identity consensus. A conflict remains
unknown.

## Output

`HandContextDraft` contains:

- hand_index;
- HandContext;
- issues;
- evidence refs;
- opening timestamps;
- safe_for_hint=false;
- safe_for_executor=false.

The draft can emit opening actions:

    HAND_START
    OPEN_GOLD

These go through the existing ReconstructedAction -> Timeline bridge, so
canonical `TimelineEvent.evidence_level` remains `unknown` until explicit
review.

## Score mapping

PublicState score order is:

    (top_right, bottom_left)

If `player_seat=0`:

    canonical scores = (bottom_left, top_right)

If `player_seat=1`:

    canonical scores = (top_right, bottom_left)

If player seat is unknown, the assembler keeps `initial_scores=None` rather
than attaching scores to guessed seats.

## Dealer base

`current_dealer_base` remains `None` in V0.1.

A visible dealer marker proves dealer identity, not the current chained dealer
base. The assembler does not derive base from historical assumptions.

## Fail-closed behavior

Examples:

- no hand index -> `hand_index_unknown`;
- score unreadable -> `initial_scores_unknown`;
- player seat absent -> `player_seat_unknown`;
- no dealer marker -> `dealer_unreadable`;
- dealer disagreement -> `dealer_consensus` / `dealer_tie`;
- Gold disagreement -> `gold_consensus` / `gold_tie`;
- PublicState issues are preserved with a `public_state:` prefix.

A draft can still be useful when incomplete. The Ledger should display unknown
fields rather than inventing defaults.

## Why this matters for whole-match reconstruction

The public reconstruction chain now has an explicit opening segment:

    PublicState + dealer marker + Gold
      -> Hand Context Assembler
      -> HandContext
      -> HAND_START / OPEN_GOLD
      -> Hand Timeline
      -> 第 N/8 局 / 庄家 / 金 / 开局比分

This closes the structural gap between PublicState and the existing action
timeline.

## Not included

V0.1 does not:

- implement dealer-marker pixel detection;
- infer player seat from UI geometry;
- infer dealer base;
- infer room options;
- promote machine facts to confirmed evidence;
- enable Hint or Executor.

Those remain separate evidence/observer tasks.
