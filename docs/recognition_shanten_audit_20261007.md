## 2026-10-24：按用户指示，开局可手动选金牌

实时内测顶部新增“手动选金牌”和“下一局 / 清除金牌”。用户选定的34种普通牌之一作为本局Gold输入，不再等待自动Gold识别或其来源资格。只更换Gold事实，手牌/副露/公开区域仍来自当前Runtime观察；向听仍核对当前手牌、多帧确认、副露组数和物理张数。未改变0.82或Executor OFF。

人工选择与采集session/epoch绑定，事实来源为 `MANUAL_USER_SELECTED`，单独记录选择/清除事件。自动Gold缺失或与选择不同不会覆盖人工选择。停止/重启采集、新的连续确认局号、用户手动清除都会重置；首次读到当前局号保留刚选择的金牌。修改金牌会清掉旧提示并重启当前手牌确认。自动Gold记忆不会残留人工牌名。

这是可选的人工输入流程，不是Gold自动识别率提升，也不自动解决二筒、九条的手牌来源拒绝。已覆盖选择、修改、清除、会话隔离、初始/下一局边界、自动Gold缺失/不同、未知手牌和几何拒绝。40项本轮相关测试、12项子测试通过，另检查现有依赖边界；未跑本地全量。真实Windows投屏操作仍待用户内测，不能用这些测试冒充实机验收。

## 2026-10-24：恢复清晰条子参考，长片整手分数达标窗口0→71

从用户已有录像 `55328a7b...` 顺序解码，复核帧150的三条/七条和帧4350的二条/八条/九条，保留实际检测器裁图、原帧/裁图RGB哈希。来源为已核实9月26日原始对局，与10月12日长片不同。五张私有参考已保存，不提交像素、不写入批准模板。直灰度替代会把长片九条排成七条，停止该方向。

仅分类器对照：新增参考+原NCC的26张长片锚点24张首选正确、24张分数达标；加±3像素平移后26/26正确且全部≥0.82。134个跨组普通牌查询新增参考后原NCC为88张首选正确/45张分数达标，平移为102/82，本批错牌达标均0。之前无新增参考的平移是98/79。查询组排除9月26日和10月12日，但六组来源仍未核实，不能当独立验收。

新增离线复盘参数 `--experimental-hand-packet PATH/selected.json`：只对原结果低于0.82的普通手牌/摸牌尝试模板平移及私有参考；原先≥0.82的结果、金皮手牌和公开区域沿用原路径。可与已有 `--experimental-gold-model` 组合。默认入口不变，所有来源资格检查、几何和连续帧确认仍原样运行。

已用组合后端重跑长片473窗口：几何可信、每张手牌/摸牌分数≥0.82从0窗口变71窗口。已核验的两手末帧1812/2718候选均为13/13正确。71是重叠窗口，不是71手，也未逐个核对全部牌名。自动向听仍0/473，剩余来源拒绝主要是二筒、九条和开金四万；不能把分数达标称为可信建议。原短片实验1/44未在本轮重复测试。

此外修复影子评测因借用Hint层文件哈希而违反依赖方向的CI失败。27项相关测试、2项子测试通过，没有本地全量测试。完整逐牌/窗口证据和复现脚本：`references/vision/2026-10-24/hand_reference_recovery.development.json`。

复现长片：沿用上节Gold实验命令，额外加 `--experimental-hand-packet ../bamboo_recovered/selected.json`，输出独立文件。此参数只供离线开发，不能宣称正式识别率或已进入Windows安装器默认识别路径。

## 2026-10-24：手牌像素对齐对照（开发实验，未接入 Runtime）

针对长片拒识，固定比较原 NCC、±3 像素平移、central7 裁紧及两者组合。训练排除两段查询所属已知原始对局和十个已复核坏裁剪；未知来源仍明确保留。五个已核验画面共69张牌：原 NCC 首选69/69、分数≥0.82为49张；平移后仍69/69、57张达到门槛；central7为69/69、43张；central7加平移退化到66/69，拒绝此组合。

随后134个普通牌标签按完整已核实原始对局（未知则按精确源SHA）反查：原 NCC 首选85/134、门槛以上43张；平移98/134、门槛以上79张，两者本批均无错牌达到门槛。这不是独立原始对局验收，参数已看过开发锚点，且六组来源仍未核实。不能把NCC当作校准概率。

长片两个锚点分别从7/13、5/13提升到9/13、8/13达到分数门槛，仍不构成完整手牌；三条约0.75，九条约0.76–0.79仍拒识。下一步集中三条/九条的有效模板和字形特征，不再试已退化的central7组合。当前Runtime、来源检查、阈值均未更改；实验自动向听仍为1/517，默认0/517。证据文件包含逐查询分数和完整复现脚本，不含私有像素。

证据：`references/vision/2026-10-24/hand_translation_probe.development.json`。

# Current hand / meld / shanten audit — 2026-10-07

## 2026-10-24: Gold scoring reaches one correct structural-advice window

**The opt-in experimental backend now produces 1/517 accepted windows, up from
0/517 for the unchanged default backend. This is still far below usability.**
Short source: 1/44; long source: 0/473. This is actual sequential Runtime ->
opening memory -> hand confirmation -> structural shanten, not a manual Gold
substitution or a candidate-identity-only count.

The accepted short-source burst is **246/252/258**, ending at 8.6 seconds.
Its thirteen current concealed tiles exactly match sampled truth, Gold is M6,
there is one own kong group, and structural shanten is 0 (PRE_DRAW). No discard
or danger advice is emitted. The Gold was recognized earlier and retained by
the existing opening tracker; the current hand still had to pass two distinct
classified observations. Neither memory nor hand confirmation was bypassed.
The two following windows stop advice again when the hand loses confidence or
is waiting for confirmation. Executor remains off.

### Scoring experiment

Used 134 existing ordinary-crop queries with their whole reviewed source group
excluded from the template bank for each prediction. Unresolved sources use
exact SHA groups for exploration only. Of these, 128 yield known candidates,
96 are correct, across 9 groups (6 unresolved). Gold test source groups Sep26
and Oct12 are excluded. Ten previously reviewed poor crops are excluded from
this experimental SIFT reference bank, while the ordinary Runtime bank is kept
unchanged.

A count-only scoring trial was insufficient and, when incorrectly applied to
hand tiles, could score S9->S7 errors over 0.82. The final adapter is therefore
**opened-indicator only**. Ordinary hand/draw and playable yellow-Gold hand tiles
continue through their existing classifier. Verified identical hand/draw
components in all **517** baseline/experimental windows.

Added geometric evidence without changing the identity candidate: unique
reference correspondences, RANSAC inlier count/fraction and spatial coverage.
Repeated query points matching one reference point do not count as independent
support. A fixed logistic model (C=1, seed=0) fits correctness with one unit of
weight per source-group/tile class. Positive/negative outcomes are not forcibly
balanced; the observed weighted positive prior is about 0.6723. These fitted
scores are a development estimate, not established Gold-domain calibration.

On twelve revealed Gold queries, raw candidates remain 12/12; **6** scores pass
0.82 and none of those six is wrong. Twelve artificial true-class-removal stress
queries produce zero passing wrong candidates. This stress is not a measured
real confusion rate, and the small revealed set is not formal promotion.
The final model artifact and exact feature order are versioned alongside code.

### Why the long clip still stops

All 723 per-frame Gold decisions within its geometry-stable bursts clear the
new scoring threshold, then fail the existing per-class stored-source support
check. Its hand/draw predictions also remain incomplete in all 473 windows;
not one window has every hand score at least 0.82. Thus removing Gold source
bookkeeping alone would still not make this source usable. Prioritize hand crop /
identity quality and assess source-policy simplification with measured impact.

No default Runtime model, threshold, source support requirement, UI, AI V0.10,
or Executor setting changed. `classify_opened_gold` is an optional classifier
method used only for `region_candidate == gold`; default Template behavior is
unchanged. The new backend requires an explicit offline flag.

```sh
python -m workspace.hint_alpha.replay_smoke \
  --video /private/short.mp4 \
  --source-sha256 f39bb98a0fe715e4f31c55b68ef920207cbbe69c7048039be7ba833afb134357 \
  --duration 9.1 --stride 6 --stateful-advice \
  --experimental-gold-model references/vision/2026-10-24/gold_sift_score_model.development.json \
  --require-accepted --output /private/short_scored_stateful.json
```

Refit only this scoring experiment with `python -m
workspace.vision.tiles_runtime_v0_2.gold_score_calibration --queries
/private/sift_queries/manifest.json --exclude-match
reviewed_match_2026_09_26_eight_hand --exclude-match
reviewed_match_2026_10_12_room324504 --model-output /private/model.json
--report-output /private/check.json`. The fitting code lazily imports sklearn;
the saved model's inference needs only existing Vision dependencies and math.

Validation: 23 directly related pytest tests plus 3 canonical-module Gold reader
unittests pass; no local full suite. The Vision reader unittest is invoked by
its `workspace.vision...` module name so its existing canonical mock paths patch
the correct module. Evidence is under `gold_scored_advice_experiment_20261024`
in the existing failure-baseline record. Default 0/517 and experimental 1/517
must remain separate in progress summaries.


## 2026-10-24: Gold candidate in sequential video, including opening/settlement

Moved the repaired candidate from twelve chosen crops to the actual sequential
frame detector. The shadow runner verifies the video SHA and every baseline
sample's RGB hash, detects the explicit Gold component on each frame, computes
its detector classification crop, and applies SIFT. It never supplies a manual
tile ID to the model, changes whole-hand geometry, or opens trusted advice.

Reviewed every sampled Gold crop in chronological contact sheets. Independently
reviewed the opening and settlement full frames, including readable Gold faces
that the detector missed. This is assistant-reviewed revealed development truth
at 5 fps, not a full-frame-rate or independent holdout claim.

| Exact replay | Sampled frames | Readable Gold frames | Correct candidate | Wrong identity | Readable missed |
| --- | ---: | ---: | ---: | ---: | ---: |
| `f39bb98a…`, short | 46 | 46 | 46 | 0 | 0 |
| `de1d21b2…`, long | 475 | 462 | 460 | 0 | 2 |

The longer source has 13 sampled frames without a readable opened identity:
0..54 (opening/not-yet-revealed/blank flip) and 2832..2844 (settlement), stride 6.
All now produce no known candidate. Readable M4 is missed at frames 60 and 66:
the tile is still white during the flip and the yellow-skin detector has not
recognized its Gold role. Do not hide these misses or spend the next cycle
optimizing this short transition before scoring/advice integration.

Found and fixed one false candidate: blank yellow frame 54 had equal two-match
scores for several classes and arbitrarily became S4. A zero/tied final match
now returns UNKNOWN. This is not a new score threshold; it prevents a sort-order
tie from being presented as an observed tile identity. Numeral ties still fall
back to the full-face score when that score has a unique winner.

Three-distinct-frame candidate agreement is **44/44** short and **458/473** long.
Only 37 and 241 of those respectively also have trusted whole-hand geometry;
Gold can remain visible while a hand is moving. The shadow candidate does not
clear that separate geometry fact. First agreement is at source times 0.4s and
2.8s. In the long source the face first becomes readable at 2.0s, so sampled
candidate acquisition is 0.8s; this is not Windows processing/capture latency.

### Source qualification from directly visible settlement evidence

The long source's frame 2832 explicitly displays:
`房号324504 第1/8局 2026-10-12 21:31:14`.
The exact video SHA and full-frame RGB hash are recorded in the evidence.
Its original-match group is now `reviewed_match_2026_10_12_room324504`, superseding
UNKNOWN for this source. The development lineage registry and sampled-hand truth
are updated. This does not retrospectively make earlier tuning a holdout test.
Both the known Sep26 and Oct12 groups are excluded in the final long shadow run;
80 unrelated/unknown-lineage stored labels remain in the development training bank.

Reproduce without rerunning the full suite or all Runtime classifications:

```sh
python -m workspace.vision.tiles_runtime_v0_2.opened_gold_temporal_probe \
  --video /private/long.mp4 --replay /private/long_baseline.json \
  --exclude-match reviewed_match_2026_09_26_eight_hand \
  --exclude-match reviewed_match_2026_10_12_room324504 \
  --output /private/long_gold_shadow.json
```

Use the short video/baseline pair for the 46-frame short run. No fixed ROI or
old identity is carried across a missing observation. Private traces are
reproducible from the original videos; compact truth ranges, trace/crop digests,
misses and the opening regression are under `gold_temporal_shadow_20261024` in
the existing evidence record. No private pixels are added to Git.

**Still not delivered:** Runtime trusted Gold/advice scoring. SIFT match counts
are not 0.82 confidence and the existing advice path continues using NCC.
No trusted advice improvement is claimed: baseline remains 0/517. The next task
is Gold-domain score calibration and the correct-candidate hand/support rejection,
not another generic tool migration or a perfect opening-animation detector.


## 2026-10-24: repair the existing Gold SIFT path

Found and reproduced a concrete loader defect: `GoldTileClassifier._crop_label`
re-cropped tile-only `templates/...` assets using their original-frame bbox.
The first real Runtime asset became an all-black 40x69 image, and constructing
this classifier raised `No reviewed non-gold templates are available`.
The loader now follows the existing Runtime convention: use tile-only pixels
as-is, while full-frame source files still use bbox cropping. All **34 classes**
now load. This is a repair to an experimental classifier, not the current
Runtime's NCC classifier.

Also fixed a harmful secondary decision: the P7 query's descriptor first choice
was P7, but Hough counted five pips after badge masking and forcibly changed it
to P5. Counts now remain diagnostics and do not replace descriptor identity.
For Wan faces, normalized upper-half numeral descriptors distinguish the digit
from the common lower Wan glyph; empty/tied numeral evidence leaves the whole
face candidate unchanged. Evidence counts describe the descriptor actually used.

| Same twelve reviewed opened-Gold queries | Raw identity correct |
| --- | ---: |
| Existing product NCC candidates | 10/12 |
| Whole-face SIFT after fixing loader | 11/12 |
| SIFT + Wan numeral comparison, no pip override | 12/12 |
| Candidate after excluding known Sep26 training match | 12/12 |

The twelve queries are M6/M4 replay frames 60/120/180 and 612/1812/2718,
plus the corrected six-crop Gold packet. These are seven identities with repeated
M6/M4 observations, **not** twelve independent matches. The filtered development
bank retains 80 labels of unresolved lineage; it is not an independent holdout.
The ordinary source-disjoint stress check (existing deterministic representatives)
has 36 queries: 16 with another-match true-class support and 20 without. NCC
scores 8/16 raw correct, full-face SIFT 6/16, and the numeral candidate 6/16.
There are no full-SIFT-to-numeral-SIFT regressions in these 16, but this does not
prove Gold generalization or make the candidate a general tile classifier.

Rejected a tempting shortcut: simply adding six real-Gold references to the
NCC bank raises M6 to about 0.99, but also makes three M4 queries become M6 at
0.8256..0.8276. The matching gold UI frame can create false high scores.
This bank was not admitted and no threshold was lowered.

Reproduce the actual Gold crop comparison using a private manifest with
`queries: [{query, crop, crop_rgb_sha256, source_sha256, truth}]`:

```sh
python -m workspace.vision.tiles_v0_1.gold_classifier \
  --queries /private/sift_queries/manifest.json \
  --dataset dataset/tiles_runtime_v0_2 \
  --lineage references/vision/2026-10-01/concealed_template_match_lineage.development.json \
  --exclude-match reviewed_match_2026_09_26_eight_hand \
  --output /private/gold_sift_results.json
```

Each crop is the previously recorded `[107,41,42,57]` detector classification
crop from its source frame, or an unchanged corrected-packet crop. Manifest
RGB hashes must match; truth is used for scoring only. Raw crop pixels remain
private. Full per-query hashes/results and the broader stress check are under
`gold_sift_restoration_20261024` in the existing failure-baseline record.

**Boundary:** no Hint/UI or Runtime wiring changed. SIFT match counts are not
Runtime confidence, and mapping them to 0.82 without validation would hide a
threshold change. Automatic trusted advice therefore remains 0/517. Next work
is a frozen Gold-domain comparison on additional matches and proper scoring
calibration, rather than treating high NCC frame similarity as correctness.
This turn runs only the directly related Gold crop/selection/pip tests.


## 2026-10-24: actual pretrained training and truth corrections

**This section corrects the previous S6/G and P6 diagnoses.** Enlarged original
frames and actual detector crops show **S4/S8**, not S6/G, in the two long-clip
bursts. The stored raw candidates were correct. The six-class Gold packet's
P6 label was also wrong: its face has three green and four red dots, hence P7.
Both error claims are withdrawn. Sample frame/RGB hashes and crop pixels are
unchanged; corrected truth and a corrected private packet version are retained.
The sampled five hands now have **69/69 correct raw template candidates**, while
trusted advisory acceptance remains **0/517** across the full two replay traces.
Raw candidate correctness is not accepted-hand correctness or full-video accuracy.

Installed CPU torch/torchvision and loaded the real ImageNet MobileNetV3-Small
weights. Actually extracted pretrained features, trained a balanced LinearSVC,
and trained the last five feature blocks plus a new 34-class head for ten fixed
epochs. Missing original-match lineage and missing strict-policy classes are
reported; they do not prevent exploratory training. Exact query sources and
known query matches are excluded; unresolved training lineage remains a caveat.
No query image enters training or epoch selection.

Direct crop review also found ten ambiguous/incomplete/adjacent-content bamboo
training crops. One controlled experiment excludes these from learned training
only; production template labels and Runtime are unchanged. No substitute tile
identity is invented for these poor crops.

| Fixed five-state/eleven-Gold development comparison | Hand raw matches | Whole-hand raw exact | Gold raw matches |
| --- | ---: | ---: | ---: |
| Existing product template candidates | 69/69 | 5/5 | 9/11 |
| Frozen MobileNet + linear head, all crops | 58/69 | 0/5 | 2/11 |
| Supervised tail, all crops | 64/69 | 2/5 | 9/11 |
| Supervised tail, ten poor crops removed | 69/69 | 5/5 | 5/11 |
| Same cleaned bank, corrected Gold canvas augmentation | 66/69 | 2/5 | 5/11 |

The unfiltered tail correctly ranks all five replay Gold anchors, including M4,
but fails M1 and SOUTH in the restored six-class packet. The apparent 5/5 success
therefore does not establish an overall Gold improvement. Training-crop cleanup
improves the neural hand candidate in this revealed comparison but regresses Gold.
No learned candidate replaces the product classifier.

Fixed one real augmentation mismatch: yellow skin is now applied to the captured
tile **before** `_square_tile_canvas`, preserving white padding exactly as query
preprocessing does. Old code yellowed that padding too. The targeted regression
checks white corners, tinted face and unmodified source pixels. This input fix
is retained as `v0_3_gold_face_white_canvas`, with the measured regression reported
rather than described as an accuracy improvement. Runtime does not use it.

### Reproduce only this experiment

```sh
python -m workspace.vision.tiles_runtime_v0_2.sampled_replay_classifier_ab \
  --replay /private/short_baseline.json \
  --truth references/vision/2026-10-24/short_clip_reviewed_sample_truth_v0_1.json \
  --video /private/short.mp4 --frames 120,216,252 \
  --replay /private/long_baseline.json \
  --truth references/vision/2026-10-24/long_clip_reviewed_sample_truth_v0_1.json \
  --video /private/long.mp4 --frames 1812,2718 \
  --exclude-match reviewed_match_2026_09_26_eight_hand \
  --gold-packet /private/corrected_gold_packet \
  --crop-review references/vision/2026-10-24/sampled_classifier_crop_review_v0_1.json \
  --finetune --output /private/result.json
```

Omit `--crop-review` for the full training bank. Historic old-canvas rows use the
parent augmentation version recorded in the evidence; current code reproduces
the corrected-canvas condition. The script imports torch/sklearn lazily; core
Runtime dependencies do not change. Related unit tests only were run this turn;
no full local suite. Existing automatic CI is not an accuracy result.

Detailed fixed configurations, missing-class policies, training losses, Gold
predictions, and limitations:
[sampled pretrained training](../references/vision/2026-10-24/sampled_pretrained_classifier_training_v0_1.json).
Next work should measure calibration/support rejection on correct candidates and
Gold-region model training with real skin examples. Do not repeat the withdrawn
S6/G confusion diagnosis or require complete lineage before exploratory training.
Threshold 0.82, AI V0.10, Hint read-only and Executor OFF are unchanged.


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
2706/2712/2718. **Correction:** both show S4 and S8; the earlier assistant S6/G truth was wrong.
The machine candidates S4/S8 were correct, so the previous confusion claim is withdrawn.
The two P2 candidates in each burst are correct and above 0.82 but rejected by
`class_not_cross_session_validated_in_region`. These two reviewed bursts establish **correct ranking with low scores and
insufficient source support**; they do not establish the previously claimed
S6/G ranking failures. The other 471 windows have no complete sampled truth; these two
bursts do not establish a whole-video error rate. Its original match remains UNKNOWN.
The 600/606/612 anchor contains a moving discard and is not labeled as a
constant complete-hand burst.

### Execution priorities from this attribution

1. Freeze these source/hash-bound development comparisons. Gold alone recovers
   only 3/39 reviewed windows, so hand work must proceed alongside Gold.
2. Restore qualified P2 support and its original-match lineage; a confidence or
   model change cannot replace missing provenance.
3. Evaluate Gold appearance and score/support rejection on the identical crops
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

Selected one private crop per class for **M1, M6, P5, P7, S8, SOUTH** (P6 was an assistant label error, corrected to P7 on 2026-10-24). This
recovers five real yellow-skin development classes beyond the current approved
M6-only bank. Each binds source SHA, sequential ordinal, exact RGB hash,
detected classification bbox and crop hash. These new labels are assistant
visual reviews, not user-confirmed Gold labels; they remain unapproved staging
material, with no template admission. The private six-crop packet is retained
separately; no pixels were added to Git. Source time uses frame/fps only as a
description; RGB hashes/decoded ordinals are authoritative for these VFR inputs.

After the P7 truth correction, current raw candidates match **10/10** selected
visible indicator anchors, but all ten remain below threshold. The earlier
P6->P7 error claim is withdrawn; both encodings depict seven dots. These are
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
