# Issue #69 — Public-region identity shadow V0.2 (development only)

**Status:** Separate, read-only public-template *proposal* probe. Not a runtime
classifier, a verified real-action recognizer, or formal Vision promotion.

## Existing facts and source groups

The current approved public-region manifest contains **17 reviewed faces
across 11 of 34 standard tile classes**: four enlarged public_action, one
small public_single, and 12 public_meld faces. They come from two already
inspected recordings. **No tile class appears in both recordings.** The
source-group manifest is public_identity_source_groups.development.json.
It requires explicit match groups and exact source SHA256. Existing
hand/draw/Gold classifier templates are not imported or modified.

Separate open PR #104 introduces a registry for three different clips, with
the first two belonging to the **same original match**. Different SHA256
or hand index does NOT imply a distinct match. Group by original match
and reconcile the registries after PR #104 is reviewed.

## Conservative development classifier

workspace/vision/public_identity_shadow_v0_2.py:

1. Verifies screenshot SHA256, approved-label status, exact source SHA,
   explicit match group and public-region identity before cropping.
2. Builds independent public-region grayscale templates, without entering
   the existing Runtime Vision hand/draw/Gold pool.
3. Excludes **every clip from the query's original match group**, not just
   the query frame or video. A candidate class requires approved examples
   from **at least two other original matches** in that same region.
   Two independently supported **competing** classes must be available.
4. Requires visual agreement, a minimum match score and a margin against
   the next eligible class. Blank/untextured and ambiguous crops abstain.
5. **Always returns runtime tile_id=UNKNOWN.** When gates pass, it may
   return only a development-only shadow_proposal—never a confirmed
   DISCARD, MELD_DELTA, CHI/PENG/KONG or Executor instruction.

This is deliberately more conservative than nearest-template matching:
the same frame, adjacent crops and repeated P1 faces from one Peng are
not independent evidence. Scores are uncalibrated grayscale correlations,
NOT recognition probabilities.

## Reproducible development benchmark

From the repository root, with Vision extras installed:

    python -m workspace.vision.public_identity_shadow_v0_2 \
      --manifest references/vision/2026-09-22/public_identity_labels_v0_1.json \
      --registry references/vision/2026-09-24/public_identity_source_groups.development.json

With complete original-match holdout, the existing 17 labels are insufficient
for **any** proposed class: eligible queries 0, abstentions 17, proposals 0.
Proposal accuracy is undefined. This is a data-coverage blocker, not a
measured recognition accuracy. Synthetic tests prove that a supported
query can produce only a quarantined shadow proposal, and that same-match,
wrong-region, wrong-SHA, screenshot mutation and blank-face cases abstain
or fail closed.

## Next gate

Independently adjudicate private hand-1/hand-2 crops and PR #104's three
new cross-match crop proposals; do not auto-approve any machine guess or
use frozen action truth as training labels. Collect independently approved
examples of the SAME tile class from DIFFERENT original matches, plus
confusing negatives and independently reviewed public_meld faces. Then
freeze a separate match-disjoint public identity evaluation and an
independent public turn-cue benchmark. Action reconstruction and the
8-hand match ledger remain read-only/UNKNOWN when evidence is missing.
Executor OFF. Keep private videos/crops outside the public repository.
