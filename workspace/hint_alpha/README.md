# Hint Alpha V0.1

第一版内部测试应用。目标不是“自动打麻将”，而是尽早把真实对局变成可复现研发数据。

## 当前已接

- Windows 窗口采集（复用 Recorder V0.2 的 WGC / PrintWindow / 屏幕区域）
- 默认自动按局录制
- PublicState 后台诊断（比分 / 局号 / 剩余牌；需要本机 Tesseract）
- Runtime Vision V0.2 稳定 3 帧诊断（手牌 / Gold / 覆盖缺口 / fail-closed 状态）
- `CurrentTableSnapshot -> 普通结构向听` 的只读内测桥；默认不绕过 Vision promotion gate
- Project release + RuleSnapshot + CurrentAgent 版本写入每次证据会话
- 一键保存“识别错误 / AI建议错误 / 新规则证据 / 结算页”
- UNKNOWN / 非 CONFIRMED / 低置信识别的 fail-closed 提示门
- 番数 / 倍率 / 庄底 / 最终净分的 Settlement Audit 核对核心
- Executor 永久关闭
- 人工点选手牌、金牌和自家副露组数，单独形成 `user_entered` 快照；无需采集窗口或视觉识别
- 未确认结算规则可人工录入前后双方分数，仅生成 `OBSERVED_ONLY` 证据，不调用规则结算
- 已关闭证据会话可导出 Hand Timeline **待人工审阅草稿**；机器/OCR/用户打点均不会自动升级为 confirmed evidence

## 新版页面结构

Hint Alpha 主窗口现在按使用场景拆成三个 Tab：

- **实时流水**：顶部固定显示第几局 / 金牌 / 剩余牌 / 双方比分；左侧保留连续流水，右侧显示当前手牌、自家副露组数、对方副露接入状态和当前阶段；底部只显示采集、手牌、金牌、局号和流水完整度。
- **AI 提示**：只展示结构向听 / 弃牌候选等只读建议，不混入 OCR、frame ID、coverage 等研发信息。
- **识别诊断**：保留原始实时预览、PublicState OCR、Runtime Vision、证据目录、版本信息和一键证据打点。

实时流水只记录已有链路明确接受的事实，例如局号变化、比分变化、可信金牌和人工录牌更新。当前实时壳尚未接入双方河牌和对手副露的低层牌面识别，因此不会伪造“对方出牌 / 吃 / 碰 / 杠”等事件；缺失动作保持 `UNKNOWN`，页面继续运行而不是中断。
## 直接录像测试

主窗口新增 **录像测试** Tab，用于把本地真实对局录像直接送入与 GitHub 回放相同的识别边界，不经过播放器、窗口缩放或 WGC：

`本地 MP4/MOV/AVI/MKV -> 原始像素解码 -> 3 帧 Runtime Vision -> CurrentTableSnapshot / structural hint`

同一组原始帧还会独立送入 PublicState OCR，用于查看第几局、剩余牌数和双方比分。OCR 缺失或失败只记录为 PublicState 错误，不会中止 Runtime Vision 测试。

使用步骤：

1. 打开 Hint Alpha，进入“录像测试”或点击顶部“录像测试”。
2. 选择本地真实对局视频；程序只读取本机文件，不上传原视频。
3. 默认从 0 秒开始测试 30 秒；测试时长填 `0` 可跑到视频结尾；默认采样间隔 `0.20s`。
4. 点击“开始录像测试”。左侧显示直接解码的原始帧，右侧显示原始分辨率/比例、Runtime 接受/阻塞窗口、可信手牌/金牌窗口、PublicState 局号票数和 OCR 错误数。
5. JSON 报告保存在 `data/hint_alpha/video_tests/`，其中保留 source SHA、原始分辨率、比例差、逐窗口 Runtime/PublicState 结果。

界面会把当前录像比例和开发对照原始录像 `2796x1290` 做只读差异提示；该差异**不是识别 gate**，不会为了匹配比例而偷偷缩放画面。录像测试报告固定标记 `development_only=true`、`formal_promotion_evidence=false`、`safe_for_executor=false`。
## 仍未接入本壳

- 双方弃牌河 / 对手副露的原始截图低层识别，因此实时危险牌提示仍保持关闭
- 实时 hand / draw / gold -> GameState 桥接（当前向听路径不需要 GameState）
- V0.10 实时合法动作提示
- 结算页番数与倍率自动读取
- 独立 Windows EXE 安装器

这些是 Issue #45 后续阶段，不允许用猜测值临时填上。

## 本地启动

开发环境：

```bat
INSTALL_HINT_ALPHA.bat
CHECK_HINT_ALPHA.bat
START_HINT_ALPHA.bat
```

### 环境自检

`INSTALL_HINT_ALPHA.bat` 会自动寻找可用的 Python 3.10–3.14，安装完成后运行一次 Doctor。之后任何时候都可以双击 `CHECK_HINT_ALPHA.bat`，或执行：

```powershell
.\.venv-hint-alpha\Scripts\python.exe -m workspace.hint_alpha.doctor
```

Doctor 分开报告：
- `Demo Ready`：UI/证据壳能否启动；
- `Live Capture Ready`：Windows Capture + pywin32 是否齐全；
- `PublicState OCR Ready`：Tesseract 是否可用。

Tesseract 缺失只会让 PublicState OCR 不可用，不会阻止窗口采集、录像和证据保存。Doctor 固定显示 `Executor: OFF`。

也可以：

```bash
python -m workspace.hint_alpha.app --demo
python -m workspace.hint_alpha.app
```

### 未 promotion Runtime 的内部向听验证

默认启动严格尊重 Runtime Vision 报告中的 `safe_for_hint=false`，因此即使
CurrentTableSnapshot 已经能计算向听，也不会把它显示成正式提示。

仅在内部研发核对时可显式开启：

```bat
START_HINT_ALPHA.bat --experimental
```

等价于：

```bash
python -m workspace.hint_alpha.app --experimental-runtime-advisory
```

窗口标题会显示 `UNPROMOTED Runtime`。该模式只允许把通过
CurrentTableSnapshot fail-closed gate 的状态送入普通结构向听分析；它不会
调用 CurrentAgent，不会构造自动点击，也不会改变 `Executor OFF`。当前
Runtime 数据仍处于开发/原型证据状态，实验结果不能当成正式 Vision
generalization 结论。

`--demo` 不连接游戏，用于检查 UI、证据目录和自动录像壳。

### 人工输入（无需 Vision）

启动后点击“人工录牌”，逐张点选当前暗手牌，选金牌及自家副露组数，提交当前快照。摸牌后新增牌；弃牌后选中并移除对应牌，再提交。每次提交单独评估，旧提示会在编辑时立即失效。完整且物理张数合法的输入只开放普通结构向听和最小向听弃牌候选；未知牌或张数不符则 BLOCKED。人录数值未经独立核验，不算视觉识别成功；公开弃牌/副露 identity 不齐，剩余张数和危险牌始终关闭。开启人工模式会先停止当前采集并另起证据会话。

需要记下未知规则的实际分数时，点“人工录分（未知规则，仅记录）”，选择未确认结算规则 ID，输入前后双方分数。输入须各自合计 2000，结果只保存为人工观察及分数差；不推断番、付款公式或规则已确认，不用于官方 AI reward。证据留在本地 `data/hint_alpha/`，不要上传私人原始画面。Executor 始终 OFF。

PublicState 当前依赖本机 `tesseract` 命令。如果没有安装，采集和证据记录仍可运行，PublicState 会明确显示不可用，不会伪造读数。

证据默认保存到：

`data/hint_alpha/<session_id>/`

每个会话包含 `session.json`、`events.jsonl`、`frames/`、`recordings/` 和 `completion.json`。


## 导出 Hand Timeline 审阅草稿

必须先停止/关闭 Hint Alpha 会话，再由审阅者明确指定它对应第几局。桥不会从 OCR 自动猜局号，也不会把 PublicState 或结算页数值当成真值。

```powershell
python -m workspace.hint_alpha.timeline_bridge ^
  --session data/hint_alpha/<session_id> ^
  --hand 3
```

默认输出到：

`data/hint_alpha/<session_id>/timeline_drafts/hand_03_timeline.draft.json`  
`data/hint_alpha/<session_id>/timeline_drafts/hand_03_timeline.draft.md`

如一个 Hint Alpha 会话覆盖多局，可以人工指定 `--start-seq` / `--end-seq` 选择该局事件范围。所有自动转换事件固定为 `evidence_level=unknown`，需人工对照录像/截图后才能形成正式证据。
