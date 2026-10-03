# FLAT identity consistency checkpoint

Date: 2026-10-03. Base: PR #117 `4189d1b`.

The strict public-meld identity bridge previously trusted any three independently
qualified face candidates, including P4/P5/P7 or mixed suits. Repeated confident
invalid identities could therefore establish a trusted observer baseline.

The bridge now checks the existing regular group decoder against **only the
three accepted identities**: a suited sequence in any displayed order or an
identical triplet. It never substitutes lower-ranked candidates to manufacture
a valid group. Invalid combinations retain individual diagnostic candidates but
block group trust. Snapshot assembly rechecks the combination, so inconsistent
precomputed results do not bypass this condition. CHI/PENG action kind remains
UNKNOWN; no Rules, AI, classification threshold, model, or Executor change.

Regression covers confident invalid suited/mixed/honor combinations, repeated
invalid observations, valid reversed sequences and honor triplets, and stale
precomputed bridge results. These are contract tests, not real identity accuracy.

The existing seven reviewed player-side FLAT groups were rerun through the
normalizer, splitter and strict identity bridge. All seven produced three crops;
all seven identity groups abstained. Producing crops does not prove their
boundaries are correct. This result neither raises identity accuracy nor qualifies
Runtime promotion; it confirms conservative behavior on existing inspected data.
See `references/vision/2026-10-03/issue69_flat_group_identity_gate_probe_v0_1.json`.

Reproduce with:

```bash
python -m workspace.vision.evaluate_flat_meld_identity_bridge --output /tmp/flat_bridge_probe.json
```

The runner verifies each locked query image SHA and registered video source
before scoring. In the tracked public Shadow bank, 15/21 face observations
abstain for insufficient cross-match class support and 6/21 for low score or
ambiguity. None of the seven expected groups has all expected classes supported
by two non-query original matches in that bank. This is the public Shadow path,
not the separately supplemented private SIFT bank; do not mix their coverage or
failure counts. Reviewed expected labels are used only for evaluation/support
diagnostics and never supplied to the classifier.

Attribution correction: even the six low-score/ambiguity observations have
unsupported expected classes in this Shadow bank. Their reason codes describe
the backend's abstention, not proof that the correct class had enough reference
support and still failed. Do not call them six isolated classifier failures.

Next measurement: separate each real face's source-disjoint class-support gap
from low-score/ambiguity failures. Prioritize ordinary FLAT templates/crop review,
with original-match lineage retained, rather than waiting for additional KONG
events. The existing strict gates and UNKNOWN outputs remain in force.
