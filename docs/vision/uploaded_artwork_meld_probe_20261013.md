# Uploaded artwork vs 15 redecoded meld faces — 2026-10-13

Issue #69 development-only experiment. The uploaded 900x720 labeled contact
sheet was visually inspected: 34 standard + 8 flower entries in client-ID
order. The 15-face redecoded candidate ZIP matches the SHA recorded in #69.
These are newly available private inputs; the original wxapkg export/map remains
separate. A contact-sheet-derived glyph is not an exact original package PNG.

## Rechecked input identity

- Sheet SHA-256: `95f1686be0f3c93eed446796fbb1ced234215224e5d9b090bc0c99d1f4a001b3`.
- Candidate ZIP SHA-256: `c92cd89091b51ed6a7dc78682612cf5401ca1a4228386459baacedf22d01484b`.
- Prior reviewed-label evidence SHA-256: `6cf0d63b66215f0833f822170e066123ff8c5286834030c74eab1d912295a744`.

All 15 PNG file hashes, decoded RGB hashes and sizes match the candidate
manifest. Labels, source SHA, decoded frame and bbox bind to the pinned existing
review evidence. Legacy PNG hashes are retained as distinct identities; the
candidate is not represented as reconstruction of the approved legacy bytes.
Original videos were not re-decoded here. Pixels and private paths are excluded
from GitHub.

The query comprises five previously reviewed groups from three video segments
of one named original match. Same-group and exact query-source real templates
are excluded according to the existing registry, leaving 58 reviewed concealed
training templates. Cross-registry match independence was not newly verified;
this is not source-disjoint promotion evidence. The crop geometry was already
reviewed; this is not an automatic detector-path test.

## Fixed experiment

The cell layout was fixed before query scoring: 9 columns, 100x140 cells, top
108 pixels only to exclude printed labels; only 34 standard cells enter ranking.
No individual class overrides or threshold changes. The six variants use
existing NCC features, existing SIFT descriptors/similarity, and the committed
10-variant self-meld renderer. Results were rerun after integrity/lineage checks
were strengthened and remained identical.

| Variant | Correct faces | Exact reviewed groups |
| --- | ---: | ---: |
| Real hand-template NCC transfer | 0/15 | 0/5 |
| Contact-sheet artwork NCC | 8/15 | 2/5 |
| Real hand-template SIFT transfer | 8/15 | 1/5 |
| Contact-sheet artwork SIFT | 7/15 | 1/5 |
| Artwork + existing self-meld renderer + SIFT | 7/15 | 2/5 |
| Real hand + rendered artwork SIFT fusion | 8/15 | 1/5 |

The glyph sheet helps the weak direct NCC transfer path, but direct artwork
fusion does not improve the stronger hand-SIFT face baseline on this batch.
The rendered variant has fewer correct faces but more exact groups, so neither
metric alone justifies selection. Do not wire any variant into Runtime on these
results. SIFT scores are not calibrated Runtime confidence; all reported
Runtime identities remain UNKNOWN. Identity threshold remains 0.82.

Machine-readable scores, every query row, environment and template hashes:
`references/vision/2026-10-13/uploaded_artwork_meld_probe_v0_1.json`.

## Reproduce privately

```powershell
python -B -m workspace.vision.atlas_artwork_meld_probe `
  --sheet <private-dir>/uploaded_tile_image.png `
  --sheet-sha256 95f1686be0f3c93eed446796fbb1ced234215224e5d9b090bc0c99d1f4a001b3 `
  --packet <private-dir>/redecoded_meld_candidates.zip `
  --dataset dataset/tiles_runtime_v0_2 `
  --lineage references/vision/2026-10-01/concealed_template_match_lineage.development.json `
  --repository-root . `
  --output <private-dir>/artwork_meld_probe.json
```

The report uses exclusive creation and contains no raw images or private paths.
Local image/intake/lineage suite: 35 tests, all passed using OpenCV 5.0.0,
NumPy 2.3.5 and Pillow 12.3.0 (the precise run environment is in the report).

The Drive root also exposes separate 10/9 and 10/13 folders. The latter contains
two files labeled as 10/12 recordings; they were inventoried only, not opened,
scored, used as support, or declared independent. Preserve their potential
holdout status until exact-source grouping and reviewed truth are established.

No Rules, Agent V0.10, Runtime, Hint or Executor behavior changes. The next
experiment should test region/domain normalization or a trained artwork-to-real
transfer candidate on development data, then freeze it before fresh evaluation.
