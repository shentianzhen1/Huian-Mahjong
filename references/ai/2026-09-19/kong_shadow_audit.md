# KONG public-information shadow audit

Date: 2026-09-19

Status: **DIAGNOSTIC ONLY — CurrentAgent remains V0.10**

## Question

Can the existing ordinary shanten/live-tile model safely identify useful kong
decisions without guessing unresolved rob-kong or kong-tail settlement rules?

## Implementation boundary

`workspace.ai.analyze_kong_actions()` receives only `PlayerObservation` and the
acting player's legal actions. It does not receive the opponent concealed hand,
wall order, reserved tiles, or simulator truth.

For each legal kong it records:

- the current alternative: PASS for `MING_GANG`, best ordinary discard for
  `AN_GANG` and `ADD_KONG`;
- post-kong ordinary shanten, live effective copies, and effective tile types
  before the mandatory tail draw;
- the adopted kong fan and its evidence status;
- live tail copies that would immediately complete the ordinary shape;
- explicit `rob_kong` and `gang_hu_scoring` blockers.

The recorder is passive. It never changes the action selected by V0.10. Kong
fan and tail-draw timing are not converted into an invented score EV.

## Fixed-seed run

- Seeds: `200000..200049`
- Hands: 50 deterministic V0.10 self-play hands
- Decision points observed: 3491
- Completion: 50/50 (`37 SIMULATION_ZIMO`, `13 SIMULATION_PINGHU`)
- UNKNOWN / loop / step-limit exits: 0

| Metric | Count |
|---|---:|
| All kong opportunities | 11 |
| `AN_GANG` | 7 |
| `MING_GANG` | 2 |
| `ADD_KONG` | 2 |
| Ordinary structure better than current action | 0 |
| Ordinary structure equal | 7 |
| Ordinary structure worse | 4 |
| `gang_hu_scoring` blocker | 3 |
| `rob_kong` blocker | 2 |
| Opportunities with no current rule blocker | 7 |

The 11 opportunities occurred at roughly 0.32% of observed decisions. Exact
structural equality is expected when moving a complete natural triplet/quad from
the concealed zone into a fixed meld. In the four worse cases, the existing
best-discard branch benefits from retaining the option to break the quad.

## Decision

Do not create or promote a kong-taking agent from this signal alone. In this
sample, the CHI/PENG rule of “take only a strict ordinary offense improvement”
would take zero kongs. A useful candidate must value the confirmed kong fan and
the immediate tail draw, while keeping these paths out of the policy until their
unknown settlement dependency is resolved:

1. all `ADD_KONG` opportunities (`rob_kong` response/value unresolved);
2. any opportunity with a live immediate winning tail (`gang_hu_scoring`);
3. any special-state transition not represented by the ordinary model.

The next evidence-safe experiment is a candidate restricted to unblocked
`AN_GANG`/`MING_GANG`, evaluated in shadow first. It must directly beat V0.10 on
fresh fixed walls with seat swaps before promotion.

## Verification

`python -m unittest discover -s tests` passes 315 tests, including five new kong
audit tests for concealed kong, big-ming kong, added-kong blocking, recorder
aggregation, and player/action validation.
