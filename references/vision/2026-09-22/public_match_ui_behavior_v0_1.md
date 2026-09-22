# Public Match Reconstruction — target UI behavior V0.1

Date: 2026-09-22  
Issue: #69  
Scope: archived target-room replay behavior used to design read-only reconstruction

This document records **visual / temporal behavior**, not Mahjong rule truth.
Rule truth remains in `RULE_STATUS.md` and `RULE_EVIDENCE_MATRIX.md`.

## Evidence reviewed

Archived GitHub evidence reviewed before freezing this design:

- `references/gameplay/2026-09-19/match_evidence_001_full_8hand/README.md`
- `references/gameplay/2026-09-19/match_evidence_002_double_you/README.md`
- `references/vision/2026-09-19/drive_8hand_tiles_v0_1_baseline.md`
- `references/vision/2026-09-19/match_evidence_001_region_aware_baseline.md`
- `references/vision/2026-09-19/match_evidence_001_temporal_stability_pilot.md`
- `references/vision/2026-09-19/public_state_v01_baseline.md`
- `references/vision/2026-09-20/public_state_status_multitimepoint.md`
- `references/capture_review/2026-09-13/README.md`
- current `dynamic_geometry.py` and `draw_event_tracker.py`, whose comments/tests preserve previously reviewed target-UI transitions.

Raw private videos are not committed and are not required to define the data contracts below.

## Confirmed / already encoded UI facts

### 1. Hand index and status line

The target room exposes:

- current hand index `N/8`;
- remaining wall count;
- both players' current scores.

The status line can be absent or unstable during opening/transition frames. In the archived 8-hand audit, hand 1 at 5 s had no stable status line while later samples did.

**Design consequence:** do not emit a new hand from one OCR frame. Require a stable hand index or a valid sequential transition. A missing opening status line is UNKNOWN, not hand 0.

### 2. Opening Gold / Jin

Archived capture evidence contains an explicit opening Gold animation. Runtime Vision also treats the public Gold display as its own visual domain.

The current detector distinguishes:

- public Gold display; and
- a yellow highlighted drawn tile that is still semantically `draw_visual`.

**Design consequence:** Gold identity is a public state field. Emit `OPEN_GOLD` only on a stable unknown→known / changed-hand transition, then retain `current_gold` for the hand.

The desired review UI may show `金: <tile>` in the **top-left overlay**. That overlay position is a product presentation choice and must not be confused with the source game's detection ROI.

### 3. Draw tile is a transient visual state

The reviewed target UI uses a separated `draw_visual` tile beside the concealed hand.

The existing temporal tracker preserves the important semantic rule:

- first appearance of `draw_visual` increments concealed count exactly once;
- if another hand tile is discarded, the drawn tile can later merge/re-sort into the concealed hand;
- that later movement is geometry only and must not emit a second DRAW;
- if the drawn tile itself is discarded, it disappears without a hand-resort merge.

**Design consequence:** reconstruct DRAW / DISCARD from temporal state, not slot identity.

Recommended lower-level states remain:

`STABLE_HAND → DRAW_VISIBLE → DISCARD_CONFIRMED → HAND_RESORTING → STABLE_HAND`

or, when the drawn tile itself is discarded:

`STABLE_HAND → DRAW_VISIBLE → DISCARD_DRAWN_TILE → STABLE_HAND`

Animation / resort frames are not classification truth frames.

### 4. Exposed meld layouts change geometry

The archived 8-hand Vision reports explicitly contain exposed-meld states and reject a single fixed 16-slot layout for all mid-hand frames.

Current dynamic geometry contains target-UI-specific recovery logic for observed meld presentations, including:

- exposed faces that can be shorter than upright concealed tiles;
- compact separated meld groups;
- a reviewed stacked `3+1` presentation where an upper face overlaps a lower face;
- dark/partially hidden meld faces that can appear as a gap between aligned visible faces.

**Design consequence:** a meld observer must compare stable meld snapshots/deltas. It must not treat meld components as concealed-hand slots.

### 5. Temporal stability is not recognition accuracy

Archived testing found unchanged tiles that were temporally 100% stable while being consistently assigned the wrong class.

**Design consequence:** multi-frame agreement is necessary but not sufficient. A stable wrong tile identity must still be rejected by the identity/confidence/source-disjoint gates.

### 6. Youjin-family transitions have visible animation evidence

Archived `14.mp4` review records:

- a visible You / 游 animation around 81.5 s;
- a visible Double-You / 双游 animation around 84.5–85.5 s;
- a subsequent terminal settlement displaying Double-You ×8.

The same replay also proves that visible Jin count alone must not define the Youjin stage.

**Design consequence:** maintain a public special-state channel:

- NORMAL
- YOUJIN
- DOUBLE_YOU
- TRIPLE_YOU
- UNKNOWN

State changes require an observed animation / settlement label / other explicit public transition evidence. Never derive stage from Jin count.

### 7. Settlement pages are strong terminal evidence

Archived match evidence records settlement pages with:

- hand number;
- winner / loser score delta;
- method label such as 平胡 / 自摸 / 游金 / 双游;
- fan components;
- multiplier;
- dealer/current base.

**Design consequence:** a generic Hu animation may emit `HU subtype=UNKNOWN`, while a readable settlement page may later upgrade the terminal review record to the displayed subtype. Reconstruction does not invent missing special settlement rules.

## Asymmetric player/opponent observation

This is a critical V0.1 design constraint.

### Player side

The bottom/player concealed tiles are currently observable by identity when Vision accepts them.

For a player claim, evidence may include:

- opponent discard tile;
- exact player concealed identities removed;
- new exposed meld identities.

### Opponent side

Opponent concealed tile identities are not public and must never be fabricated.

For an opponent claim, evidence may include:

- player discard tile;
- opponent concealed **count** decrease, if observable;
- opponent new exposed meld identities.

Therefore `HAND_DELTA` supports both:

- `removed_tiles=[...]` for the visible player hand;
- `removed_count=N` for a concealed opponent hand.

A public meld can still reveal which tiles were consumed after the claim because those tiles are now exposed, but the system must record that their pre-claim concealed identities were not directly observed.

## Action reconstruction rules

### DISCARD

Preferred evidence:

1. new tile appears in actor's discard river / latest-discard region;
2. previous actor hand/draw state loses one semantic tile where observable;
3. tile identity passes the current identity gate.

If identity is uncertain, record `DISCARD tile=UNKNOWN` rather than guessing.

### CHI

Corroborated when:

- other actor's latest discard is tile X;
- new exposed meld is a legal visual three-tile suited sequence containing X;
- claimant concealed count decreases by 2;
- for the player side, exact removed identities should also match the two non-X meld tiles when available.

This is visual consistency only; it does not establish or modify target-room CHI legality.

### PENG

Corroborated when:

- other actor discarded X;
- new exposed meld is XXX;
- claimant concealed count decreases by 2;
- exact player-side removed identities, when visible, are XX.

### MING_GANG

Corroborated when:

- other actor discarded X;
- new exposed meld is XXXX;
- claimant concealed count decreases by 3.

### ADD_KONG

Do not infer from a four-tile group alone.

Require:

- previously stable exposed PENG XXX;
- later stable exposed group XXXX in the same meld position/group;
- claimant concealed count decreases by 1;
- no conflicting discard-claim transition.

### AN_GANG

Not classified in the current V0.1 contract from generic four-tile geometry. It needs a dedicated reviewed temporal signature before automatic labeling.

### HU

- visible generic terminal Hu: `HU subtype=UNKNOWN`;
- explicit terminal/settlement label may provide subtype;
- Youjin-family subtype requires its observed state/terminal evidence;
- unresolved Rob-Kong / Gang-Hu settlement remains rule UNKNOWN even if the visual sequence is reconstructed.

## Proposed observer state machine

### Hand lifecycle

`NO_HAND → OPENING → GOLD_KNOWN → PLAYING → TERMINAL → SETTLED → NEXT_HAND`

Hand-index OCR and score transition are guards; no single frame may jump the state machine.

### Normal player turn

`STABLE → DRAW_VISIBLE → SELECT_OR_DISCARD → DISCARD_CONFIRMED → RESORTING → STABLE`

`SELECT_OR_DISCARD` is an observer concept only. A raised tile / animation may help locate the outgoing tile but is not itself a Mahjong action.

### Claim window

`LATEST_DISCARD → CLAIM_PENDING → MELD_TRANSITION → CLAIM_CONFIRMED → POST_CLAIM_DISCARD`

If discard, hand delta and meld delta do not agree:

`→ EVIDENCE_CONFLICT`

No rule repair is attempted.

### Youjin family

`NORMAL → YOUJIN → DOUBLE_YOU → TRIPLE_YOU`

Only observed/reconstructed public transitions advance this display state. Missing evidence yields UNKNOWN rather than a count-based guess.

## Output views

### Machine review

Persist:

- raw observations;
- reconstructed actions;
- reconstruction evidence grade;
- confidence;
- source/session/frame/time references;
- conflicts / UNKNOWN reasons.

When these machine events are bridged into Hand Timeline, their canonical
`evidence_level` stays `unknown` until explicit human review. Machine
DIRECT/CORROBORATED is not the same thing as rule-evidence confirmation.

### Human hand ledger

Example:

    第 1/8 局
    庄家：对手
    金：SOUTH

    00:06.8 对手 DISCARD M9
    00:12.4 对手 DISCARD P5
    00:13.0 我方 CHI [P3 P4 P5], claimed=P5
    00:14.3 我方 DISCARD E
    ...
    00:52.3 我方 YOUJIN
    ...
    01:14.5 我方 HU DOUBLE_YOU
    01:17.0 SETTLEMENT +264 / -264

### Match ledger

Join eight Hand Timelines without replacing their canonical per-hand JSON. Match view adds:

- 1/8...8/8 boundaries;
- dealer / current Gold;
- score before/after;
- final 8-hand score;
- anomaly index linking back to hand/frame evidence.

## What is still not evidenced enough to hard-code

Do not freeze these as target-UI facts yet:

- exact opponent discard ROI coordinates;
- exact player/opponent river growth direction and wrap layout;
- exact opponent meld-area coordinates and group ordering;
- a dedicated visual signature for AN_GANG;
- persistent on-screen Youjin badge, if any, outside the observed animations;
- generic Hu animation subtype mapping without readable terminal evidence.

These must be learned from reviewed frames/video, not guessed from Mahjong convention.

## Immediate implementation order

1. keep current RawObservation/ReconstructedAction contracts;
2. support player exact hand delta and opponent count-only hand delta;
3. add discard-river snapshot/delta observer;
4. add player/opponent meld snapshot/delta observer;
5. add temporal action assembler using this document's state transitions;
6. bridge resulting actions into Hand Timeline;
7. only then add 8-hand Match Timeline rendering.

Executor remains off.
