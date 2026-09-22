# Player Perspective V0.1

Date: 2026-09-22  
Issue: #69  
Status: explicit seat-namespace bridge

## Purpose

Vision uses screen-relative actors:

- player = local/bottom player
- opponent = the other visible player

Rules, Environment, Settlement and MatchRunner use canonical logical seats:

- seat 0
- seat 1

Those namespaces must not be silently conflated.

Player Perspective V0.1 is the explicit bridge.

## Archived replay evidence

Two already-audited settlement fixtures lock the current development mappings.

### 66fe863f_youjin100

`tests/fixtures/settlement_66fe863f.json` states:

- winner = seat 0;
- dealer = seat 1;
- archived replay analysis follows the local/winning player's bottom hand and
  public actions.

Therefore this replay development session maps:

    local player -> seat 0
    opponent     -> seat 1

### b3892b34_zimo68

`tests/fixtures/settlement_b3892b34.json` explicitly states that seat 0 maps
to the bottom/winning player.

Therefore:

    local player -> seat 0
    opponent     -> seat 1

These are evidence-backed mappings for these source sessions, not a Mahjong
rule saying every future UI must use seat 0 for the bottom player.

## Manifest

`references/vision/2026-09-22/player_perspective_v0_1.json`

Each entry stores:

- source session;
- source video SHA256;
- canonical player seat;
- evidence status;
- fixture/evidence reference.

## Runtime policy

For an archived known session, the mapping may be resolved by:

- source session, or
- source SHA256.

For a new live source, the caller may provide an explicit capture/runtime
configuration such as:

    explicit_player_seat = 0

If no evidence/config exists:

    player_seat_unresolved

If explicit config disagrees with archived source evidence:

    player_seat_evidence_conflict

If the caller supplies **both** session and source SHA256, they must refer to
the *same* archived entry. A mixed pair is rejected even if the two archived
entries happen to use the same player seat, and even if explicit runtime config
would otherwise agree:

    player_source_identity_conflict

A truly new (unarchived) live session/hash pair may still use explicit capture
configuration. Session-only and SHA-only lookup remain available for replay
sources with only one identifier.

The resolver fails closed and returns no seat.

## Dealer-marker integration

Dealer Marker Detector returns screen-relative:

    player / opponent / UNKNOWN

It is converted into `DealerEvidence.dealer_seat` only after the player
perspective is resolved.

Example for 66fe:

    local player seat = 0
    visible dealer actor = opponent
    -> dealer seat = 1

Example for b389:

    local player seat = 0
    visible dealer actor = player
    -> dealer seat = 0

These are covered by real-frame integration tests.

## Score mapping

Hand Context Assembler receives `player_seat` from this bridge.

Only then can PublicState UI score order:

    (top-right, bottom-left)

be converted into canonical seat order.

No seat mapping means no canonical score mapping.

## Boundaries

V0.1 does not:

- infer seat from bottom-screen geometry alone;
- modify Rules/Environment seat semantics;
- infer dealer;
- infer initial dealer history;
- infer next dealer;
- infer player identity from nickname/avatar;
- make a runtime capture profile automatically trusted.

Unknown sources require an explicit mapping.

## Next useful work

With hand number, player perspective and dealer marker now separated cleanly,
the opening reconstruction stack is structurally:

    PublicState
    + Player Perspective
    + Dealer Marker
    + Gold Observation
    -> Hand Context Assembler
    -> HAND_START / OPEN_GOLD
    -> Hand Timeline / Match Ledger

The remaining large Vision bottlenecks are public tile identity coverage and
continuous real-frame action/turn evidence.
