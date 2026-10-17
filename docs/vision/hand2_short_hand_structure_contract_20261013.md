# Three-meld short-hand contract checkpoint — 2026-10-13

Local development record. No Runtime/advisory/Rules/threshold changes.

The advisory validator already derives concealed target as
`(5 - open_melds) * 3 + 2`. With three trusted own exposed groups it accepts
7 concealed tiles before draw or 8 including draw. No new rules or arbitrary
minimum relaxation is necessary in the shanten layer.

Five synthetic tests confirm: trusted three structural UNKNOWN-identity groups
permit seven-tile pre-draw structural shanten and eight-tile noncomplete
post-draw discard analysis; untrusted meld count, only two groups, missing hand
identity or untrusted Gold block. Remaining-copy counts remain unavailable;
Executor stays false. These tests deliberately assert supplied trusted facts
and must not be represented as successful machine recognition of the video.
Existing shanten-advisor nine tests and current-state ten tests also pass.

## Actual detector-path structure

On sequential Hand-2 source ordinals 3334–3338, the original public tile
detector produces exactly three bottom_group candidates. Each complete region
was actually visually reviewed in this session; the source SHA and per-frame
RGB identities are retained privately. Source/frame and region-reviewed flags
represent assistant-reviewed revealed development evidence, not a blind review.

The existing full-frame structure bridge accepts all five frames, each with
three 3-face groups and all tile identities UNKNOWN. Existing MeldSnapshotObserver
with settle_frames=5 establishes a stable trusted baseline at 3338. It outputs
zero action events: there is no before/after meld change in this window. One
separate synthetic trusted=false input is rejected.

This establishes a real reviewed structure-count development path, not live
source qualification or independent-match accuracy. Do not infer CHI/PENG/KONG
semantics or exact identities from three 3-face groups.

## Remaining boundaries

The separate geometric selector prototype correctly assigns 7 hand + 1 draw
and 9 meld faces but retains geometry_untrusted=true under the original
minimum-eight guard. This document does not override that guard. Integrating
trusted short-hand counts requires an explicitly separate advisory boundary
with verified group completeness, actor/source/epoch, stable current hand and
physical count agreement; it cannot be done by changing one numeric minimum.
Actual Gold/hand identities remain unaccepted where original gates reject them.
No manually reviewed tile identity is injected into real machine advice.
