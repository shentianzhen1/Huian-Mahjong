# Vision Tiles V0.1

离线原型只识别三个固定区域：自己的 `hand_region`、新摸牌 `draw_region`、金牌展示 `gold_region`。它不推断整桌状态，不调用 Rules、Environment、Simulator 或 Executor，也不会点击小程序。

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
  --output dataset/tiles_v0_1/meta/roi_profiles/huian_1108x690.json --slots

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

手工标注为权威来源。`annotate_tiles --suggest` 可显示本地模板候选，但必须由标注者确认后才写入 `labels/tiles.jsonl`。模板推理只用于验证数据闭环，后续可替换为 ONNX 模型而不改变 ROI、标签或后处理接口。

## 输出与约束

`infer_tiles` 输出 JSON，含整体 `valid`、每个槽位的 `tile_id`、`category`、`confidence`、`region`、`slot`，以及被低置信过滤的候选和约束问题。后处理会：过滤低置信候选，限制手牌最多 17 张、摸牌和金牌展示各最多 1 张，拒绝物理手牌区出现第 5 张同牌，并预留多帧投票接口。

输出永远带有 `safe_for_executor: false`。V0.1 没有自动点击接口。


## 准确率与稳定性评测

真实识别基线必须同时报告**准确率**和**多帧稳定性**，两者不能互相替代。

### 1. 人工标签留组准确率

`evaluate_tiles` 按 `source_frame`（缺失时按图片路径）整组留出测试；测试组绝不会进入模板库，避免“拿同一张牌截图训练又测试”造成数据泄漏。

```powershell
.\.venv-capture\Scripts\python.exe -m workspace.vision.tiles_v0_1.evaluate_tiles `
  --dataset dataset/tiles_v0_1 `
  --confidence 0.80 `
  --output dataset/tiles_v0_1/meta/accuracy_report.json
```

输出包括：
- approved 标签总量；
- 可评估 / 不可评估样本数和覆盖率；
- 精确牌面准确率；
- 万/筒/条/字/花类别准确率；
- 置信阈值过滤后的覆盖率和准确率；
- 每牌类、每区域准确率；
- 混淆矩阵；
- 因“该牌类只出现在测试组、训练组没有第二份真实样本”而不可评估的明细。

若没有人工 approved 标签，或真实来源组少于2组，评测器直接拒绝生成准确率，不允许用空数据或同图模板冒充真实基线。

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
