# Public Match Reconstruction V0.1

Date: 2026-09-22  
Issue: #69  
Status: read-only foundation

## Purpose

Turn a match recording or live capture into an auditable public-event stream that is useful for:

- reviewing one hand without replaying the whole video;
- reconstructing all eight hands as a match ledger;
- finding rule conflicts and UNKNOWN nodes;
- extracting exact clips/screenshots for later rule evidence;
- feeding future trusted public state into Hint Alpha without enabling Executor.

This is not a rule engine and is not a Vision promotion claim.

## Product-facing target

A review view should eventually read like:

    Hand 1/8
    Dealer: opponent
    Gold: SOUTH

    00:06.8  opponent DISCARD M9
    00:09.1  player DRAW P3
    00:10.0  player DISCARD S9
    00:12.4  opponent DISCARD P5
    00:13.0  player CHI
              claimed=P5
              consumed=P3,P4
              meld=P3,P4,P5
    ...
    00:52.3  player YOUJIN_STATE=YOUJIN
    ...
    01:14.5  player HU subtype=DOUBLE_YOU
    01:17.0  SETTLEMENT +264 / -264

If a subtype or transition is not sufficiently supported, the stream must say UNKNOWN.

## Pipeline

Capture / video frame

→ raw visual observers

→ RawObservation stream

→ Public Action Reconstructor

→ ReconstructedAction stream

→ Hand Timeline JSON

→ deterministic Markdown review

→ 8-hand Match Timeline

→ anomaly / rule-evidence review

## Separation of responsibilities

### Raw observers

Raw observers report only what was visible:

- hand index text;
- dealer marker;
- Gold/Jin tile;
- discard candidate;
- hand count / identity delta;
- meld-area snapshot / delta;
- Youjin-family animation or state marker;
- Hu animation / settlement page;
- score / remaining / other PublicState fields.

They do not decide target-room legality.

### Reconstructor

The reconstructor combines independent observations into public actions.

For a claimed meld, a high-confidence action requires consistency across:

1. the other player's public discard;
2. claimant concealed-hand delta;
3. claimant new exposed meld.

For the visible player hand, the delta may contain exact removed tile identities.
For the opponent concealed hand, the contract requires only a count delta; hidden
tile identities must never be fabricated. The new exposed meld makes the consumed
tiles public after the claim.

Example:

    opponent DISCARD P5
    player hand removed P3,P4
    player meld added P3,P4,P5

becomes:

    player CHI claimed=P5 consumed=P3,P4 meld=P3,P4,P5

If the three sources disagree, emit EVIDENCE_CONFLICT instead of choosing one.

### Timeline

Hand Timeline is the human/machine review record. It stores reconstructed events plus provenance. It is not allowed to silently upgrade UNKNOWN rule evidence to confirmed rule truth.

## Evidence grades

- DIRECT: one UI fact is directly visible and can stand alone, such as Gold=SOUTH or a visible discard.
- CORROBORATED: two or more independent observations agree on one public action.
- INFERRED: a temporal interpretation is derived from observations but is not directly displayed.
- UNKNOWN: missing, ambiguous, or contradictory evidence.

A numeric confidence remains useful for detector quality, but confidence alone never changes UNKNOWN into a confirmed semantic event.

## V0.1 action model

Direct facts:

- HAND_START
- OPEN_GOLD
- DISCARD
- YOUJIN_STATE
- HU
- SETTLEMENT

Cross-evidence actions:

- CHI
- PENG
- MING_GANG
- ADD_KONG

Safety outputs:

- UNKNOWN_ACTION
- EVIDENCE_CONFLICT

AN_GANG is intentionally not classified from a generic four-tile visual group yet. The observer must first provide evidence that distinguishes a concealed Kong from an added/exposed Kong.

## Youjin policy

The reconstruction layer may display:

- NORMAL
- YOUJIN
- DOUBLE_YOU
- TRIPLE_YOU
- UNKNOWN

It may preserve an observed active state over time.

It must not invent the trigger predicate from tile count or Jin count. The Rules/Environment state machine remains the rule authority.

## Hu policy

A visible Hu terminal can be recorded as HU.

The subtype is only attached when supported by public evidence, for example:

- settlement text;
- explicit Youjin/Double-You/Triple-You terminal state;
- verified rob-kong sequence plus terminal evidence;
- other direct target-room UI evidence.

If only a generic Hu animation is visible, subtype stays UNKNOWN.

## Full-match storage target

Future persisted review bundle:

    match_<id>/
      manifest.json
      hand_01/
        observations.jsonl
        actions.jsonl
        timeline.json
        timeline.md
      ...
      hand_08/
      match_timeline.json
      match_timeline.md
      anomalies.json

Raw private video does not need to be committed.

## Rule-evidence bridge

When the reconstructed public action contradicts current executable expectations, create a review anomaly such as:

    RULE_CONFLICT
    timestamp=35.4
    observed_action=CHI
    reconstruction_grade=CORROBORATED
    rule_status=UNKNOWN

The reconstruction layer must not patch Rules automatically.

## V0.1 acceptance

- contracts are importable without optional Vision dependencies;
- direct facts preserve UNKNOWN;
- CHI/PENG/MING_GANG require consistent discard + hand delta + meld delta;
- ADD_KONG requires explicit previous-Peng evidence;
- contradictory evidence emits EVIDENCE_CONFLICT;
- output converts into existing Hand Timeline events with provenance;
- no Executor, Hint advice, AI version, or Rules behavior changes.
