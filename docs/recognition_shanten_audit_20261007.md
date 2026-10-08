# Current hand / meld / shanten audit — 2026-10-07

User's near-term objective: stable current-hand and exposed-meld observations,
then ordinary structural shanten and minimum-shanten discard suggestions.
Execution truth remains Issues #69/#45/#7. Audited draft base: PR #126
`2fafd7efb8fb08dc5b5c26290ad5f3d9999a87d1`; all five workflows passed.
PR #126 and #117 remain Draft/unmerged. This is not a main release.

## Findings

| Boundary | Verified current behavior | Remaining limit |
| --- | --- | --- |
| Capture / installed UI | Windows build extracts and hashes payload, checks spawn/Tk and starts LiveHintAlphaApp | Actual mirrored game, latency and disconnect recovery are not validated by the synthetic installer smoke |
| Concealed identity | Reviewed bank covers 34 standard classes; only 22 have at least two stored concealed source sessions | Twelve classes lack that support; any rejected tile blocks the complete hand. Stored sessions alone do not prove independent original matches |
| Gold | Dedicated multiframe gate and capture-scoped persistence; trusted hand boundary is independent of display OCR | Eleven classes lack two stored Gold-domain source sessions. Physical opening is not inferred |
| Hand stability | Runtime freezes geometry counts across 3–5 frames but classifies the selected hand frame | Geometry stability alone does not prove hand identity stability |
| Own meld count | Dynamic components are grouped; count-only incomplete groups require concealed-count corroboration | An unexplained extra fragment could previously be silently dropped while the retained count remained trusted |
| Meld identity | Strict public identity adapter/normalized FLAT and STACKED experiments exist | Runtime reader does not emit a qualified public_identity_result for meld components. SIFT/MobileNet offline success is not live full-meld accuracy |
| Shanten | Rules-independent structural calculator consumes complete hand + trusted Gold + own meld count | Public identity UNKNOWN permits structural shanten only; remaining-copy/danger and special-Hu eligibility remain separate |
| Reporting | Frozen private-source replay can reproduce saved accepted/blocked snapshots | The recorded 8/13 accepted windows are same-source development smoke, not full-hand accuracy or Windows live acceptance |

Full-bank missing two-session support at this audit:

- Concealed: B, G, M2, M4, M7, M8, M9, N, P2, S9, SOUTH, W.
- Gold: B, G, M2, M4, M7, M8, M9, P2, S9, SOUTH, W.

Reproduce the inventory with `prepare_runtime_resources()` and compare
`covered_by_region[domain]` against `cross_session[domain]`. Query-session
exclusion can remove additional coverage. These are collection priorities,
not permission to lower the 0.82 threshold or admit unreviewed templates.

## Implemented audit fixes

1. Live-only `LiveSnapshotStability` requires two matching current observations
   from **distinct actual classified frames**, with increasing capture times,
   in the same session/epoch and within a two-second gap. Hand multiset, Gold
   and observed own meld groups must agree. Sorting or merging draw_visual into
   hand does not manufacture a hand change. Overlapping burst IDs do not count
   the same selected identity frame twice.
2. A changed/UNKNOWN/conflicted/physically impossible hand immediately blocks
   advice; no prior hand is substituted. Capture/confirmed-hand resets forget
   the confirmation streak. This adds at least one live read interval before
   initial or changed-hand advice; actual added latency needs measurement.
3. The live entry point enables this guard. The frozen Runtime reader,
   classifier scores/thresholds and stateless replay boundary remain unchanged.
   A stateless replay's accepted-window count must not be reported as acceptance
   of this guarded live path.
4. Unexplained meld fragments make the observed meld count untrusted. Rejected
   hand component identity cannot be overridden by a report-level trust flag.
   Nonfinite public identity scores/margins are rejected. Malformed/illegal
   known meld structures or Gold in an exposed meld block advisory calculations;
   legitimate three/four-slot UNKNOWN meld identities remain UNKNOWN.
5. The UI distinguishes unknown meld identity from its trusted group count,
   displaying known group faces only when present. Advisory evidence now records
   hand/meld trust, meld values, Gold provenance, source frames, capture time,
   Runtime inference elapsed time and per-region identity rejection reasons.

No CurrentAgent V0.10 changes, hidden-rule guesses, dark-face fallback,
threshold relaxation, Vision promotion or Executor activation.

### Worker-error recovery follow-up

An accepted live Runtime worker error now interrupts the hand/meld confirmation
streak. Recovery requires two new valid distinct identity frames, even when the
first recovered hand matches the hand shown before the error. Previously the UI
blocked on error but retained confirmation votes, allowing immediate restoration
after one recovered observation. Confirmed Gold and Gold conflicts remain scoped
to the hand and are not cleared by a classifier error. Wrong-session,
wrong-generation and expired worker errors are ignored before interruption;
stateless replay and other live pipeline contexts remain unaffected.

## Next executable order

1. **Whole current-hand reliability:** source-qualified Windows sessions with
   reviewed frame truth; include no meld, one/multiple melds, separate draw,
   hand sorting, yellow Gold skin, prompts/shadows and resolution changes.
   First recover and source-group existing reviewed material for the twelve
   concealed support gaps; collect additional independent original matches only
   for gaps that remain after recovery. Score the frozen current bank first; review/intake belongs
   to a separate development set, never the untouched promotion holdout.
2. **Own meld count before full identity:** evaluate actual detector boxes and
   group boundaries, including FLAT, STACKED, add-kong and residual fragments.
   Count-only successes must be reported separately from exact face successes.
3. **Qualified live public identity input:** verify the existing normalization,
   segmentation and source-disjoint public bank can be used on actual Runtime
   detector output. Preserve missing-class/occluded-face UNKNOWN. Do not connect
   an offline experimental winner as a Runtime accepted identity.
4. **End-to-end live acceptance:** run the installed guarded UI on a real mirror;
   verify acquisition, changed-hand suppression, recovery and confirmed new-hand
   reset. Read-only structural shanten is the immediate output. Complete rivers,
   danger, action ledger, special-rule migration and new Agent experiments do not
   become prerequisites for this scoped acceptance.

For each reviewed session report: exact tile accuracy, exact **whole hand**
accuracy, displayed/blocked windows, wrong accepted hands, own meld-count
accuracy, exact meld-face accuracy, source/epoch conflicts, Runtime and total
capture-to-advice p50/p95 time, and acquisition/recovery times. Do not quote
accepted-only tile accuracy without its rejection fraction or substitute
geometry/test pass rates for identity accuracy. No new numeric promotion gates
are introduced here; Issue #7's frozen independent gate remains authoritative.

Private full frames/video remain outside GitHub. Green CI proves regression
contracts, not the requested real-world recognition reliability.

## Existing-sample recovery audit

The 2026-10-07 inventory verifies 145 approved labels and 145 unique existing
template files. The real `prepare_runtime_resources()` loader consumes all 145
labels: 144 ordinary templates and 145 Gold-normalized identity templates. One
Gold-skin-only crop is deliberately excluded from the ordinary bank. The old
manifest count of 142 was stale metadata, not a runtime loading cap.

All 121 supplied `asset_sha256` values match crop bytes. The remaining 24 legacy
rows do not supply that field; their `sha256` identifies the original source,
not the crop, and must not be interpreted as a failed crop hash. Twelve stored
source sessions do not by themselves establish twelve independent matches.

The existing private 36-face confirmed packet contains public meld faces
(12 groups from two original matches), so it cannot silently fill concealed-hand
support gaps. Historical V0.1 full labels/ROIs are local-only and absent from
this checkout; their migration completeness remains unverified. This does not
prove those assets were lost. Recover available reviewed local assets with
`legacy_reviewed_recovery.py` and preserve original-match provenance before
requesting new recordings. No private packet or raw frame was added to GitHub.

`dataset/tiles_runtime_v0_2/runtime_asset_inventory_20261007.json` supersedes
historical inventory counts only. Historical accuracy reports remain historical;
this audit does not refresh their measurements or relax any confidence gate.

## Batch recovery for the current gaps

The scan-only `legacy_reviewed_batch` command selects support gaps from current
approved concealed labels (hand plus draw, excluding Gold-only skins). It writes
one contact sheet/plan per target and a batch plan under the ignored Runtime
work tree. Runtime labels/templates are untouched. Gold-region candidates are
counted separately from usable concealed candidates. A missing local dataset is
reported as `LEGACY_LABELS_UNAVAILABLE`, not as zero available old samples.

Run from the repository root on the machine holding the old reviewed dataset:

```powershell
python -m workspace.vision.tiles_runtime_v0_2.legacy_reviewed_batch --legacy-dataset dataset/tiles_v0_1
```

Use `--legacy-dataset` with the actual archived dataset directory if different.
The current targets are the twelve concealed classes listed above. Reapproval
and an explicitly reviewed original-match grouping are still required before
admission; finding crops does not automatically resolve independent support.

The exact-SHA recovery queue now isolates four unresolved sources affecting six
existing labels: W, M9, SOUTH and S9. Other gap classes have reviewed source
lineage but still lack the required stored-session support. This queue resolves
provenance questions, not missing second-match samples. It supplements the
historical, already-resolved M1/M3 queue without changing that frozen artifact.

```powershell
python -m workspace.vision.concealed_template_local_sha_scan D:\huianmahjong\HuianMahjong_Codex_Handoff --queue references/vision/2026-10-07/concealed_support_gap_lineage_recovery_queue_v0_1.json --output dataset/tiles_runtime_v0_2/work/local_gap_sha_scan.json
```

The scan output contains private local paths and must remain local. If an output
parent is absent, create it first. Exact SHA matches require source review and
never automatically assign original matches. Repository-wide search found the
four SHA values in historical Phase5B selection records, but those records do
not identify independent original matches, so no lineage mapping was invented.

## Private exposed-meld packet restoration

The existing `huian_36_user_confirmed_private_v01.zip` has now been restored into
the private working environment. All 36 PNG bytes match their reviewed crop
hashes, and its approved-label manifest matches the hash pinned by the current
recovery result V0.3. This is current byte-integrity verification; original
video frames were not rehashed/re-extracted in this audit.

The repository already held recovered evidence for five groups, not zero:
G02, G03, G07, G08 and G09 (15 faces). The actual existing private SIFT loader
successfully loaded those 15 faces. The public development bank contributes
21 other templates; the combined bank has 36 templates. This combined total
must not be confused with admission of all 36 faces from the private packet.

| Packet portion | Faces | Current status |
| --- | ---: | --- |
| G02/G03/G07/G08/G09 | 15 | Existing recovery evidence verified and loaded into development SIFT |
| G04 | 3 | Source SHA mismatch remains blocked |
| G01/G05/G06/G10/G11/G12 | 18 | Packet pixels restored; no current per-group recovery result |

No new template was admitted, and no private pixels or filenames identifying
original videos were committed. This development bank is separate from real
Runtime/Hint meld identity. Source disjointness, missing classes and blocked
sources retain their existing gates. The metadata-only inventory is
`references/vision/2026-10-07/private_public_meld_recovery_inventory_v0_1.json`.
