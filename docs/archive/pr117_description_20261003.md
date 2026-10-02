# PR #117 description archive — 2026-10-03

Historical text preserved before the repository audit. Superseded; do not use its “current”, “next”, head SHA, CI or dataset counts as the active checkpoint. Current scope/results are in PR #117 and its branch evidence files.

## Current purpose

This is the **single active Issue #69 integration PR**, based directly on `main`.

V0.1 remains a read-only current-table advisory:
- structural shanten from trusted concealed hand + Gold + own exposed-meld count;
- effective-tile / remaining-copy metrics only when public identities are trusted;
- transparent public danger proxy only in a trusted discard window;
- fail closed on provenance, identity or physical-count conflicts;
- Executor remains OFF.

## Repository / dataset checkpoint

- current PR head: `eb812ed`
- latest head CI: **Tests ✅ / Vision Regression ✅ / Evidence Contracts ✅**
- approved Runtime V0.2 crops: **145**
- logical source sessions: **12**
- standard classes: **34/34**
- concealed classes with >=2 logical sessions: **22/34**
- reviewed `gold_skin_only` crops: **1 (M6)**
- live identity threshold: **0.82**

## 2026-10-01 — concealed-template original-match lineage gate

The latest opponent exposed-meld MobileNet development result exposed a provenance flaw in the prototype bank: the previous run selected 68 concealed-hand labels, but all 68 lacked a verified mapping from their Runtime `source_session` to an **original recorded match**. Distinct stored sessions are not sufficient evidence of independent matches.

This is now fail-closed:

- new exact-SHA registry: `references/vision/2026-10-01/concealed_template_match_lineage.development.json`;
- Runtime `source_session` is no longer accepted as an independence signal for this evaluator;
- a concealed template enters the cross-match opponent bank only when its exact source SHA256 has an explicit reviewed `match_group`;
- same-original-match templates are excluded even if their session names differ;
- missing lineage excludes the template rather than silently using it;
- current audit: **128** approved non-Gold hand labels, only **5** exact-SHA lineage-qualified, covering **M2/M6/N/P3/P8** from the reviewed 2026-09-19 eight-hand match;
- current opponent M1-M2-M3 query therefore lacks lineage-qualified **M1 and M3** templates and is now blocked **before MobileNet model loading**;
- the earlier recorded MobileNet 0/5 result remains historical development evidence, not a basis for more tuning;
- Runtime threshold remains **0.82**; Runtime/Hint/Executor behavior is unchanged.

New contract / audit files:

- `workspace/vision/concealed_template_match_lineage.py`
- `tests/test_concealed_template_match_lineage.py`
- `references/vision/2026-10-01/concealed_template_lineage_audit_v0_1.json`

Next gate: recover explicit original-match provenance for reviewed concealed M1 and M3 templates, or obtain a new source with explicit SHA/match lineage. Do not group unknown sources merely because their session names differ.

A metadata-only recovery queue is now frozen:
- **4** unresolved exact source SHA256 values;
- **8** approved M1/M3 hand labels;
- each remains `UNKNOWN_ORIGINAL_MATCH`;
- `workspace/vision/concealed_template_lineage_recovery.py` regenerates the queue deterministically;
- `references/vision/2026-10-01/concealed_template_lineage_recovery_queue_v0_1.json` is the reviewed queue;
- CI verifies session names are never treated as match evidence.

## Real first-hand 174s checkpoint

The representative three-frame burst now reaches:

- snapshot status: **PARTIAL**
- SHANTEN capability: **enabled**
- opened Gold: **M6 trusted**
- concealed tiles: **11/11 trusted**
- player exposed-meld count: **2 trusted for structure**
  - one complete 4-component cluster
  - one incomplete 2-component cluster preserved only as a count-only UNKNOWN meld because the 11-tile concealed count independently implies exactly two exposed melds
- ordinary structural shanten: **-1 / POST_DRAW_COMPLETE**
- visible remainders: **disabled**
- danger hint: **disabled**
- Executor: **OFF**

The `-1` result is only ordinary structural completeness. It is not a claim that every special Huian / Youjin condition is satisfied.

## M6 Gold closure

M6 no longer blocks this real snapshot.

The target session remains excluded from classifier templates and cross-session identity support. The reviewed yellow M6 crop only qualifies the real UI skin; it is not used to self-match the same recording. Exact M6 identity still requires independent cross-session support and the unchanged 0.82 threshold.

In the target burst the two yellow M6 copies pass at approximately **0.8317 / 0.8213**. Source-disjoint Gold evaluation keeps the reviewed yellow M6 as top-1 M6 at approximately **0.8265**, with runtime-gated accepted accuracy **100%** in the development report.

## P3 / P8 closure

Independent concealed samples from the older eight-hand match improved the same real window:

- P3: **0.7848 → 0.8942**
- P8: **0.6953 → 0.9408**

No center/enlarged discard-face material was used.

## Current remaining work

Basic structural shanten has now crossed a real-video checkpoint. The next blocker is **public-state completeness** for remaining-copy and danger output: both rivers and exposed-meld identities still need trusted current-state observations.

Full eight-hand action replay remains an offline regression target, not a V0.1 usability gate.

## Safety / merge gate

- PR remains Draft and unmerged
- no formal Vision promotion yet
- Executor OFF / `safe_for_executor=false`
- do not infer missing public tile identities
- do not lower the 0.82 identity threshold to force acceptance


## 2026-10-01 — public_meld independent-match coverage audit

The exposed-meld geometry path remains frozen after the reviewed 7/7 regular groups reached normalized 3-face classifier input. The rejected concealed-template transfer result is unchanged: 6/21 raw exact and 0/21 accepted at the existing 0.82 gate; do not lower the threshold and do not reuse concealed templates for public meld identity.

New read-only coverage audit:
- approved `public_meld` labels: **21**
- distinct public-meld classes: **17**
- independent original-match groups represented by those labels: **4**
- classes already supported by >=2 independent match groups for a genuinely new-match query: **P6, S4**
- the other currently covered classes have only one independent match group and need another independent match before comparable cross-match validation
- multiple hands/clips from one original match count once
- strict leave-one-existing-match-out would require >=3 total match groups for a class

New files:
- `workspace/vision/public_meld_identity_coverage.py`
- `tests/test_public_meld_identity_coverage.py`

Head `1234ef61` CI: Evidence Contracts **SUCCESS**, Vision Regression **SUCCESS**, Tests **SUCCESS** (Python 3.10–3.14, Rules/Environment coverage, package smoke and legacy advisory included).

This audit changes no Runtime/Hint/Executor behavior and does not constitute formal Vision promotion evidence.


## 2026-10-01 — public_meld identity-face normalization experiment

The geometry path remains frozen: reviewed regular exposed-meld groups still reach normalized 3-face input successfully. The remaining blocker is identity-domain alignment.

A source-disjoint development A/B was run on the only two currently eligible first-hand public-meld query classes (P6 and S4), with the query match group excluded and each candidate class still requiring >=2 other independent match groups.

Results:

- `legacy_gray@inset0.00`: **0/2**
- `gray_edge@inset0.00`: **1/2**
- `lab_chroma_edge@inset0.00`: **1/2**
- `gray_edge@inset0.12`: **1/2**
- `lab_chroma_edge@inset0.12`: **1/2**
- `legacy_gray@inset0.12`: **2/2**
  - P6 -> P6, margin ~= 0.065538
  - S4 -> S4, margin ~= 0.219742

Interpretation: the strongest current signal is a **query/template crop-domain mismatch**, not a need for a more complex feature family. A separate deterministic `public_meld_identity_normalization` layer now exists after face splitting and before identity feature extraction.

Safety:
- the 12% inset was selected after inspecting the same two development queries;
- therefore 2/2 is in-sample development evidence, **not** a validation accuracy claim;
- normalization remains development-only and is **not wired into Runtime/Hint/Executor by default**;
- no identity threshold was lowered;
- concealed-template reuse remains rejected;
- more independent original-match public-meld samples are still required before promotion.

New evidence note:
`references/vision/2026-10-01/public_meld_identity_normalization_v0_1.md`

Latest head `cc5c0a9`: Vision Regression **SUCCESS**, Evidence Contracts **SUCCESS**, Tests **SUCCESS** including Python 3.10-3.14, Rules/Environment coverage, package smoke and legacy advisory.


## 2026-10-01 — query-only normalization negative control and holdout gate

The 0.12 identity inset is now explicitly frozen as a **query-side development candidate only**. It must not preprocess the reviewed public-meld template bank.

A restored pre-existing private 36-face reviewed package was used locally as a tight-crop negative control; no private pixels, source hashes, player/room metadata or crop registry were uploaded.

Aggregate result with the unchanged legacy gray feature and raw templates:
- same-original-match cross-clip queries with another same-class reference: **6/17** top-1 at baseline vs **4/17** with query-side 12% inset;
- the only shared cross-original-match S4 query moved from **33/33** to **22/33** in the opposite 33-face gallery, but matching similarity decreased rather than improved;
- reverse S4 retrieval remained **3/3** and similarity also decreased.

Conclusion: 12% is **not** a generally better public-meld preprocessing rule. Current evidence supports it only as a candidate compensation for query crops carrying excess outer border after the public-meld crop/split path. Already-tight reviewed template crops stay unchanged.

The frozen candidate contract now enforces:
- normalization scope = `query_side_split_face_only`;
- template-bank preprocessing = forbidden;
- identity threshold lowering = forbidden;
- Runtime/Hint/Executor wiring = OFF;
- future validation must use an independent original match group and must not alter the frozen candidate or reuse holdout pixels as templates.

A fail-closed holdout evaluator and tests are present. The previously inspected selection queries are explicitly rejected as holdout input.

Latest head `86b1e0b`: Vision Regression **SUCCESS**, Tests **SUCCESS**, Evidence Contracts **SUCCESS**. PR remains Draft/unmerged; Executor OFF.

Current next blocker: obtain a readable independent-source public-meld query packet for the frozen candidate. Do not continue tuning the feature family or inset on the selection queries.


## 2026-10-01 — public_meld SIFT candidate and group decoder

The public-meld identity track has moved beyond the rejected concealed-template reuse and the earlier 12% grayscale crop candidate.

New development-only SIFT path:
- private retrospective user-confirmed packet: **36 faces / 12 groups / 2 original matches** kept private; no private pixels committed;
- same original match, different clips/hands: legacy grayscale **6/17** top-1 vs SIFT **13/17** top-1;
- old cross-match S4 retrospective: SIFT rank **4/33** one direction and **1/3** reverse;
- locked public query-only packet with the query match excluded and >=2 other original match groups per eligible class:
  - **P6 -> P6**, margin ~= **0.04240094**
  - **S4 -> S4**, margin ~= **0.10077920**
  - top-1 **2/2**
- these are candidate-selection/development results, **not blind validation**.

Frozen SIFT candidate:
- grayscale -> 3x bicubic -> CLAHE 2.0 / 8x8;
- SIFT nfeatures=100;
- BFMatcher L2, KNN k=2, ratio 0.80;
- fallback five best raw matches;
- best template per independent match group;
- class eligible only with >=2 other original match groups;
- any parameter change creates a new candidate.

New generic group decoder:
- accepts per-face identity scores from any backend;
- ranks only Mahjong-valid regular 3-face combinations (suited sequence or triplet);
- sequence display order is not assumed; permutations are considered;
- runner-up is a genuinely different canonical meld, not another permutation;
- optional development margin/face-score gate can abstain;
- action_kind remains UNKNOWN and stacked KONG is not handled here.

Safety:
- existing Runtime public identity bridge is unchanged;
- no threshold lowering;
- no private pixels uploaded;
- Runtime/Hint/Executor remain OFF for SIFT and group decoding;
- future SIFT validation must use a **new independent original match group** not used to select this candidate.

Latest exact head `a6db3a1`: Evidence Contracts **SUCCESS**, Vision Regression **SUCCESS**, Tests **SUCCESS** including Python 3.10-3.14, Rules/Environment coverage, installed-package smoke and legacy advisory.


## 2026-10-01 — frozen SIFT holdout qualification

The SIFT development candidate is now frozen end-to-end before any future blind evaluation.

Frozen selection provenance:
- the candidate contract records all match groups inspected while choosing the SIFT path:
  - `reviewed_recording_66fe`
  - `reviewed_recording_b389`
  - `reviewed_match_2026_09_19_eight_hand`
  - `reviewed_recording_14`
  - `reviewed_match_2026_09_26_first_hand`
- none of these may later be relabeled as a SIFT holdout;
- registering a future source does not make its pixels template-eligible.

Implementation / contract lock:
- SIFT preprocessing and matcher parameters are exported as implementation constants;
- CI compares those constants to the frozen candidate JSON;
- any silent drift in scale, CLAHE, keypoint count, KNN, ratio, fallback count or independent-match requirement fails tests.

New blind evaluator:
- `workspace/vision/public_meld_sift_holdout.py`
- requires a query-only packet from a **new independent original match group**;
- source session / source SHA / match group must match the locked source registry;
- query path and SHA are verified;
- any query/source already used as a `public_meld` identity template is rejected;
- candidate parameters cannot change after freeze;
- current first-hand P6/S4 selection packet is explicitly rejected as future holdout evidence;
- output remains development-only with Runtime/Hint/Executor OFF and no production threshold.

Exact latest head `edbb54d`:
- Evidence Contracts **SUCCESS**
- Tests **SUCCESS** (Python 3.10–3.14, Rules/Environment coverage, installed-package smoke, legacy advisory)
- Vision Regression **SUCCESS**, including the new public-region contract/holdout tests and unchanged Runtime V0.2 regression.

### Evidence boundary now

Further tuning on the already reviewed matches would contaminate the next validation step. The next meaningful public-meld identity evidence must come from a genuinely new original match group that was not used anywhere in SIFT candidate selection.

No merge, Runtime promotion, Hint change or Executor change is authorized by this work.


## 2026-10-01 — Drive source recovery and large-video chunk provenance

The connected Drive `Huian` folder was inspected directly rather than relying on search indexing.

Recovered source inventory:
- the older 2026-09-19 eight-hand recordings and independent `14.mp4` are still present;
- the 2026-09-26 live eight-hand match is present as four large screen recordings;
- the later three recordings cover rounds 2-8 according to the existing private eight-round reconciliation manifest;
- raw video remains private and is not committed.

Current chat/container transport limitation:
- the later three source recordings are approximately 192-224 MB each;
- the current file-materialization path rejects files above 100 MB;
- this is a transport constraint, not missing evidence.

New local-only engineering support:
- `workspace/vision/private_video_chunking.py`
- `tests/test_private_video_chunking.py`
- default 45-second chunk plan;
- ffmpeg stream-copy command generation;
- source SHA / match-group / chunk interval / derived SHA/size record;
- derived chunks remain the SAME original source and can never count as new independent match groups;
- frame-level use still requires the existing `verified_frame_lineage` check;
- raw/derived media stays private;
- Runtime/Hint/Executor behavior is unchanged.

Exact head `b806e73` CI:
- Evidence Contracts **SUCCESS**
- Vision Regression **SUCCESS**
- Tests **SUCCESS** including Python 3.10-3.14, Rules/Environment coverage, installed-package smoke and legacy advisory.

Next data step: locally segment the 2026-09-26 rounds 2-8 source recordings, scan for stable public meld groups, and add only source-qualified reviewed identity evidence. Do not count multiple chunks/hands from that same eight-hand match as independent validation sources.
