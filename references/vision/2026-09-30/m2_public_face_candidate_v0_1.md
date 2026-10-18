# M2 public-face candidate — 2026-09-30

Issue: #69  
Status: **public candidate retained; concealed Runtime gap RESOLVED**

The enlarged public M2 evidence in
`references/gameplay/2026-09-15/66fe863f_youjin100/fourth_p1_visible_069000ms.jpg`
was deliberately **not** relabelled as a concealed tile.

A later review of the user's private match recording located a clean M2 in the
actual player `hand_region`. Only the privacy-bounded tile crop was promoted
to Runtime V0.2; the full source frame/video and private path remain outside the
repository.

Tracked Runtime evidence:

- tile: `M2`;
- region: `hand_region`;
- anonymous logical session: `session_eight_hand_match_a`;
- asset: `templates/hand/tile_a6df97037ce092fb_M2.png`;
- role: development/prototype only.

This closes the previous Wan-suit class-completeness blocker. It does **not**
make M2 itself trusted at runtime: M2 still has only one stored concealed
logical session and must fail the cross-session identity gate.

The original public/action M2 remains useful only as public-domain reference
evidence. It was never used to fake concealed coverage.

`safe_for_hint=false` and `safe_for_executor=false` remain unchanged.
