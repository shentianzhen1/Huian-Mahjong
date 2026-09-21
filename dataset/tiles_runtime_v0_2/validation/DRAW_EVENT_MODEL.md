# Draw Event Model V0.2

The Vision geometry layer reports what is visible: `hand`, `draw_visual`,
`meld`, `gold`, or `unknown`. A drawn tile is already a concealed tile even
while it is visually separated from the continuous hand.

The temporal layer owns this state machine:

```
STABLE_HAND -> DRAW_STARTED -> DRAW_VISIBLE -> DRAW_MERGING
            -> DRAW_SETTLED -> STABLE_HAND
```

Untrusted, occluded, or animated frames do not update semantic game state. The
tracker keeps one pending draw transaction from first visibility through
settlement. During that transaction the semantic concealed count remains
`hand_region_count + draw_visual_count` from the first trusted draw frame. When
the tile later appears in the hand region, it settles the same transaction; it
does not add another tile.

`DrawEvent` contains `player`, `tile_bbox`, optional `tile_id`,
`first_seen_frame`, `settled_frame`, and `confidence`. `tile_id` remains null
until a later classifier supplies it. This phase does not mutate GameState.

The intended architecture is:

```
Vision observations -> Event Tracker -> GameState -> AI
```

Discard, Chi, Peng, Kong, and flower-replacement tracking can later use the
same observation/event/state separation. Static ROI changes must not directly
mutate GameState.
