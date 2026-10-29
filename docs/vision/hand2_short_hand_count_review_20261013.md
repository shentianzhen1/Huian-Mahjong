# Independent development short-hand count review — 2026-10-13

Correction: the centre-frame drawn tile is M2, not M3. See
`hand2_gold_draw_truth_correction_20261013.md`; identity interpretation below is
historical and superseded, while geometry/count review and acceptance remain unchanged.

Local checkpoint, no Runtime/Hint/AI/Executor or threshold change. The original
GeometryFrame is never marked trusted or mutated by this new review.

`development_short_hand_review.py` validates count evidence separately:
- exact five consecutive decoded ordinals and retained reviewed RGB identities;
- declared/expected source SHA agreement (caller verifies actual bytes/pixels);
- one source session, own actor, stream epoch and matching component/frame IDs;
- trusted complete meld snapshots settled by the existing five-frame observer;
- each exposed face assigned to exactly one structural group, without hand/draw
  centres inside those groups;
- short concealed count consistent with those groups and at most one draw;
- stable current hand geometry, no unexplained fragments or other fatal issues.

It returns count-only acceptance with advice_allowed=false, safe_for_runtime=false
and safe_for_executor=false. Hash declarations alone are not independent source
verification. No UNKNOWN identity is converted to known, no geometry minimum
is lowered and no physical-copy accounting is inferred from group count alone.

Actual source bytes and all five RGB hashes were checked against the previously
locked private Hand-2 record before invoking this review. Development selector
plus the original public detector/full-frame meld bridge on 3334–3338 passes:
7 hand, 1 draw, 3 structural groups. All source/actor/region review assertions
remain assistant-reviewed revealed development evidence from one match.

## Separate identity diagnostic

Only after count review, original primary classification/identity gates on
the corrected centre-frame crops accept six of eight truth tiles correctly.
Two stay UNKNOWN:
- concealed Gold E: correct raw candidate E, confidence 0.653774;
- draw M3: raw candidate M5, confidence 0.770405.

The unchanged UNKNOWN-only tight-crop diagnostic on draw M3 also rejects:
raw candidate M2, confidence 0.805096. Neither confusion becomes an accepted
wrong identity. The Gold tile is not forced through ordinary-tile normalization.
No whole-hand/shanten/advice success is claimed. This is a corrected-geometry
development diagnostic, not a normal trusted Runtime export.

Validation: three focused tests (including nine negative-case subtests) pass;
four frames, missing RGB binding, source mismatch, actor/epoch/frame mismatch,
untrusted/changed group counts, unknown fragments and other geometry failures
reject. Five short-hand advisory contract tests also pass. Further independent
data and confidence/source support are needed before any production integration.
