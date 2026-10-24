# Current hand / meld / shanten audit — 2026-10-07

## 2026-10-24: sampled truth and blocker attribution

Replayed both exact private sources on parent `1fdc7aa` with the unchanged
classifier, templates and 0.82 threshold. Automatic advice remains **0/517**.
Added an offline snapshot-intervention runner; it is not imported by Runtime,
Hint UI, or Executor. `replay_smoke` only adds an explicit geometry trust flag.

Reviewed every sampled image used in the comparison, including whole-hand
composition before the P6 kong, the M3 replacement draw, and after M3 discard.
Truth pins sequential frame ordinals and RGB hashes. Labels are assistant-reviewed
revealed development annotations, not player-confirmed or independent holdout truth.

| Same reviewed windows | Machine | Correct Gold only | Correct hand only | Correct Gold + hand |
| --- | ---: | ---: | ---: | ---: |
| Short clip, 37 stable windows | 0 | 3 | 0 | 37 |
| Longer clip, 2 reviewed bursts | 0 | 0 | 0 | 2 |

Counts mean **snapshot shanten calculation allowed under manual substitution**,
not automatically correct/accepted hands. Geometry, source scope, own meld output,
and physical checks are retained. This is stateless attribution and does not
prove multiframe live confirmation, change recovery, or correctness on unsampled
frames. Public river and exact meld identities remain incomplete. Calculator
outputs are not independent validation of shanten or special Hu rules.

The short comparison covers frames 0..180, 198..228, and 240..270 at stride 6.
Seven windows touching unannotated moving tiles (186/192/234) are excluded.
All 37 eligible complete raw candidate hands match sampled truth, while 34 are
rejected. Repeated rejection decisions: S2 35, M6 15, M3 2, all below threshold.
These are overlapping observations, not unique errors or independent matches.

The longer comparison contains only bursts 1800/1806/1812 and
2706/2712/2718. Both have a true S6 represented by raw S4 and true G by raw S8.
The two P2 candidates in each burst are correct and above 0.82 but rejected by
`class_not_cross_session_validated_in_region`. Thus there are **three distinct
failure types**: correct ranking with low scores, wrong ranking, and insufficient
source support. The other 471 windows have no complete sampled truth; these two
bursts do not establish a whole-video error rate. Its original match remains UNKNOWN.
The 600/606/612 anchor contains a moving S6 discard and is not labeled as a
constant complete-hand burst.

### Execution priorities from this attribution

1. Freeze these source/hash-bound development comparisons. Gold alone recovers
   only 3/39 reviewed windows, so hand work must proceed alongside Gold.
2. Restore qualified P2 support and its original-match lineage; a confidence or
   model change cannot replace missing provenance.
3. Evaluate Gold appearance and concealed S6/G confusions on the identical crops
   with source-separated classifier training. S2/M6/M3 score calibration is a
   separate question; do not lower 0.82 or treat neural logits as Runtime confidence.
4. Compare complete correct trusted hands and wrong accepts on a separate match
   before Runtime wiring. These revealed windows are development regression only.
5. After identity improves, rerun sequential stateful change/recovery checks.
   The current intervention does not clear live release or Executor gates.

Reproduce (first generate fresh replay with the existing source-locked command):

```sh
python -m workspace.hint_alpha.replay_blocker_attribution \
  --replay /private/short_baseline.json \
  --truth references/vision/2026-10-24/short_clip_reviewed_sample_truth_v0_1.json \
  --output /private/short_attribution.json
```

Use the corresponding `long_clip_reviewed_sample_truth_v0_1.json` for the
94.9-second source. The runner rejects mismatched source/RGB hashes, missing
geometry flags, stateful replays and source-session conflicts; it excludes
incomplete truth or a changed hand within a burst. Machine adapter messages are
retained separately from current gate issues, so intervention results do not
present old rejection logs as still-active gates.

Exact results and exclusions are under `blocker_attribution_20261024` in the
[existing evidence record](../references/vision/2026-10-19/continuous_replay_failure_baseline_v0_1.json).
Private video, full-frame pixels and complete replay traces are not committed.


## 2026-10-19: measured continuous-replay failure baseline

This section supersedes older progress claims for the two exact uploaded clips
below. It records a reproduced failure, not a recognition improvement. Runtime,
classifier, templates and threshold 0.82 were unchanged. The measured reader/data
snapshot is PR #126 head `f20bfb3dd654c0267173911e2d1c4f9f71d0258f`.

Two existing uploaded videos were decoded sequentially in full, at 1108x512 and
30 fps. Every sixth frame formed overlapping three-frame bursts (0.2-second
sampling; 0.4-second burst span). The same Runtime report was evaluated both
statelessly and with `RuntimeAdvicePipeline` plus `LiveSnapshotStability`.

| Exact source | Duration | Windows | Geometry stable | All concealed IDs trusted | Stateless / stateful advice |
| --- | ---: | ---: | ---: | ---: | ---: |
| `f39bb98a…` | 9.1 s | 44 | 37 | 3 | 0 / 0 |
| `de1d21b2…` | 94.9 s | 473 | 241 | 0 | 0 / 0 |

All 517 windows were blocked by unknown/untrusted opened Gold. On stable geometry
windows, every per-frame Gold observation was below 0.82: scores ranged from
0.350–0.379 in the short clip and 0.338–0.368 in the longer one. In the longer
clip, concealed candidates P2 and M8 also encountered stored-session support
gates. Decision counts repeat tiles across overlapping windows; they are not
unique-tile counts or measured error rates. Geometric rejection has not been
reviewed against continuous animation truth and must not be called detector
error/recall. Adding state memory alone did not resolve these two failures.

A directly reviewed short-clip frame 120 (4.0 s) contains sixteen concealed
tiles and opened Gold M6. All sixteen raw candidates agree with that frame,
but M6 at 0.817985 and one S2 at 0.812364 remain rejected. Opened Gold's M6
candidate scores only 0.368945. The manually specified hand yields structural
shanten 0; that calculator reference is not automatic advice acceptance.
This is one revealed, assistant-reviewed frame, not a full-video accuracy set.

The short clip hash matches the existing 2026-10-01 mobile-clip record and belongs
to the already reviewed Sep-26 first-hand development match. Its zero-advice
Gold/S2 blocker was already recorded on 2026-10-06. It is not the 184-second,
2796x1290 `fba5…` original that shares its filename: original timestamps/truth
must not be reused on this derivative. The longer clip's original match group
remains UNKNOWN. Neither is claimed as a new independent holdout.

Metadata, exact hashes, frame/threshold definitions and per-source rejection
counts: [failure baseline](../references/vision/2026-10-19/continuous_replay_failure_baseline_v0_1.json).
Raw videos, frames and complete diagnostic traces remain private; no pixels
were added to the repository. Linux reader p50/p95 timings in the metadata are
not Windows capture-to-advice latency.

### Reproduce and inspect

Run from the pinned development checkout with Vision dependencies. Use the exact
private input bytes matching the chosen metadata entry:

```sh
python -m workspace.hint_alpha.replay_smoke \
  --video /private/source.mp4 --source-sha256 EXACT_SOURCE_SHA256 \
  --start 0 --duration EXACT_SOURCE_DURATION --stride 6 \
  --output /private/stateless.json --require-accepted
```

Zero accepted windows intentionally fails `--require-accepted` after retaining
the report. Reports now preserve `identity_observations` (raw components and
per-frame Gold decisions), so wrong candidates and correct-but-rejected
candidates can be distinguished. Add `--stateful-advice` to reproduce the
existing Gold-memory/distinct-frame confirmation boundary on **one hand**.
That optional mode has no automatic hand-boundary reset and is not a live
capture acceptance mode; default replay remains stateless. Neither mode enables
Hint or Executor. The short clip's updated CLI was checked against the original
stateless decisions, while the longer comparison used the same reader and
pipeline functions through a source-locked sequential evaluation harness.

### Opened-Gold crop/appearance countercheck (2026-10-19)

Six directly reviewed revealed-development anchors use sequential ordinals
60/120/180 from `f39bb98a…` (M6) and 612/1812/2718 from `de1d21b2…` (M4).
Exact RGB hashes are recorded in the baseline metadata. The visible tile face
is contained in both the detector box `[110,48,36,48]` and the expanded
classification box `[107,41,42,57]`; there is no obvious truncation on these
six anchors. This does not establish geometry correctness across either video.

Reused the five fixed `opened_gold_normalization_ab.NORMALIZATION_MODES` on
both crop types, using symmetric query/reference features and all approved
readable current labels after exact-query-SHA exclusion. Original-match
disjointness is not established, especially for the UNKNOWN-group M4 clip.

| Candidate | M6 + M4 anchor Top-1 matches | Interpretation |
| --- | ---: | --- |
| Expanded crop, current gray feature | 4/6 | Current low-score ranking |
| Expanded crop, face-only gray | 6/6 | Top score only 0.313–0.345; no calibrated acceptance |
| Expanded crop, inner-8% gray | 4/6 | Top score only 0.395–0.430 |
| Tight detector crop, current gray | 0/6 | Directly tightening the crop regresses all six |
| Existing query-size projection | 3/6 | M6 correct; M4 becomes M1 |
| Existing role-invariant feature | 3/6 | M6 correct; M4 becomes M1 |
| Experimental Wan upper-half feature | 6/6 | Local ranking success; no generalization or calibration claim |

The last experiment tests a specific explanation: the common lower Wan glyph
can dominate its distinguishing numeral. It retains the existing full-face
coarse-family choice, then, for family M only, ranks class maxima using
`_full_face_score(query_maps[:, :48, :], reference_maps[:, :48, :])` from the
existing 64x96 `_appearance_maps`; the default max shift remains 4. No sweep or
per-identity constants were selected. This new score is not Runtime confidence.

Counterchecked that fixed feature on the existing deterministic ordinary-tile
leave-one-original-match-out representatives, excluding unreviewed lineage and
the whole query match. Both the original role-invariant feature and the new
candidate score **7/16 scorable queries**, with zero gains and zero regressions.
Another 20 of 36 representatives lack a disjoint true-class reference. These
ordinary-tile queries cannot establish opened-Gold generalization; in particular,
the six-anchor result does not supply missing cross-match M4/M6 coverage.

Decision: none of these experiments qualifies a Runtime change. Simple crop
tightening is contradicted by this countercheck. Further identity-model work
needs source-qualified opened-indicator coverage, calibrated scores, and a
separate whole-hand evaluation. The 517-window zero-advice baseline is unchanged.
Raw pixels and private harness outputs remain outside the repository.

### Learned classifier and recovered Gold development material (2026-10-19)

Current approved bank coverage was reproduced: 147 projected references across
34 classes, but only two direct `gold_region` classes (N/S3) and one real
yellow-skin class (M6). Ordinary class coverage is not opened-Gold coverage.
Only 10 projected classes have two reviewed original-match groups; the legacy
session-based count is 23. No labels or Runtime coverage policy changed.

Ran fixed learned HOG + LinearSVC/RBF-SVC candidates on the same six revealed
Gold anchors. HOG uses the unchanged Gold-gray feature, unsigned 9-bin cells,
16x16 blocks with 8x8 stride/cells, block L2-Hys and vector L2. Both models use
C=1, balanced classes; RBF gamma is `scale`. Nine deterministic crop-preserving
appearance variants cover brightness, bottom shadow, yellow tone, blur and
downsample/upscale. The initial attempt to reuse MobileNet's square canvas was
discarded as incompatible with this HOG input; the reported run keeps actual
crop geometry. No hyperparameter sweep or probability calibration was performed.

| Training scope | Linear Gold anchor Top-1 | RBF Gold anchor Top-1 |
| --- | ---: | ---: |
| Reviewed lineage only: 65 ordinary labels / 585 augmented rows / 29 classes | 3/6 | 0/6 |
| Permissive development: 144 ordinary labels / 1296 augmented rows / 34 classes | 6/6 | 3/6 |

The known Sep-26 query match is excluded in both scopes; unresolved sources enter
only the permissive scope. Oct-12's query match remains UNKNOWN, so even the
reviewed-training-only result is not an independent evaluation for that clip.
Both models classify all their unaugmented training crops correctly as a fit
sanity check. In the separate ordinary-tile leave-one-match-out countercheck,
both achieve 6/16 scorable queries, while 20 more lack true-class references.
Neither learned candidate qualifies for Runtime. This is not a complete learned
model search or evidence against stronger pretrained representations. This host
currently has no torch/torchvision/pretrained weights; the prior MobileNet
experiment remains historical evidence, not a newly rerun model.

Four existing uploaded videos were recovered, SHA-verified and sequentially
decoded: `55328a7b…` (217.083 s), `4ffc9187…` (206.467 s), `7a8edc73…`
(188.6 s), `3c15ab16…` (188.6 s). Existing exact-SHA source records assign
all four to the same Sep-26 original match; the last two cover the same events
and do not increase independence. Twelve fixed quarter/middle/three-quarter
anchors were reviewed: ten show opened indicators and two show settlement.

Selected one private crop per class for **M1, M6, P5, P6, S8, SOUTH**. This
recovers five real yellow-skin development classes beyond the current approved
M6-only bank. Each binds source SHA, sequential ordinal, exact RGB hash,
detected classification bbox and crop hash. These new labels are assistant
visual reviews, not user-confirmed Gold labels; they remain unapproved staging
material, with no template admission. The private six-crop packet is retained
separately; no pixels were added to Git. Source time uses frame/fps only as a
description; RGB hashes/decoded ordinals are authoritative for these VFR inputs.

Current raw candidates match 8/10 visible indicator anchors, but all ten are
below threshold; P6 becomes P7 in both encodings of the same event. These are
selected revealed checkpoints, not continuous accuracy. The new samples can
support a development training comparison, but require source-diverse Gold
queries and calibration before any promotion. They do not resolve the pending
Gold E source gap or the 517-window zero-advice product baseline.

### Immediate recognition work

Prioritize opened-Gold crop/appearance qualification, then the dominant concealed
identity/support failures on fixed frames. Do not lower 0.82, fill UNKNOWN from
the top candidate, tune to reproduce old PNG hashes, or claim a fix from CI.
Review stable/animation truth before changing geometry. Test candidates on the
same locked development frames and retain a separate untouched original-match
batch for the formal gate. Existing source recovery remains relevant; adding
more diagnostic tools or moving PR files is not an accuracy result.

The historical sections below retain their original dates and source scopes.

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
