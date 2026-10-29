# Private development candidate: desktop restoration

Execution truth remains Issues #69/#45/#7. This is an experiment handoff,
not Runtime promotion or installed recognition readiness.

Keep private files outside the checkout, for example
`D:\huianmahjong\private_materials\`. The private package is
`huian_hand1_candidate19m8_private_checkpoint_20261016.zip`.
It holds 19 old-source support PNGs, their metadata and private evaluation
reports. It does not contain the baseline bank or production integration.
Download it from the user's ChatGPT files or copy it through the user's Drive;
ChatGPT account login does not synchronize arbitrary desktop directories.

From this branch's checkout with the normal Vision dependencies installed:

```powershell
python -m workspace.vision.tiles_runtime_v0_2.restore_private_candidate `
  "D:\huianmahjong\private_materials\huian_hand1_candidate19m8_private_checkpoint_20261016.zip" `
  --baseline dataset/tiles_runtime_v0_2 `
  --output "D:\huianmahjong\private_materials\candidate19m8"
```

The output must not already exist and cannot overlap the baseline directory.
The tool checks paths, metadata and all crop SHA256 values before writing;
it rejects overwrite, traversal, collisions and corrupted templates. It creates
a separate bank, retains the baseline's reviewed-addition sidecars, and reports
baseline/support/final label counts. At the audited baseline these are
147 + 19 = 166. Different baseline counts require investigation, not silent
reinterpretation of the old experiment. The package SHA is recorded but must
still be checked against the trusted transferred file; self-contained asset
hashes are integrity checks, not independent proof of provenance.
The historical ten rows have no embedded `original_match_group`. Restoration
preserves this absence and reports it (ten missing rows in this package), rather
than inventing lineage from `source_session`. Reviewed match accounting still
requires the separate exact-source lineage evidence.

## Offline recognition contract

This command only restores the bank. It does not launch live capture or select
a candidate in the app. The experiment combines:

1. standalone `development_cluster_geometry.py`, including upper-rim seam
   selection and nominal-boundary tie resolution;
2. the separately restored bank;
3. primary Runtime classification followed only for UNKNOWN by tight-box
   classification with the same 0.82 confidence/source-support gates.

Use the existing whole-hand exporter/fallback evaluator for frozen production
geometry. To evaluate the standalone geometry, use a separate offline harness;
do not globally patch the live reader or treat repeated copies of one frame as
independent stable-frame votes. Production detector/reader/dataset are unchanged.
No PNG, video, private archive or signed URL is included in this commit.

## Revealed first-hand development results

The same inspected match was repeatedly used during optimization; none of the
following is a new source-disjoint holdout or a live Windows acceptance result.
All support additions remain one Sep-26 original match, not multiple matches.

| Fixed centre ordinal | Before nominal tie fix | After tie fix | Wrong accepts after fix |
| --- | --- | --- | --- |
| 569 | 16/17 | 17/17 | 0 |
| 1423 | 16/16 | 16/16 | 0 |
| 2277 | historical 13/13 | NOT RERUN | unknown this round |

Gold M4 remains UNKNOWN: ordinary crops do not qualify real yellow M4 evidence,
and a tight Gold crop performs worse. Complete concealed identities do not
authorize shanten while opened Gold and other structural inputs are untrusted.

The local query video copy became truncated (27,086,336 bytes rather than
43,316,119) and decoding failed before the third checkpoint. Restore the exact
original source and verify its pinned hash before a complete rerun; do not
substitute approximate frames. This does not establish damage to the user's
original recording. Private original-source identity is retained in the saved
checkpoint, not inferred from filenames.

Frozen: threshold 0.82, Agent V0.10, Hint read-only, Executor OFF, Draft PR126
unmerged. Local tests and CI are engineering checks, not recognition promotion.
