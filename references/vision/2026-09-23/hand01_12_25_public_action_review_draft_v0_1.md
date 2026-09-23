# #69 — hand 1, 12–25 s: four visually corroborated action candidates

**Status: DRAFT / UNFROZEN / DEVELOPMENT ONLY.** The original `3.mp4`
SHA256 is `1560c1e04a632f07dc5f53947ba3080ed93ff927a7bd028a457f3415b0bc69a3`,
confirmed against its archived original. These notes are based on the user's
existing recording, not a source-disjoint or newly held-out recording.

We extracted the original video frames, inspected before/after pairs and
navigated the 12–25 s interval with quarter-second filmstrips and a per-frame
image-change scan of the two concealed hands, two public zones, central action
focus and replay progress. **Automated image differences are not semantic
human truth**; four visible actions are preliminary reviewer hypotheses.
Original video bytes, Drive IDs, and personally identifying UI screenshots
have **not** been committed to the public repository.

| ID | First-visible source frame | Approx. recording time | Visual evidence | Actor (source-specific, user-confirmed) |
|---|---:|---:|---|---|
| A | 404 | 13.931 s | Upper hand loses **中**; public upper-right **中** appears; central enlargement is secondary corroboration | opponent (upper) |
| B | 489 | 16.862 s | Bottom hand loses **白板**; matching left public tile appears | player (lower) |
| C | 587 | 20.241 s | Upper hand loses **北**; public upper-right **北** appears; central enlargement is secondary corroboration | opponent (upper) |
| D | 684 | 23.586 s | Bottom hand loses **發**; matching left public tile appears | player (lower) |

Source frames are **zero-based** and all recording-relative. Times refer to
the **first visibly changed public-zone frame**, not independently measured
touch/click time. The evaluator's temporal tolerance must not be treated as
evidence of more precise onset. The four candidate onsets correspond to replay
progress moving from 1/18 through 5/18, but **进度 N/18 is replay/action
progress, not 第N/8局**. The source settlement independently identifies this
as the first of eight hands.

## Source-specific actor mapping confirmed

The user directly confirmed on **2026-09-23** that, **in this exact
recording**, the lower detailed-hand UI shows their own hand (`player`) and
the upper hand is `opponent`. The actor side for A/C is therefore opponent
and for B/D is player. This confirmation does **not** independently verify
that all four candidate actions or first-visible frame timestamps are
correct, and **does not establish simulator seat 0 or seat 1**. Do not apply
a generic lower=player rule to a different recording.

## Remaining requirements before truth freeze

Review the complete continuous 12–25 s interval without model overlays,
including all intervening quiet/no-action frames and moments covered by
replay controls. Confirm that all four proposed discards are the entire set
of qualifying public actions, or correct the draft if additional or
obscured actions are found. `review_stage` stays
`first_pass_unfrozen_not_exhaustive` and `truth_frozen=false` until that
separate review passes. Then create a strict, independently frozen
`public_action_attribution_eval_v0_1` truth batch **before** running or
inspecting model predictions.

No measured actor-attribution precision, turn coverage, event precision,
recall, or false-positive rate is claimed by this draft. Turn actor remains null for all four candidates
unless a separate visible turn signal is verified. Executor stays OFF.
