# Private client-artwork whole-hand A/B

Issue #69 development experiment, using the artwork recovered in Draft PR #138
and the current PR #126 classifier code. This CLI does not alter Runtime, labels,
the 0.82 threshold, Rules, V0.10, Hint or Executor. It does not establish formal
Vision promotion or real Windows latency.

## Inputs on the private-source machine

- Current Runtime dataset, with its approved labels, additions and actual crops.
- The existing private `tile_encoding_map.json`: 34 standard + 8 flower assets,
  client/project IDs, derived PNG/atlas/metadata paths and their hashes. The
  imported intake verifier checks this packet; flowers are excluded from the
  standard concealed classifier experiment.
- The reviewed exact-source-SHA original-match registry and its evidence files.
- A private whole-hand baseline export with its `crops/<sample_id>/...` files.
- A separate manual review lock binding the export SHA, source SHA, original
  match and complete selected sample truth. Old exports with unreviewed or
  superseded labels must be re-reviewed/corrected before creating the lock.

Do not automatically set `reviewed=true`. After inspecting the actual exported
crops against the original source, the lock has this shape:

```json
{
  "schema_version": "client_artwork_ab_review_lock_v0_1",
  "development_only": true,
  "reviewed": true,
  "reviewer": "manual-reviewer",
  "baseline_export_sha256": "<actual export SHA-256>",
  "source_sha256": "<actual source SHA-256>",
  "original_match_group": "<reviewed original-match group>",
  "samples": [
    {"sample_id": "<existing sample ID>", "truth_tiles": ["<every tile in slot order>"]}
  ]
}
```

The tool verifies that locked slot truth covers all concealed and separate draw
tiles, that hand/draw slots are unique, and that crop paths stay in their sample
directory. Gold-skinned hands are out of scope for this ordinary-artwork slice;
do not silently reinterpret them as ordinary samples. Only explicitly reviewed
selected samples are evaluated.

```powershell
python -B -m workspace.vision.client_artwork_ab `
  --dataset dataset/tiles_runtime_v0_2 `
  --package-map <private-dir>/tile_encoding_map.json `
  --lineage references/vision/2026-10-01/concealed_template_match_lineage.development.json `
  --baseline-export <private-dir>/baseline_export.json `
  --review-lock <private-dir>/review_lock.json `
  --repository-root . `
  --output <private-dir>/client_artwork_whole_hand_ab.json
```

Output creation is exclusive; previous reports cannot be overwritten. The tool
uses the existing Vision dependencies. Raw package pixels, image/video paths
and crops are not written into the report or published by this command.

## Comparison and acceptance semantics

Both classifiers see the identical current query crops and the same qualified
real training bank. All known query-original-match templates and unknown-lineage
training sources are excluded. The registry's review evidence paths must exist
inside the specified repository. The report distinguishes exact registry query
lineage from a private review-lock-only claim; neither is a fresh holdout claim.

Three results are reported:
1. Baseline real templates, using the existing feature/NCC implementation.
2. Isolated real + client-artwork templates, using that same implementation.
3. Primary-first result: retain every baseline accepted identity; consult the
   merged candidate only for baseline UNKNOWN.

Artwork contributes no real class coverage and no original-match count.
Diagnostic acceptance uses the existing 0.82/category identity gate plus at
least two **other original matches** for the proposed class. This is explicitly
stricter than the packaged Runtime's historical stored-session diagnostic;
its accepted counts must not be substituted for that older measurement.

For each variant, report raw correct tiles, accepted correct, wrong accepted,
rejections/reasons, exact raw whole hands, exact accepted whole hands and fully
accepted wrong hands. Also retain paired raw improvements/regressions and every
tile result. Exact classification does not establish special-Hu eligibility,
strategic advice quality, actual guarded live acceptance or latency.

## Current verification

Local contract/intake/lineage suite: 33 tests, 32 pass and one image test skips
because this Linux environment lacks OpenCV. Vision CI explicitly installs the
dependencies and runs the image test, including full private-packet validation,
the real classifier and proof that 42 artwork assets cannot open missing real
support gates. This synthetic test is tool verification, not recognition data.

The private 42-class artwork packet was not available in this GitHub checkout,
recent Library uploads or the connected Drive search. No new real A/B accuracy
is reported in this implementation. Existing 93/137 -> 99/137 and 43/43 remain
their original development results; this tool does not refresh either number.
