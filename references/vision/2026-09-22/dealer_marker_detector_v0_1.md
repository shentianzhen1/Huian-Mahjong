# Dealer Marker Detector V0.1

Date: 2026-09-22  
Issue: #69  
Status: development visual input for Hand Context Assembler

## Goal

Provide one missing opening-context input:

    who currently has the visible dealer marker?

The detector returns only:

- player
- opponent
- UNKNOWN

It does not OCR the dealer count and does not infer dealer base.

## Real evidence

Two archived target-room development sessions expose opposite dealer positions:

### 66fe863f_youjin100

README / settlement evidence identifies the opponent as dealer.

Across six locked gameplay screenshots, the orange/red dealer badge is visible
next to the upper opponent avatar anchor.

### b3892b34_zimo68

README / settlement evidence identifies the local player as dealer.

Across four locked gameplay screenshots, the orange/red dealer badge is visible
next to the lower-left local-player avatar anchor.

These 10 frames are already-reviewed development evidence and are not formal
source-disjoint promotion data.

## Profile

Two narrow normalized anchor zones are used:

    player_marker:
      left=0.115 top=0.640 right=0.170 bottom=0.750

    opponent_marker:
      left=0.655 top=0.005 right=0.695 bottom=0.075

These are not generic river/action ROIs. They are specifically adjacent to the
two persistent avatar/dealer anchors.

## Pixel signature

V0.1 detects saturated orange/red pixels:

- hue < 25 or hue > 170
- saturation > 120
- value > 140

A zone is active only when both hold:

- mask ratio >= 0.030
- largest connected-component ratio >= 0.020

On the locked 10-frame development set:

- active marker mask ratio is >= ~0.059;
- active largest-component ratio is >= ~0.040;
- inactive opposite marker zone is effectively zero in these samples.

This margin is why V0.1 can stay simple and fail closed.

## Ambiguity policy

Exactly one side active:

    actor = player / opponent

Neither side active:

    dealer_marker_unreadable

Both sides active:

    dealer_marker_ambiguous

No tiebreak by score, turn order, or Mahjong rules is allowed.

## Hand Context bridge

`DealerMarkerObservation.to_dealer_evidence(...)` converts actor to canonical
seat only after the caller supplies `player_seat`.

Example:

    observed actor = opponent
    player_seat = 0
    -> dealer_seat = 1

If player_seat is unknown:

    dealer_seat = None

The marker detector never chooses seat numbering itself.

## Dealer count / dealer base

The visible marker includes values such as dealer 3 / dealer 5 in reviewed
frames, but V0.1 deliberately does not OCR or expose those numbers.

Reason:

- marker presence proves dealer actor;
- dealer count/base is a separate state/evidence problem;
- parsing the badge number and translating it into target-room base must not be
  silently bundled into one detector.

Therefore `current_dealer_base` remains UNKNOWN in Hand Context Assembler.

## Safety

- safe_for_hint = false
- safe_for_executor = false
- development evidence only
- no Rules / AI mutation
- machine result enters Timeline only through UNKNOWN-only reconstruction paths

## Next work

Useful next steps:

1. add third-session dealer-marker frames when available;
2. validate live-capture scaling/window transforms;
3. decide whether dealer-count OCR is worth a separate observer;
4. establish explicit player-seat/session mapping evidence;
5. continue end-to-end hand opening -> public action replay evaluation.
