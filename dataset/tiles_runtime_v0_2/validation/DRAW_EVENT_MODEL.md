# Draw / Discard / Hand-Resort Event Model V0.2

The Vision geometry layer reports what is visible: `hand`, `draw_visual`,
`meld`, `gold`, or `unknown`. A drawn tile joins the concealed multiset as soon
as a trusted `draw_visual` appears. Its later screen position does not add the
tile again.

## Observed UI paths

When another concealed tile is discarded:

```
STABLE_HAND -> DRAW_VISIBLE -> DISCARD_CONFIRMED
            -> HAND_RESORTING -> STABLE_HAND
```

When the newly drawn tile itself is discarded:

```
STABLE_HAND -> DRAW_VISIBLE -> DISCARD_DRAWN_TILE -> STABLE_HAND
```

`HAND_RESORTING` (also called post-discard resort) is a UI animation. It changes
visual layout only. It never changes the concealed count and never emits a new
draw or discard. During this state `stable_for_hint=false`.

Example count flow:

```
stable:          hand=10, draw_visual=0, concealed=10
draw visible:    hand=10, draw_visual=1, concealed=11
discard another: semantic concealed=10
hand resort:     semantic concealed=10 (geometry untrusted)
stable:          hand=10, draw_visual=0, concealed=10
```

The draw event is emitted exactly once when `draw_visual` first becomes
trusted. A separately confirmed discard decrements the semantic count exactly
once. The discard confirmation must say whether the source was `hand`,
`draw_visual`, or `unknown`; unknown fails closed and does not mutate the count.

No slot index is treated as a persistent tile identity. Once tile
classification exists, consistency must use concealed-tile multisets:

```
after = before + drawn_tile - discarded_tile
```

Automatic sorting may move many components, so slot-to-slot correspondence is
not evidence of tile identity.

## Annotation policy

Frames captured during automatic sorting use:

```json
{"frame_state": "animation", "animation_type": "hand_resort"}
```

Their boxes may be retained as visual audit evidence, but the frames are
excluded from stable component, region, slot, and hand-count metrics. Only a
later motionless trusted frame is stable geometry truth.

The intended architecture remains:

```
Vision observations -> Event Tracker -> GameState -> AI
```

This phase does not modify GameState, Rules, AI, Simulator, Hint Alpha, or the
Executor.
