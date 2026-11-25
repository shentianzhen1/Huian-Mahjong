# Offline cluster selection probe — 2026-10-13

Local checkpoint; production `dynamic_geometry.py` is unchanged. The separate
`development_cluster_geometry.py` is a revealed-data hypothesis, not a Runtime
promotion. No identity/threshold/rule/AI/Executor changes.

The raw component inventory at Hand-2 ordinal 3336 already contains the seven
concealed faces and detached draw. The largest contiguous cluster instead has
nine shorter exposed faces. `max(clusters, key=len)` selects that cluster and
then assigns the first actual concealed face as draw. Ting badges are visible,
but the failure is not proven to be caused by them; sufficient hand components
exist before cluster selection.

Development selector retains the largest cluster unless there is exactly one
multi-face alternative with taller bodies, larger height/width ratio and lower
bottom baseline. It uses no tile identities, expected hand count or fixed x
coordinate. Its geometric constants are development choices, not independently
validated gates. Ambiguity preserves the old result and cannot establish trust.

Revealed real-window results (five sequential frames each):
- 832–836: 16 hand + 1 draw, no meld candidates, unchanged counts;
- 2083–2087: 13 hand + 1 draw + 3 meld faces, unchanged counts;
- 3334–3338: 7 hand + 1 draw + 9 meld faces, corrected counts.

Correct counts still require box/body and identity review. No advice acceptance
is claimed. The existing minimum-eight component guard stays unchanged: all
five corrected short-hand frames remain `geometry_untrusted=true`, reason
`component_count_outside_reviewed_range`. Do not lower this minimum globally
or treat the geometry-only nine meld faces as three trusted meld groups.
Future short-hand acceptance needs independently trusted own meld grouping and
physical hand-state validation through the advisory layer.

The experiment passed all 12 existing dynamic-geometry synthetic tests via the
development detector, plus five focused cluster-selector tests. Neither these
tests nor this one original match establish generalization. Next verify exact
automatic boxes and regress other source-qualified short-hand/multiple-meld
layouts before considering an isolated production change.
