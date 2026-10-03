# STACKED visible-face identity: development slice

Audited base: PR #117 `9f90ab45628482f35c601c63904c91246ac0ae0b`.
The four-case meld structure matrix is implemented. It does not certify face
identity. The canonical `prepare_public_meld_faces` still returns no STACKED
classifier crops; private visible-face splitter validation from another window
must not be treated as a committed splitter.

`rank_stacked_visible_identity` is an offline, score-only diagnostic entry point.
It requires the three reviewed roles `top`, `lower_left`, `lower_right` and explicit
source-frame/face-review qualification. Upstream scorers must enforce exact
source SHA and original-match exclusion before supplying scores. Boolean review
flags are caller declarations, not pixel or lineage verification performed by
this decoder.

The output keeps three visible observations separate from four physical tiles.
Same-tile hypothesis ranking preserves each face's independent winner and flags
disagreement/ties. A missing competitor has no measured margin. Agreement never
fills the occluded identity, emits an action, or opens Runtime/Hint/Executor.
There is no new classifier, threshold, or live bridge integration.

Next measurable step:

1. Recover the private reviewed splitter and exact-source frame qualification
   for Hand 1 DAIMINKAN and Hand 6 BUGANG. Check three role crops cover their
   respective visible bodies, including bounds/background/occlusion failures.
2. Run the frozen source-disjoint scorer separately on each reviewed crop;
   preserve role scores, source/frame lineage, independent-match support and
   classifier abstentions. Never reuse query pixels as templates.
3. Feed those scores into this decoder. Report individual winners, same-tile
   hypotheses, conflicts and UNKNOWN separately for each event and frame.
   These two events belong to the same original match and do not create two
   independent match groups.

No real-video identity accuracy is claimed by this implementation or its
synthetic score tests. Runtime identity remains UNKNOWN until separately
qualified; the existing strict identity bridge continues rejecting STACKED.
