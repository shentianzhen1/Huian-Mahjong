# Vision Tiles V0.1

离线原型处理三个固定区域：自己的 `hand_region`、新摸牌 `draw_region`、金状态区域 `gold_region`。ROI profile 可把区域声明成 `tile` 或 `marker`。当前8局回放中左上角 gold 只是一张黄色牌背标记，不显示具体金牌牌面，因此回放 profile 应使用 `gold_region=marker`，不能把它当牌面分类。它不推断整桌状态，不调用 Rules、Environment、Simulator 或 Executor，也不会点击小程序。

## 数据集

`dataset/tiles_v0_1/` 的目录固定为：

```text
images/frames/       从 Recorder V0.2 AVI 抽取的关键帧
images/rois/         经过已校准 ROI 裁剪的图像
labels/tiles.jsonl   人工确认的单牌方框和牌面标签
meta/frames.jsonl    关键帧来源、帧号、时间戳、尺寸
meta/roi_crops.jsonl ROI 裁剪的可追溯记录
meta/roi_profiles/   仅限已验证窗口尺寸的 ROI/槽位配置
```

牌面 ID 与旧 Core 一致：`M1..M9`（万）、`P1..P9`（筒）、`S1..S9`（条）、`E/SOUTH/W/N/R/G/B`（字）、`F1..F8`（花）。第一版输出牌面类别与候选牌面，不定义胡、碰、杠、回合等复杂状态。

## 最小流程

在项目根目录使用 Recorder V0.2 的虚拟环境：

```powershell
.\.venv-capture\Scripts\python.exe -m workspace.vision.tiles_v0_1.extract_frames `
  data/capture_validation/recording_example.avi --dataset dataset/tiles_v0_1 --interval 1

.\.venv-capture\Scripts\python.exe -m workspace.vision.tiles_v0_1.calibrate_rois `
  dataset/tiles_v0_1/images/frames/frame_000000.png `
  --output dataset/tiles_v0_1/meta/roi_profiles/huian_1108x690.json --slots --gold-mode marker

.\.venv-capture\Scripts\python.exe -m workspace.vision.tiles_v0_1.crop_rois `
  --dataset dataset/tiles_v0_1 `
  --profile dataset/tiles_v0_1/meta/roi_profiles/huian_1108x690.json

.\.venv-capture\Scripts\python.exe -m workspace.vision.tiles_v0_1.annotate_tiles `
  dataset/tiles_v0_1/images/rois/frame_000000__hand_region.png `
  --dataset dataset/tiles_v0_1 --region hand_region

.\.venv-capture\Scripts\python.exe -m workspace.vision.tiles_v0_1.infer_tiles `
  dataset/tiles_v0_1/images/frames/frame_000000.png `
  --dataset dataset/tiles_v0_1 `
  --profile dataset/tiles_v0_1/meta/roi_profiles/huian_1108x690.json
```

`calibrate_rois` 和 `annotate_tiles` 打开本地 OpenCV 窗口。ROI 配置保存源图精确尺寸；尺寸不匹配或未校准时会拒绝裁剪/推理，避免把猜测坐标用于识别。

手工标注为权威来源。真实录像抽帧标注时应传 `--source-session <video-or-session-id>`，同一录像的所有帧使用相同 session ID。`annotate_tiles --suggest` 可显示本地模板候选，但必须由标注者确认后才写入 `labels/tiles.jsonl`。模板推理只用于验证数据闭环，后续可替换为 ONNX 模型而不改变 ROI、标签或后处理接口。

## 输出与约束

`infer_tiles` 输出 JSON，牌面区域包含 `tile_id`、`category`、`confidence`、`region`、`slot`；marker 区域单独输出 `markers` 的存在/不存在，不生成 `tile_id`。分类前先做亮色牌面主体存在检测，空槽会被跳过而不是硬猜一张牌。后处理会过滤低置信候选、限制手牌最多17张和摸牌最多1张、拒绝物理手牌区出现第5张同牌，并预留多帧投票接口。

输出永远带有 `safe_for_executor: false`。V0.1 没有自动点击接口。



### Gold 的正确观测方式

当前8局回放在对局开始后只保留左上角黄色牌背标记；该标记能证明“金状态UI存在”，但不能证明具体哪一张是金。真实运行时应在**开金/翻金事件**直接识别可见牌面并把 `gold_id` 写入会话状态，后续帧只用 marker 检查UI仍处于预期状态。若录像没有录到翻金事件，则该录像不能提供 gold_id 的视觉真值。

## 准确率与稳定性评测

真实识别基线必须同时报告**准确率**和**多帧稳定性**，两者不能互相替代。

### 0. 先检查真实数据是否够测

```powershell
.\.venv-capture\Scripts\python.exe -m workspace.vision.tiles_v0_1.dataset_status `
  --dataset dataset/tiles_v0_1 `
  --output dataset/tiles_v0_1/meta/dataset_status.json
```

该报告先回答“数据够不够测”，而不是直接给准确率。重点字段包括：已审核标签数、真实来源组数、已覆盖牌类、跨来源重复牌类、可进入留组评测的样本比例、三个ROI区域是否都有标签，以及下一批最应该补哪些牌类。只有同一牌类至少出现在两个独立来源组中（真实录像优先指两个不同 `source_session`），才能在“测试录像不进模板库”的前提下评估该类。

### 1. 人工标签留组准确率

`evaluate_tiles` 优先按 `source_session`（整段录像/录屏会话）留出测试；没有 `source_session` 时才回退到 `source_frame`，再缺失才按图片路径。来自同一录像的相邻帧必须共享同一个 `source_session`，否则会形成“同录像帧一边训练、一边测试”的泄漏。

真实小程序界面优先使用 `same_region`：手牌和摸牌的底色、边框和缩放可能不同，测试牌只和同一区域的训练模板比较。`marker` 区域不进入牌面准确率；若要评估 gold_id，必须使用真正看到金牌牌面的开金/翻金事件样本。

```powershell
.\.venv-capture\Scripts\python.exe -m workspace.vision.tiles_v0_1.evaluate_tiles `
  --dataset dataset/tiles_v0_1 `
  --confidence 0.80 `
  --template-scope same_region `
  --output dataset/tiles_v0_1/meta/accuracy_report.json
```

`--template-scope all_regions` 保留原始跨区域模板池行为，只适合兼容和域差异诊断，不建议作为真实 Executor 门槛。

输出包括：
- approved 标签总量；
- 可评估 / 不可评估样本数和覆盖率；
- 精确牌面准确率；
- 万/筒/条/字/花类别准确率；
- 置信阈值过滤后的覆盖率和准确率；
- 每牌类、每区域准确率；
- 混淆矩阵；
- 因“该牌类只出现在测试组、训练组没有同区域第二份真实样本”而不可评估的明细。

若没有人工 approved 标签，或真实来源组少于2组，评测器直接拒绝生成准确率，不允许用空数据或同图模板冒充真实基线。某一区域缺少跨来源同类样本时，该区域样本应报告为不可评估，而不是强行记为识别错误。

### 2. 连续帧稳定性

将连续、槽位对齐的推理结果写成 JSONL，每行包含 `predictions` 数组，然后运行：

```powershell
.\.venv-capture\Scripts\python.exe -m workspace.vision.tiles_v0_1.evaluate_stability `
  dataset/tiles_v0_1/meta/predictions_sequence.jsonl `
  --agreement 0.80 `
  --minimum-frames 3 `
  --output dataset/tiles_v0_1/meta/stability_report.json
```

它按 `region + slot` 报告：
- 连续可见帧数；
- 多数票牌面；
- 一致率；
- 多数牌平均置信度；
- 是否达到稳定门槛；
- 整体稳定槽位比例。

**稳定不等于准确。** 一套模型可以连续多帧稳定地认错，所以稳定性报告必须和人工标签留组准确率一起看。

### Executor 门槛

Tiles V0.1 的所有输出仍固定 `safe_for_executor: false`。当前阶段不因为某一项指标看起来好就开启自动点击；至少要先有目标小程序真实录像上的：
1. 经人工确认的 ROI；
2. 跨来源人工标签准确率；
3. 连续帧稳定性；
4. 典型错牌/混淆报告；
5. 手牌张数和物理同牌最多4张等后处理约束回归。

在这些指标可复现之前，Vision只提供观察结果，不向 Executor 发动作。
