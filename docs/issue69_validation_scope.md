# Issue #69 validation scope

Status: superseded for the V0.1 advisory test target by
`docs/issue69_advisory_state_scope.md`.

This checkpoint narrows manual validation without weakening the fail-closed
evidence contract. It does not change Rules, AI, Simulator, Hint, Runtime
promotion, or Executor behavior.

## Layer 1: representative Hand 1 closure

Hand 1 is the only hand that receives a representative end-to-end manual
closure in V0.1.

Required stages:

- opening / dealer / Gold facts when directly observed;
- player and opponent public-action sequence at evidence-backed checkpoints;
- discard-river and exposed-meld transitions when independently observed;
- Youjin/Hu terminal state when visible;
- settlement and score transition when visible.

A zero-gap exhaustive ledger is not required. Missing tile identity, actor,
turn, river placement, or action semantics remains `UNKNOWN`. Candidate
animation, prompts, or rule expectations cannot fill evidence gaps.

## Layer 2: Hands 2–8 scenario coverage

Hands 2–8 are sampled for distinct visual and temporal cases. They are not
manually transcribed event by event.

| Scenario | Minimum V0.1 evidence | Fail-closed condition |
|---|---|---|
| Normal discard | stable public-river growth sample | identity/actor uncertainty stays UNKNOWN |
| Dense or second-row river | stable count/frontier transition | overlay, reflow, or multi-slot jump is rejected |
| CHI | discard + hand/meld consistency when available | one cue alone is insufficient |
| PENG | discard + meld-delta consistency when available | one cue alone is insufficient |
| KONG | action-area/meld/hand evidence when available | subtype is UNKNOWN without corroboration |
| Flower replacement | visible flower/replacement transition | no rule-based backfill |
| Gold | directly visible opened Gold fact | no concealed inference |
| Ting prompt | prompt presence only | disappearance does not prove PASS or draw |
| Youjin family | visible state/terminal evidence | trigger rules are not invented |
| Hu and settlement | visible terminal/score transition | subtype/amount stays UNKNOWN if obscured |

Coverage is satisfied by representative, provenance-preserving samples. It is
not an accuracy claim and does not require every scenario to appear in every
hand.

## Layer 3: eight-hand automated replay

All eight hands remain replay/regression inputs. The automated harness must
report separately:

- decoded/rejected source intervals;
- geometry candidates;
- known versus UNKNOWN tile identity;
- actor/action candidates;
- false positives and false negatives against available frozen truth;
- conflicts and abstentions;
- terminal/settlement observations.

Synthetic tests and green CI do not establish real-video accuracy. Development
recordings do not become independent blind holdouts.

The first complete Hand 1 machine-replay checkpoint is recorded in
`docs/issue69_hand1_full_machine_replay.md`. It demonstrates partial river
signal only and does not satisfy complete-flow reconstruction.

## Historical full-replay exit criteria

- Hand 1 has a representative evidence-backed opening-to-settlement closure.
- Hands 2–8 have a compact scenario-coverage matrix.
- Eight-hand replay can run without cross-source evidence leakage.
- Missing/conflicting evidence fails closed to `UNKNOWN`.
- Existing focused tests and final CI are green.
- Executor remains OFF and no merge to main occurs without explicit approval.

These full-replay criteria remain an offline reconstruction milestone. They are
not required before testing read-only shanten and public-danger assistance.
