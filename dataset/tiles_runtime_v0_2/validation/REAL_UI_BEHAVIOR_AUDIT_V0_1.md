# Real UI Behavior Audit V0.1

Status: observation complete for the current local archive; implementation paused  
Date: 2026-09-21  
Runtime safety: `safe_for_executor=false`

## Scope and method

This audit precedes further Event Tracker and tile-classification work. It does not change Rules, AI, Simulator, Hint Alpha, Dynamic Geometry, or approved geometry truth.

The local-only scanner examined 24 video sources under `data/capture_validation/`, including the eight sources designated as the full-game set. It sampled every source sequentially at 4 samples per second, used adaptive global and regional frame differences to locate change peaks, and produced 184 candidate windows spanning 1.5 seconds before and after each peak. The archive contains these source resolutions:

| Resolution | Sources |
|---|---:|
| 1108x690 | 19 |
| 1126x698 | 2 |
| 1046x480 | 2 |
| 960x448 | 1 |

Candidate labels from the automatic scan are hypotheses, not event truth. A source-stratified review pack and a denser 0.2-second review pack were inspected manually. Full frames, original paths, and contact sheets remain in the ignored local `work/` tree; the repository contains only this report and an aggregate candidate summary.

## Evidence notation

- **VIDEO_CONFIRMED**: the before/transition/after sequence is visible in reviewed frames.
- **PLAYER_CONFIRMED**: supplied Huian gameplay feedback describes the real UI behavior; it may still need a clean video sequence for timing measurements.
- **OBSERVED_PARTIAL**: part of the transition is visible, but tile identity or the complete beginning/end is not independently established.
- **UNKNOWN**: current footage does not justify a state or subtype.

## Observed real actions

| Behavior | Status | Real visual sequence | Evidence |
|---|---|---|---|
| Ordinary draw becomes visible | VIDEO_CONFIRMED | A new independent tile appears to the right of the continuous bottom hand while the existing hand remains in place. | `session_4d68a8e72498d729`, frames 207-237; `session_781bfe34c40993ef`, frames 213-243 |
| Select a hand tile | VIDEO_CONFIRMED | One bottom-hand tile rises above the shared baseline before leaving the hand. Slot position alone is not persistent identity. | `session_781bfe34c40993ef`, frames 313-329; `session_dcac8580c55879a2`, frames 207-215 |
| Discard a selected tile | VIDEO_CONFIRMED | Raised tile transitions toward the central table/discard area; the bottom hand then stabilizes with one fewer semantic tile. | `session_781bfe34c40993ef`, frames 323-333; `session_dcac8580c55879a2`, frames 211-221 |
| Draw, discard another tile, then auto-sort | VIDEO_CONFIRMED + PLAYER_CONFIRMED | The right-side drawn tile already belongs to the concealed multiset. Another tile is selected/discarded; multiple bottom tiles then change position; the former right-side tile becomes part of the continuous hand. | `session_627b6c2022d3f910`, frames 163-193 |
| Discard the just-drawn tile | OBSERVED_PARTIAL + PLAYER_CONFIRMED | The independent right-side tile is selected and leaves; no semantic draw is produced when the remaining hand stabilizes. Exact tile identity awaits tile classification. | `session_dcac8580c55879a2`, frames 197-227 |
| CHI response | VIDEO_CONFIRMED | `吃/过` controls appear; a combination-choice panel can appear; a large `吃` animation overlays the table; a changed meld/hand layout later stabilizes. | `session_4d68a8e72498d729`, frames 333-363 |
| PENG response | VIDEO_CONFIRMED | `碰/过` controls appear around the triggering discard; a large `碰` animation follows; the meld area and concealed hand subsequently stabilize. | `session_781bfe34c40993ef`, frames 245-275 |
| Pass/response controls disappear | OBSERVED_PARTIAL | A response control such as `吃/过` can disappear without the inspected window showing a CHI animation. Whether this was an explicit pass or timeout is not distinguishable here. | `session_94960e642f407502`, frames 373-403 |
| KONG stacked meld layout | PLAYER_CONFIRMED | A Kong is displayed as three tiles below and one tile stacked above. The clean transition and Ming/An/Bu Kong subtype were not confirmed in this audit. | Player feedback; clean frame sequence still required |
| Opening/deal | VIDEO_CONFIRMED | A large `开局` overlay precedes the initial hand becoming visible. The dealing layout is transitional and must not be treated as stable geometry. | `session_6f17296422fb1534`, frames 187-201 |
| Flower replacement prompt/animation | VIDEO_CONFIRMED | After the opening/deal transition, a large `补花` overlay appears while the hand is still changing. | `session_6f17296422fb1534`, frames 201-204 |
| Self-draw win | VIDEO_CONFIRMED | A `自摸` response control is visible, followed by a large `自摸` overlay. The exposed terminal layout is not a normal concealed-hand observation. | `session_59460988023cc9f1`, frames 31-61 |
| Settlement page | VIDEO_CONFIRMED + PLAYER_CONFIRMED | Gameplay is replaced by a results/settlement layout. The last manually reviewed holdout frame was also confirmed as settlement. | Candidate windows `ui_audit_0124`, `ui_audit_0149`, `ui_audit_0151`; player confirmation |
| Replay controls | VIDEO_CONFIRMED | A large replay transport bar overlays the center/bottom while replayed tile motion continues beneath it. These frames are not valid runtime event evidence. | `session_04bf012ce76304b7`, frames 278-366; `session_0b9561b6e5ce79c3`, frames 75-163 |
| Room creation/loading/waiting | VIDEO_CONFIRMED | Room settings, loading dialogs, and waiting-for-friends scenes replace or obscure the game table. | `session_6bb8fccdc030451c`, frames 111-141 |

## Confirmed state-transition model

The model below separates what the screen shows from what the semantic game state contains.

```text
NON_GAME / LOADING
        |
        v
OPENING_ANIMATION -> DEALING_TRANSITION -> FLOWER_REPLACE_ANIMATION? -> STABLE_HAND

STABLE_HAND
    | new independent right tile; semantically add once
    v
DRAW_VISIBLE
    | select a different tile       | select the drawn tile
    v                               v
TILE_SELECTED                  DRAWN_TILE_SELECTED
    | discard confirmed             | discard confirmed
    v                               v
DISCARD_CONFIRMED              DISCARD_DRAWN_TILE
    |                               |
    v                               v
HAND_RESORTING                 STABLE_HAND
    |
    v
STABLE_HAND

REACTION_PROMPT
    | choose CHI/PENG              | pass/timeout
    v                              v
MELD_ANIMATION                  STABLE/WAITING
    |
    v
MELD_AND_HAND_RESORTING
    |
    v
STABLE_HAND

WIN_PROMPT -> WIN_ANIMATION -> TERMINAL_REVEAL -> SETTLEMENT
```

`HAND_RESORTING`, `MELD_ANIMATION`, opening/dealing, flower replacement, terminal reveal, replay, and large overlays are untrusted geometry periods. Stable geometry resumes only after multiple consecutive frames agree.

## Semantic invariants

1. `draw_visual` is a visual placement, not a separate permanent game zone.
2. A newly observed draw is added to `concealed_tiles` once when the draw event is confirmed.
3. `draw_visual -> HAND_RESORTING -> hand` changes layout only; it must never add the tile a second time.
4. A discard removes only the confirmed discarded tile from the concealed multiset.
5. Automatic sorting invalidates persistent slot identity. State consistency must later use the concealed tile multiset, not “tile at slot N”.
6. Meld and Gold tiles do not count toward the concealed tile count.
7. A static frame may describe geometry, but it must not directly mutate GameState. Only a confirmed temporal event may do that.

## Transition records

| Event | Before state | Transition | After state | Affected regions | Count/position effects | Stable confirmation |
|---|---|---|---|---|---|---|
| DRAW | stable continuous hand | independent right tile appears | `DRAW_VISIBLE` | hand, draw_visual | concealed +1 once; hand-region count may be unchanged | same independent component persists across several frames |
| TILE_SELECT | stable or draw-visible hand | one tile rises above baseline | `TILE_SELECTED` | hand or draw_visual | no semantic count change | raised component persists without global motion |
| DISCARD_OTHER | selected hand tile | selected tile enters table; bottom row moves | `HAND_RESORTING` | hand, draw_visual, discard | concealed -1; many slot positions may change | discard is stable and bottom layout agrees for several frames |
| DISCARD_DRAWN | selected draw tile | right-side tile leaves | stable hand | draw_visual, discard | concealed -1; draw_visual 1->0 | discarded component stable; no second draw emitted |
| CHI | reaction controls | choice panel/large overlay/layout motion | stable meld + hand | prompt, meld, hand | meld grows; concealed geometry decreases/resorts | meld group and hand stable across several frames |
| PENG | reaction controls | large overlay/layout motion | stable meld + hand | prompt, meld, hand | meld grows; concealed geometry decreases/resorts | same as CHI |
| FLOWER_REPLACE | opening or stable hand | `补花` overlay and hand motion | stable hand | overlay, hand, possible draw | timing/count semantics not yet fully established | overlay gone and geometry stable; semantic event remains conservative |
| SELF_DRAW_WIN | win control | large `自摸` overlay/terminal reveal | settlement path | prompt, overlay, all tile regions | terminal state; normal geometry invalid | settlement/terminal scene classification |
| SCENE_REJECT | any | replay bar, room dialog, loading, or settlement replaces/obscures play | non-runtime scene | whole frame | no GameState mutation | scene returns to trusted gameplay before observations resume |

Exact `duration_frames` must remain resolution/FPS/session dependent. The reviewed 10 FPS clips show visible sub-transitions lasting multiple frames, but this audit does not encode a universal fixed duration.

## Required changes to the current Event Tracker design

These are design findings only; implementation is intentionally deferred.

1. Add scene gating before event logic: gameplay, opening/dealing, replay, settlement, loading/dialog, and unknown overlay.
2. Add a visual selection substate for a raised tile. Selection is not a discard until the tile reaches/stabilizes in the discard area.
3. Preserve `HAND_RESORTING`/`POST_DISCARD_RESORT` as a layout-only animation state that cannot emit DRAW or DISCARD events.
4. Treat reaction controls and large action overlays as observations, not sufficient semantic confirmation. Confirm CHI/PENG/KONG only from the stable post-action layout plus the triggering context.
5. Add a discard-area observer and a stable post-state confirmation window. Bottom-hand count deltas alone are insufficient.
6. Represent stacked meld components so the upper fourth Kong tile is meld, not hand/draw/gold.
7. Stop tracking long-lived tile identity by slot index. Once tile classification exists, reconcile before/after concealed multisets with the confirmed draw/discard event.
8. Suppress all stable-hand output during opening, flower replacement, hand resort, meld animation, terminal reveal, replay controls, and obscuring dialogs.
9. Allow overlapping/ambiguous visual hypotheses to return `UNKNOWN`. A Gold tile near the draw location must not be silently treated as draw, nor vice versa.

## Single-frame observations that are usable

Single frames may safely provide observations, not events:

- a stable tile component and its current visual region candidate;
- a visibly raised tile candidate;
- visible response buttons (`吃`, `碰`, `胡`, `过`) as UI affordances;
- a large action overlay (`吃`, `碰`, `自摸`, `补花`, `开局`) as an animation observation;
- replay controls, room dialogs/loading, lobby/waiting, and settlement as scene-rejection evidence;
- a stacked four-tile meld shape as a meld candidate once a clean example is available.

## Behaviors that require continuous frames

- draw appearance and confirmation;
- selection versus transient vertical motion;
- discard confirmation;
- draw-tile discard versus discard-other-then-resort;
- hand automatic resort and its end;
- CHI/PENG/KONG confirmation and stable meld formation;
- flower replacement semantics;
- Gold movement versus hand/draw movement;
- win/terminal transition;
- all GameState mutations.

## Behaviors that must currently return UNKNOWN

- second-tap cancellation of a selected tile;
- changing selection from one tile to another;
- exact Ming Kong, An Kong, and Bu Kong transition sequences;
- whether every Kong stack uses identical orientation/overlap under all seats and skins;
- exact flower entry path before `补花` and replacement-draw timing;
- opponent layout symmetry for every local-player transition;
- Gold relocation rules relative to hand/meld changes;
- Qiangjin, Sanjindao, Youjin, Double/Triple Youjin, Rob-Kong/Gang-Hu, and other special-result UI sequences not cleanly evidenced here;
- prompt disappearance when explicit pass and timeout cannot be distinguished;
- any frame obscured by a large overlay, replay transport, popup, loading state, or unresolved animation;
- any transition where geometry changes but no stable before/after state is available.

## Audit limitations and next gate

- The scanner selected the eight largest user-designated recordings as the full-game set; several files are short segments, so completeness of every individual hand was not independently reconstructed.
- Automatic candidate recall is intentionally broad. Candidate-type counts are not event-frequency statistics.
- Exact tile identities were not used; apparent examples are treated as geometry/transition evidence only.
- Current footage confirms CHI and PENG transitions, but not clean subtype-complete KONG transitions.
- The audit found enough architectural evidence to revise the Event Tracker specification, but not to resume implementation blindly.

Before Event Tracker implementation resumes, the transition table should be converted into explicit observation/event contracts and regression fixtures. Missing high-impact sequences should be collected or marked `UNKNOWN`; they must not be filled by inferred Mahjong behavior. Phase 6 remains paused by this audit decision, and `safe_for_executor=false` remains unchanged.
