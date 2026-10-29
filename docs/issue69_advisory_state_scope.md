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

The representative first-hand real window at approximately 174 seconds now
reaches the advisory gate as `PARTIAL` with `SHANTEN` enabled. The same
three-frame burst trusts all 11 visible concealed tiles and the opened Gold M6.
A visually incomplete second player meld cluster is preserved only as a
count-only UNKNOWN meld after the concealed hand count independently implies
the same two-meld structure. No missing meld tile identity is guessed.

For that real snapshot the ordinary structural shanten bridge returns `-1`
(`POST_DRAW_COMPLETE`). This means only that the ordinary 5-meld + pair
structure is complete under the current Gold wildcard model; it is not a claim
that every Huian special-state or Youjin condition is satisfied.

Public remaining-copy and danger capabilities remain closed because river and
exposed-meld identities are not yet complete/trusted. This is therefore a real
basic-shanten checkpoint, not a formal Vision promotion or Executor gate.

## Gold identity cross-session gate

Gold-skin classification normalizes away the yellow UI skin and ranks the
underlying face against the complete reviewed template bank. Its cross-session
identity gate therefore aggregates approved base-tile evidence across
`hand_region`, `draw_visual`, and `gold_region`, while still requiring at
least two distinct source sessions. Multiple crops from one match cannot
self-validate.

M6 Gold-skin identity is now closed for the representative first-hand window
without lowering the live confidence threshold of `0.82`.

Evidence roles are deliberately separated:

- the current runtime session is still excluded from classifier templates and
  from cross-session identity support, so the reviewed yellow M6 crop cannot
  self-match;
- a reviewed `gold_skin_only` crop is only proof that the class has been seen
  under the real yellow UI skin;
- exact M6 identity still has to pass confidence/category gates and retain at
  least two non-target logical source sessions of identity support.

With that separation, the two yellow M6 copies in the 174-second window are
accepted at approximately `0.8317` and `0.8213` while the target session is
excluded from training. Source-disjoint Gold evaluation also keeps the reviewed
real yellow M6 as top-1 M6 at approximately `0.8265`, above `0.82`, with
runtime-gated accepted accuracy remaining 100% in the development report.
