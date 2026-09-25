# Issue #69 — live system prompts versus archived replay controls

**Date:** 2026-09-25. **Status:** source-review policy + tested read-only
development tracker; no validated live button OCR / no action promotion.

## Why the capture mode is a prerequisite

The original supplied materials are eight clips of ONE original eight-hand
match plus the existing `14.mp4` replay of ONE other original match.
They are useful for reviewing **actual visible river/meld/hand changes**
and existing action timings, but they are *not* samples of a live
interactive action button dialog.

For this update, source frames at roughly **25%, 50%, and 75%** of
each of the existing nine video clips were privately sampled and visually
reviewed. **All 27 sampled source frames show the replay transport strip**
with the four `重播 / 暂停 / 返回 / 下一步` controls. They must be
treated as **negative controls** for LIVE system-action-prompt recognition.
This count is *sample coverage*, not 27 independent matches, not proof that
every original video frame has the overlay, and not an OCR accuracy metric.

The September 25 screenshot similarly shows video in the phone gallery
with playback controls. A lookalike UI control or a game `过` icon in an
archived replay is not evidence that a current live player was offered
or selected PASS.

The private 27-frame contact sheet and original video files are **NOT**
uploaded to public GitHub. This note intentionally includes no private
video filenames, original SHA values, raw crops or player/room identities.

## Owner-corrected UI semantics

- **Cancel concealed-hand shadow recognition.** Hand geometry, verified
  tile identities and the physically separate `draw_visual` tracker remain
  valid independent data. Dimming is not a reliable eligibility mask.
- **System live prompt = offered actions only.** Record verified game
  action buttons `吃 / 碰 / 杠 / 胡 / 过`; several can be offered at once.
  The button set cannot prove which one the player selected.
- **Ordinary 摸:** comes from independent stable drawn-tile geometry, not
  from a prompt disappearing or a guessed `摸` OCR label.
- **CHI:** require observed preceding discard, actual newly exposed meld
  and, where obtainable, independent hand count/identity change. Later
  SHA-bound shaded *exposed-meld* position is an OPTIONAL follow-up cue
  on the suited sequence, not the action timestamp.
- **PENG/KONG:** exposed tiles have identical identities, so no shaded
  acquired-position is needed. A four-face-looking blob alone also does
  not establish a Kong; use independently verified source regions.

## New implementation

`workspace/vision/public_action_prompt.py` now requires BOTH:
(1) independent `LIVE_INTERACTIVE` source-mode attestation that did not
use the candidate button labels, and (2) separately reviewed LIVE frame
and button-region evidence. Existing archived replay footage receives
`IN_GAME_REPLAY` and is categorically ineligible for positive live
prompt training or live offer observations.

`workspace/vision/public_prompt_window_tracker.py` builds a bounded
source-scoped UI offer history from successive verified frames:

| Emitted transition | Allowed conclusion |
|---|---|
| `PROMPT_OPENED` | Stable set of live offered choices, NOT a completed action |
| `PROMPT_OPTIONS_CHANGED` | Different stable choices on the same offer window |
| `PROMPT_DISAPPEARED_UNATTRIBUTED` | Buttons stably absent; PASS/DRAW/CHI/PENG/KONG all still UNKNOWN |
| `PROMPT_INTERRUPTED_UNKNOWN` | Replay, overlay, bad ROI, missing frame, source/epoch change or unresolved PASS-only screen; discard unsupported interpretation |

Unstable one-frame blinking does not emit a new action. Different original
sessions and stream epochs never share a prompt window; all emitted events
have local IDs and public-safe metadata without the original video SHA
or filenames. Source proof and reviewed crop bytes must remain private.

The tracker is **not** yet integrated into the production Hand Timeline:
its output is a development-only parallel UI-observation stream.
The existing `TemporalActionAssembler` remains responsible for actual
independently corroborated DISCARD + HAND_DELTA + MELD_DELTA; the existing
draw_visual tracker remains responsible for DRAW. No prompt window can
modify actual reconstruction evidence grades or executor behavior.

## Regression and acceptance

Run with the optional Vision dependencies installed:

    python -B -m unittest discover -s tests -p "test_public_action_prompt.py" -v
    python -B -m unittest discover -s tests -p "test_public_prompt_window_tracker.py" -v

In GitHub, merged #113's generic root-public Vision lane automatically
runs both, with synthetic positive live offers and negative
replay/session/epoch/ROI/frame-gap cases. This CI does NOT use private
video frames; the 27-frame replay contact-sheet inspection above is
separate source-local manual evidence.

**Remaining acceptance:** a source-verified LIVE game-button pixel/OCR
detector needs real interactive popup examples; the nine current archived
replays cannot establish its recall or precision. Integrate only when
live-source and replay-negative controls are separately measured. #69
still requires independent real-video river+hand+meld corroboration and
owner action-event adjudication; the seven prior CHI-like development
candidates remain unconfirmed canonical event truth.
