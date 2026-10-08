# Public Meld SIFT Candidate V0.1

Date: 2026-10-01  
Issue: #69  
Scope: development-only exposed-meld identity experiment

## Why this candidate exists

The geometry path is already able to normalize and split reviewed regular
three-face exposed melds. The remaining failure is identity-domain robustness.

The earlier whole-face grayscale reuse remains rejected. A 12% query-side
center inset improved the two known P6/S4 development queries, but retrospective
private checks showed that crop normalization alone does not generalize enough
across old independent recordings.

## Development evidence used to select SIFT

No private pixels are committed by this note.

Private user-confirmed packet:
- 36 approved public-meld faces;
- 12 groups;
- two original matches;
- same original match but different clips/hands: legacy grayscale top-1 6/17,
  SIFT top-1 13/17;
- the only cross-match shared class in that old packet is S4:
  SIFT ranks were 4/33 in one direction and 1/3 in the reverse direction.

Public repository query-only packet, with the query match excluded and each
eligible class requiring support from at least two other original match groups:
- P6 -> P6, score ~= 0.04973953, margin ~= 0.04240094;
- S4 -> S4, score ~= 0.10338719, margin ~= 0.10077920;
- top-1 2/2.

These are candidate-selection results, not blind validation. The P6/S4 truth
was already known, and the private 36-face packet had already been reviewed.

## Frozen algorithm

- grayscale;
- 3x bicubic enlargement;
- CLAHE clip limit 2.0, grid 8x8;
- SIFT nfeatures=100;
- BFMatcher L2, KNN k=2;
- Lowe-style ratio 0.80;
- fallback to five best raw matches when no ratio-filtered match survives;
- class score uses the best template per independent match group;
- a class is ranked only with >=2 other match groups;
- conservative class score is the second-best independent-match-group score.

Any parameter change is a new candidate and cannot inherit future holdout
evidence from this frozen candidate.

## Runtime policy

This candidate is not wired into Runtime, Hint, or Executor. It defines no
production confidence threshold and is not formal Vision promotion evidence.

The next meaningful evidence must come from a newly observed independent
original match group that was not used to choose this candidate.
