# Vision V0.1 设计说明

## 范围

Vision V0.1 是离线牌面识别原型，只处理玩家自己的手牌区、新摸牌区和金牌展示区。输入是 Recorder V0.2 生成的 AVI 或单张 PNG，输出是带置信度和约束检查结果的 JSON。它不构造完整 `GameState`，不依赖 Simulator，不识别按钮，也不调用 Executor。

## 数据流

```text
Recorder AVI
  -> 固定时间间隔抽关键帧 + frames.jsonl
  -> 按真实截图人工校准 hand/draw/gold ROI 和牌槽
  -> 三块 ROI 裁剪 + roi_crops.jsonl
  -> 人工框选牌块和确认 tile_id
  -> labels/tiles.jsonl
  -> 本地模板分类原型
  -> 低置信过滤 + 数量/四副本约束
  -> 单图 JSON 结果（safe_for_executor=false）
```

人工标签是当前唯一训练/模板来源。半自动模式只能提供已有模板的候选，最终标签必须由人确认。未来把模板分类器替换为 ONNX 模型时，保留同一套分类 ID、ROI 配置、JSONL 数据和后处理接口。

## 固定 ROI

每份 ROI profile 绑定截图精确宽高和界面布局，包含：

- `hand_region`：玩家当前手牌，不包含摸牌间隔外的独立牌。
- `draw_region`：玩家最新摸到、通常与手牌有间隔的一张牌。
- `gold_region`：按具体布局声明为 `tile` 或 `marker`。当前8局回放布局左上角只显示黄色牌背/金状态标记，不显示具体金牌牌面，因此该 profile 必须设为 `marker`，只检查标记存在，不输出 `tile_id`。真正的 gold_id 应在实时开金/翻金事件中识别并记忆；回放若缺少该事件，不能从牌背硬猜。

ROI 和槽位必须在真实截图上通过 `calibrate_rois` 选择。未校准、截图尺寸变化或缺少槽位时，离线推理直接报错，不缩放猜测坐标。

## 类别和输出

稳定牌面 ID 为 `M1..M9`、`P1..P9`、`S1..S9`、`E/SOUTH/W/N/R/G/B`、`F1..F8`；对应视觉大类为 `wan/tong/tiao/honor/flower`。类别只描述牌面，不表达吃、碰、杠、胡或特殊规则。

牌面分类只对 `region_mode=tile` 的区域运行；`marker` 区域只输出存在/不存在观测。牌槽在分类前先做亮色牌面主体存在检测，空的 draw/hand 槽不再被硬识别成任意牌。后处理再按置信阈值分离候选，并检查手牌数量、摸牌区最多一张、手牌加摸牌区同牌最多四张。`MultiFrameVoter.vote(frames)` 已预留按区域和槽位聚合多帧结果的接口；V0.1 的单图命令尚不自动调用它。

## 安全边界

所有推理 JSON 固定输出 `safe_for_executor: false`。低置信、数量异常、第五张同牌或几何不匹配都会留在结果中或直接停止推理。`marker` 观测不能替代 gold_id；只有在实时开金事件中直接看到并确认牌面后，后续状态机才可记住该 gold_id。当前模块没有鼠标、键盘、窗口控制或小程序操作代码。
