# Concealed Gold reference trial

The explicit private-packet adapter accepts a row with `role: concealed_gold`, `truth`, `crop`, and `rgb_sha256`, alongside existing packet metadata. The crop path is relative to the selected manifest. Use only reviewed tile-only private crops.

This role creates a concealed-Gold wrapper outside the opened-indicator classifier. It delegates ordinary and opened-indicator methods unchanged. Reference scoring searches one feature pixel of translation using replicated borders to absorb small crop shifts. A weak full-bank prediction can receive a reference score only when the passing reference classes uniquely agree with its original identity. Confident original predictions remain unchanged. Scores are developmental NCC, not calibrated probabilities.

Loading such a row does not change source coverage, cross-session qualification, training labels, or ordinary/neutral/inner features. The caller's existing explicit trial/source rules still apply; adding a reference does not qualify a class for default Runtime.

Validation: eight focused tests pass, including role parsing, ordinary/opened method isolation, agreement/disagreement, confident pass-through, and unchanged source coverage. A reviewed SOUTH training crop confirms wiring through self-match; this is not held-out accuracy. The explicit 26-row private trial packet now replaces all manual reference-feature bank mutations in the revealed 76–90 second replay. Across 34 paired windows, compared hands, Gold, shanten, discard candidates, issues and display status match the earlier candidate. Ten windows display advice: four from the old hand and six from the new hand. This is same-source development replay, not independent accuracy.

The installed trial bundle is now version `2026.10.30.1`, with 28 user-authorized tile-only reference images (20 ordinary, 7 opened-indicator, 1 concealed-Gold). It was packaged at `7f1a86e`. These remain development references; source qualification and the strict default identity gates are unchanged.

The raw Runtime component now records `concealed_gold_reference_supported` for a Gold-skinned hand/draw component when the loaded reference layer supports the current prediction at the unchanged threshold. This is diagnostic evidence only: it does not convert UNKNOWN to an admitted identity or alter the hand-source trial policy.

The 2026-11-01 activation check uses the shipped bundle directly on decoded frames 2640/2646/2652 of the known Sep26 recording. The existing trial policy already accepts the complete 16-tile hand and reports 4 shanten; disabling trial blocks it. There is no newly recovered window from this audit. A separate test confirms that even a supported reference cannot silently bypass `class_missing_real_gold_skin_example`. Thirty-nine focused tests pass. No installer was rebuilt for this diagnostic change.
