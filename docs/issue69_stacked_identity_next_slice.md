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

## Reviewed-crop pipeline checkpoint, 2026-10-03

`score_reviewed_stacked_faces` now connects separately reviewed readable crops
to the frozen SIFT scorer and this decoder. It excludes unreviewed/unreadable
faces before classification. Optional class-score export preserves the scorer's
default output and ranking, as checked on the existing locked P6 query.

The [development probe](../references/vision/2026-10-03/issue69_stacked_reviewed_sift_pipeline_probe_v0_1.json)
uses newly reconstructed manual crops, not the unavailable original frozen
splitter. It is not a repeat of the historical 7/9 experiment. The tracked public
bank, without private template supplementation, qualifies only P6 and S4 for
these queries. Source aliases for the same original match were canonicalized
before exclusion; the two events still count as one original match.

- Hand 1 clip: 3 frames / 9 readable face observations rank P6; 3/3 frames agree.
- Hand 6 original: visible outlined faces match the approved B/white-dragon
  visual style on direct review, while prior owner-confirmed identity is still
  UNKNOWN. B has no eligible public class support. The scorer consequently
  ranks P6/S4; frame 3354 unanimously ranks P6. Agreement does not establish
  correct identity, even with three distinct visible crops.

These observations certify neither automatic cutting nor 34-class accuracy.
Next: recover/version the original splitter and its crop qualification records,
and obtain reviewed B public-meld references from other original matches before
using Hand 6 to measure classifier correctness. Do not tune the scorer against
this event or turn a missing expected class into an accepted wrong identity.

## Expanded-bank and rectification checkpoint, 2026-10-03

The original pinned private supplement was restored through the existing
source/frame/crop-integrity loader: 15 templates, five recovered groups. Under
the same query-original-match exclusion and >=2-other-match rule, the eligible
bank is M4/M5/M6/P6/P7/P8/S4. B remains unsupported.

With the previous manual crops held fixed, Hand 1 is **6/9** face Top1 correct,
not the narrow two-class bank's 9/9; only frame 258 has three unanimous P6
winners. This is not a reproduction of the old 7/9 experiment. Expanded
competitors reveal P6/P7 confusion and qualify the earlier optimistic result.

One new geometry-only reviewed-quadrilateral rectification was tested without
score-driven parameter search. Hand 1 declined to **3/9**, with no unanimous
frames. The transform is **not adopted** by the scorer/pipeline; its helper
remains an isolated offline experiment. The new manual corners are not automatic
splitter validation, and top-face boundary/neighbor intrusion remains a review
limitation. Do not treat this experiment as evidence that automatic perspective
normalization in general is ineffective.

The pipeline now explicitly reports unscored standard classes alongside its
candidate rankings and retains group identity UNKNOWN even for unanimous
winners. Missing B support cannot be repaired by choosing the highest-scoring
available class. See the expanded-bank probe under `references/vision/2026-10-03`.
