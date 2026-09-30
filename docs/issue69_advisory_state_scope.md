# Issue #69 — advisory current-state scope

Status: **V0.1 TEST TARGET**

The V0.1 test target is read-only shanten and public-danger assistance. A
complete action-by-action reconstruction is not a release gate. The product
boundary is a source-qualified, stable current-table snapshot that can recover
after a missed animation without inventing the missing historical action.

## Required current state

| Capability | Required trusted observations | Failure behavior |
|---|---|---|
| Basic shanten | complete player concealed hand, opened Gold identity, player exposed-meld count | suppress shanten |
| Live effective-tile counts | basic shanten state plus complete public rivers and exposed-meld identities | show structural shanten only |
| Public danger hint | complete hand plus both public rivers and exposed melds | suppress danger hint |

The snapshot must also preserve source session and stream epoch, reach the
minimum stable-frame window, reject impossible fifth copies, and allow at most
three playable copies of the opened Gold. Any physical conflict blocks every
advisory capability.

## Explicit non-requirements

- exact reconstruction of every draw/discard animation;
- classification of the button press that caused an exposed meld;
- opponent concealed-hand identity;
- full Youjin/Hu/settlement reconstruction;
- exact action timestamps or an exhaustive eight-hand manual ledger.

Full-hand and eight-hand replay remain useful offline regression inputs. They
are no longer V0.1 usability gates and cannot establish real-video accuracy by
themselves.

## Safety boundary

The current-state gate reports capabilities separately. Unknown public tile
identity may still permit structural shanten while blocking remaining-copy and
danger calculations. Unknown hand or Gold identity blocks shanten. No state is
safe for Executor, and Executor remains OFF.

## Runtime adapter checkpoint

The Runtime V0.2 stable-burst report now feeds this current-state contract.
Player concealed identities, opened Gold and player meld count come from the
same Runtime report. Optional river and opponent-meld snapshots are joined only
when actor, source session and stream epoch match; cross-source inputs are
dropped.

A private real-window smoke check reached the gate and correctly remained
`BLOCKED` because concealed identities were incomplete and Gold was not trusted.
This is a connectivity and abstention result, not a real-video accuracy claim.

The runtime geometry now retains multiple yellow-skinned faces that occupy
concealed hand/draw geometry instead of removing one as a standalone Gold
region. Gold-skin normalization also crops to the dominant tile face before
ranking, so an adjacent Ting overlay is not treated as part of the tile. In a
private smoke window, both retained copies ranked the same expected candidate,
but both remained `UNKNOWN` because their scores were below the acceptance
threshold. The snapshot therefore remained `BLOCKED`; this is still an
abstention check, not an accuracy claim.

## Gold identity cross-session gate

Gold-skin classification normalizes away the yellow UI skin and ranks the
underlying face against the complete reviewed template bank. Its cross-session
identity gate therefore aggregates approved base-tile evidence across
`hand_region`, `draw_visual`, and `gold_region`, while still requiring at
least two distinct source sessions. Multiple crops from one match cannot
self-validate.

A separate older replay was reviewed and contains visible M6 concealed faces,
but that replay renderer does not preserve the live yellow Gold skin. Those
frames are only candidates for base M6 identity intake; they are **not**
Gold-skin appearance evidence and are not counted as an approved template until
the privacy-reviewed crop and source-session provenance are added to the
dataset. The live confidence threshold remains `0.82`; no threshold was lowered
to make the current M6 candidate pass.
