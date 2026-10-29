# Concealed Gold reference trial

The explicit private-packet adapter accepts a row with `role: concealed_gold`, `truth`, `crop`, and `rgb_sha256`, alongside existing packet metadata. The crop path is relative to the selected manifest. Use only reviewed tile-only private crops.

This role creates a concealed-Gold wrapper outside the opened-indicator classifier. It delegates ordinary and opened-indicator methods unchanged. Reference scoring searches one feature pixel of translation using replicated borders to absorb small crop shifts. A weak full-bank prediction can receive a reference score only when the passing reference classes uniquely agree with its original identity. Confident original predictions remain unchanged. Scores are developmental NCC, not calibrated probabilities.

Loading such a row does not change source coverage, cross-session qualification, training labels, or ordinary/neutral/inner features. The caller's existing explicit trial/source rules still apply; adding a reference does not qualify a class for default Runtime.

Validation: eight focused tests pass, including role parsing, ordinary/opened method isolation, agreement/disagreement, confident pass-through, and unchanged source coverage. A reviewed SOUTH training crop confirms wiring through self-match; this is not held-out accuracy. The explicit 26-row private trial packet now replaces all manual reference-feature bank mutations in the revealed 76–90 second replay. Across 34 paired windows, compared hands, Gold, shanten, discard candidates, issues and display status match the earlier candidate. Ten windows display advice: four from the old hand and six from the new hand. This is same-source development replay, not independent accuracy.

The installed 19-reference manifest and default runtime behavior remain unchanged. No private new pixels or installer are included in this change.
