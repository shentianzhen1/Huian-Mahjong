# Issue #69 — existing two-match private public-meld review audit (2026-09-24)

This note contains **no original video, frame, private crop, room ID, player
name or private SHA manifest**. The user has already provided eight clips
of ONE original match and a separate, already-inspected rules replay
of ANOTHER original match. Reuse the existing material before requesting
new recordings.

## Private audit, not classifier promotion

An independently run private local source-pixel audit of the existing
candidate package checked all **nine video SHA-256 digests**, the
frame seek/geometry metadata, and the exact PNG crop pixels against the
source frames: **12/12 development candidate groups, 36/36 crops exact**.
There were zero mismatched source-frame indices beyond two frames and no
byte-identical PNG duplicates.

A second **private local temporal geometry screen** re-read the 12 selected
group positions at **±0.25 and ±0.50 seconds** around their reference frame.
The bottom_group-only development detector mirror found **12/12 groups**
at **all 4/4 adjacent timestamps each**, with per-frame group IoU ≥0.80.
This demonstrates temporal persistence for these chosen crops, **not**
generalized exposed-meld detection or evidence of a new CHI/PENG/KONG action:
concealed-hand/Gold lookalikes can also persist across frames. This proves **origin/pixel integrity only**;
the 36 identities still require human verification and no CHI/PENG/KONG
actions have been confirmed by this check.

The source lineage must record **two original matches, not nine independent
matches**. An older exporter reused `hand_number=8` on the other match's
rules-replay clip: its true meaning is *a different recording*, NOT hand 8
of the first match. Public training and evaluation must use original-match
group IDs rather than individual clip names or this hand-number field.

The visually inspected private sidecar includes tentative candidate labels
only. One proposed class (S4) occurs in both original match groups, but has
not received independent user approval. The PR #110 basic 32×48 normalized
grayscale feature yields approximately **0.180 cosine similarity** between
these two preliminary S4 crops; when comparing the separate-match crop to
the 33 private candidates in the first match, its proposed mate ranks
**33/33**, behind visually different candidates. An exploratory HOG feature
instead ranks it 7/33: neither is a valid identity decision or an estimate
of accuracy. This is a concrete **appearance-domain/generalization blocker**,
not evidence that more video by itself will solve recognition. Validate
labels and test a public-region-specific preprocessing/model before asking
for new recordings.

## Reproducible PRIVATE source-pixel verification

The PR adds `workspace.vision.private_meld_review_audit` with synthetic
CI tests; the private original clips and crop archive are kept outside
the repo. The original manifest format is
`private_existing_evidence_review_v0_1` with already-exported
`pending_human_adjudication` face crops. Supply a separate local registry:

```json
{
  "schema_version": "private_meld_sources_v0_1",
  "sources": [
    {
      "clip": "example.mp4",
      "sha256": "<exact lowercase sha256 of the private file>",
      "match_group": "verified_original_match_1"
    }
  ]
}
```

Match-group IDs in the registry must equal the original private packet's
source-group IDs. Run with the project's Vision extras:

```bash
python -m workspace.vision.private_meld_review_audit \
  --archive /private/unapproved_face_crops.zip \
  --videos /private/existing_video_clips \
  --private-registry /private/existing_sources.json
```

The verifier rejects wrong source SHA **before any decoding**, conflicting
source match IDs, unexpected/duplicate archive members, traversal, invalid
three-face partitions, wrong source frame index/resolution, a byte-altered
crop and any forged `approved` face label. It emits aggregate counts only
and cannot mark samples as independent blind evidence or runtime safe.

GitHub CI: eight **synthetic** intake tests (not the private videos)
plus original Vision tests. The independent private audit and synthetic CI
test the same type of checksum/geometry contract but are **not** a
source-disjoint classification benchmark. PR #111/#112 separately protect
against four-face-to-three false splitting and hand/Gold lookalikes.
Executor OFF; no Rules/AI/Simulator/Hint changes.

## Remaining blockers

- Human adjudication of the existing 36 face images and doubtful samples;
  do not silently turn a visual proposal into an approved training label.
- Cross-original-match public-region classification testing after approval,
  keeping a completely separate untouched test source for eventual
  promotion.
- Generic public meld-vs-hand discrimination, independent turn cues and
  the full eight-hand action ledger.

No fresh recording requested at this stage.


## Follow-up: user-confirmed identities (2026-09-24)

The user explicitly reviewed the existing G01–G12 visual contact sheet and
confirmed **all 36/36 individual proposed visible tile identities**. This
changes the status of the **PRIVATE** labeled-development sidecar only;
the immutable original candidate packet remains pending/UNKNOWN to prevent
overwriting provenance. The private approved ZIP binds the exact source
packet hash, exact displayed contact-sheet hash and the **9 SHA-verified
existing videos / 12 groups / 36 source-pixel-equal crops**; no private
SHA, pixel, raw recording or per-face label map is committed to GitHub.
The reviewer confirmed previously proposed visual identities; this is
**not** independently blind label collection.

A new pure intake/approval module
`workspace.vision.private_meld_label_confirmation` accepts a separate
explicit user declaration bound to the exact ZIP and displayed JPEG,
verifies the proposed tile class, group/face ordering, each private crop
hash, original locked external source registry and invokes the existing
exact-video pixel auditor **before** emitting a development-only
private approved-label sidecar. It rejects altered packets, unchecked or
partial approval, swapped crop proposals and attempted writes inside the
public repository. All issued labels retain UNKNOWN action/actor,
`safe_for_runtime=false` and `formal_promotion_evidence=false`.

### Offline evaluation, *existing two private original matches only*

Of the 36 now user-confirmed private face IDs, 33 come from the eight
clips of the **same first match** and three (S2, S3, S4) from the other
existing replay. There are 20 visible classes in the first and three
in the second; **only S4 overlaps**. Query the second match S4 against
the first match's 33 confirmed public crops:

| Frozen exploratory feature | True S4 rank among 33 | Observation |
|---|---:|---|
| PR #110 raw 32×48 gray (unchanged) | 33/33 | cosine ~0.180 |
| Simple CLAHE+HOG edge (offline only) | 8/33 | not reliable |

The other match's S2 and S3 have zero same-class first-match gallery
examples, so no closed-set success for those queries is valid. For an
additional **same-original-match only** different-hand diagnostic, 17
queries had a matching class in other-hand galleries: gray top-1
**6/17**, HOG top-1 **6/17**. These development diagnostics are NOT
independent blind accuracy and **do not pass public identity**. Current
PR #110's two previously inspected public source groups remain a
separate existing bank; no private samples have been imported into it.

The next development work uses these already-confirmed private samples
to address bright-face alignment, varying perspective/blur and
Gold/concealed-hand false public-meld geometry **offline**, without
requesting more recordings. Generic live public-meld identity,
independent turn and complete eight-hand actions remain NOT PASSED.


## Existing-material appearance normalization diagnostic (2026-09-24)

A **new development-only, PRIVATE input** CLI
`workspace.vision.private_public_face_offline_probe` now re-verifies the
**separately held explicit user confirmation and exact reviewed sheet**,
original source-video SHA **before decoding**, and every approved lossless
crop against the corresponding decoded source frame. It rejects modified
approval records, unsafe ZIP entries, wrong match-group provenance, pixel
tampering, attempts to make the 8 clips from the same original match appear
independent, and output to the public source checkout.

Only two fixed offline descriptors are compared:
- Existing PR #110 normalized 32×48 raw grayscale baseline.
- New *pale-face-only* connected-component crop, 4% inset, 64×96 CLAHE
  and a deterministic 9-bin 8×8-cell gradient histogram (HOG) computed
  with NumPy + OpenCV Sobel (no new package dependencies or reliance on
  optional `cv2.HOGDescriptor`).

**Actual LOCAL run using the pre-existing private approved 36-face ZIP,
external confirmation declaration and original nine video files**:

| Diagnostic | Original raw gray | Face-only fixed HOG |
| --- | ---: | ---: |
| Existing clips and original matches source-verified | 9 clips, 2 matches | 9 clips, 2 matches |
| Source crops pixel-verified | 36/36 | 36/36 |
| Single shared *cross-original-match* class's first correct rank in 33 gallery faces | 33/33 | 3/33 |
| First-match **different-clip but same-original-match** top-1 on 17 eligible queries | 6/17 | 11/17 |
| Other second-match queries lacking any gallery class | 2, abstain | 2, abstain |
| PR #110 independent other-match-group gate satisfied | 0 queries | 0 queries |

These samples were already inspected **and** the shared-class pair was
examined while choosing preprocessing: this is a **contaminated development
comparison**, not an independent blind accuracy number. The improvement
does not amount to even one validated live tile prediction. Keep all
runtime public identities and action semantics **UNKNOWN**; a new source
group would have to be frozen before a legitimate cross-match holdout.
There is still no generic false-positive discriminator for Gold + concealed
hand lookalikes, no proven independent public turn cue and no confirmed
complete eight-hand action ledger.

**CI verification:** dedicated synthetic privacy/provenance, matching-class
absence, exact-review-sheet and low-texture abstention tests run in the
Vision workflow; **real private source files are never added to GitHub or
CI**. The owner should not need to supply more footage until the existing
sample/negative-control work is exhausted.

To reproduce locally using *private* paths from outside the Git checkout:

```bash
python -m workspace.vision.private_public_face_offline_probe \
  --confirmed-zip /private/approved_36.zip \
  --user-declaration /private/external_user_declaration.json \
  --existing-videos /private/original_clips \
  --output /private/frozen_normalization_report.json
```
