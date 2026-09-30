# First-hand real Gold M6 review target — 2026-09-30

Issue: #69  
Status: **private-source review target / NOT an approved label**

The first-hand human audit provides a stronger review target than the earlier
generic Gold-M6 diagnostic window:

- logical source session: `session_eight_hand_match_a`;
- scan window: **170–176 seconds**;
- strongest visual check: **174–175 seconds**;
- visible state: two yellow Gold-skinned M6 copies remain in the player's
  concealed area immediately before the Youjin terminal sequence.

This file records only an anonymized logical session and time window. It does
not publish the private video, source URL, Drive ID, source hash, full frame,
room/player identifiers, or a guessed bbox.

## Required workflow

1. Run `gold_skin_review_queue` against the private original recording for
   170–176 seconds, reusing `session_eight_hand_match_a`.
2. Review the exported tile-only proposals against the original source frame.
3. Accept a crop only if the tile is visibly M6, the crop is tile-only, and the
   yellow Gold skin is intact.
4. Admit the exact reviewed crop with
   `reviewed_tile_intake --gold-skin-only --tile-id M6`.
5. Rerun source-disjoint Gold identity evaluation and Runtime smoke at the
   unchanged **0.82** threshold.

No proposal may be auto-approved. A montage/contact sheet may be used for
localization but must not be admitted as a Runtime training crop because it is
rescaled/compressed relative to the original frame.

The earlier ~110-second Gold-M6 experiment remains a separate diagnostic
record. Do not merge the two source/session claims unless original-media
provenance proves they are the same logical match.

`safe_for_hint=false`; `safe_for_executor=false`.
