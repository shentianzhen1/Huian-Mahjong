# Hint Alpha V0.1

第一版内部测试应用。目标不是“自动打麻将”，而是尽早把真实对局变成可复现研发数据。

## 投屏内测快速开始

打开手机投屏，选择投屏窗口；勾选“试用识别”，点击“开始内测”。
素材栏应显示版本和校验状态；金牌未确认时，可在开始后手动选择本局金牌。
辅助窗口会提示当前阻塞原因，并在建议可显示时给出“采集到文字更新”的本次耗时。
该时间不包含手机到电脑的投屏传输和屏幕绘制，不代表完整操作延迟。

## 向听内测参考包（2026-10-25）

素材版本 `2026.10.25.6` 内置 19 张参考和训练审核清单，启动时自动加载，
无需单独下载或手动选择素材包。勾选试用识别后等待当前手牌重新确认；金牌也可手动选择。

训练审核会核对10张已记录坏裁图的来源与字节，再从本次内测分类器和覆盖事实中
一起排除；不改写正式标签或原图。加载失败保留原包；关闭并重开程序可恢复内置素材。
内置素材仅供开发内测。
切换试用模式或成功加载新包后，会清空旧帧并拒绝切换前画面的延迟结果，等待新画面
重新确认；手动选定的本局金牌保留。

同一已暴露开发录像中，实际worker和建议链路复测为173/237个向听窗口、42个弃牌窗口。
这是固定源时间离线回放，不是Windows投屏延迟或独立准确率。只提供结构向听，
不开放公开剩余张数、危险度或Executor；真实Windows投屏仍需验收。

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
## 自动录像复盘

主窗口新增 **录像复盘** Tab。用户只需要选择本地真实对局视频；程序自动识别容器可解码性、原始分辨率、FPS、总时长和宽高比，并自动从 `0s` 跑到视频结尾，不再要求填写开始时间、测试时长或采样间隔。

自动采样间隔会按录像 FPS / 总时长选择，并保持三帧稳定窗口在现有 `<=0.8s` 时序约束内。原视频只在本机读取，不上传 GitHub，也不经过播放器或 WGC 缩放。

为避免整场复盘被重复计算拖慢，录像模式使用专门的离线缓存策略：Runtime Vision 的模板资源每个录像会话只构建一次，重叠三帧窗口复用已经完成的几何结果；PublicState OCR 约每 2 秒做一次 2 帧稳定读取，中间窗口复用最近一次 PublicState 观察。0.82 identity gate、UNKNOWN/fail-closed 规则和三帧 Runtime 稳定要求不因此降低。

自动流水采用增量生成。复盘过程中一旦出现新的可信换局、开金、比分变化或手牌快照事件，会立即追加到“自动流水草稿”，不再等待整段录像完成。预览帧允许丢旧帧以保持 UI 响应，但流水事件走独立队列，不因预览拥塞而丢失。

复盘链路：

`本地 MP4/MOV/AVI/MKV/M4V -> 原始像素解码 -> Runtime Vision + PublicState OCR -> 自动流水草稿`

当前自动流水草稿会记录已有链路能够直接观察到的事实：

- OCR 稳定识别到的换局；
- Runtime Vision 可信的开金；
- OCR 稳定识别到的比分基线 / 比分变化（结算方式仍为 `UNKNOWN`）；
- 可信的我方手牌快照变化。

弃牌、吃、碰、杠、对手副露等公共动作继续复用 Issue #69 的公共区域证据 / Temporal Action Assembler。新录像在公共区域尚未通过来源绑定/自动校准前，不会偷用旧录像的 ROI，也不会根据麻将合法性反推动作；流水明确标记 `PARTIAL / UNKNOWN`。

复盘完成后生成：

- `data/hint_alpha/video_tests/<name>.json`：完整诊断报告；
- `data/hint_alpha/video_tests/<name>.timeline.json`：机器可读流水草稿；
- `data/hint_alpha/video_tests/<name>.timeline.txt`：直接查看的中文流水。

界面同时显示当前录像和开发对照原始录像 `2796x1290` 的比例差；该差异只用于诊断，不会为了匹配比例而偷偷缩放画面。所有录像复盘产物固定为 development-only，不能作为 Vision 正式 promotion 证据，Executor 始终关闭。
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

### 本局金牌手动选择（实时内测）

使用支持的 `workspace.hint_alpha.live_app` 入口，开始采集后，点顶部“手动选金牌”，从中文牌名中选择开出的金牌，再点“使用本局金牌”。只需要选择金牌，手牌和副露继续自动识别；不必进入“人工录牌”。本局后续提示使用这项人工输入，不再等待自动金牌识别、金牌多帧投票或金牌模板来源资格。界面标明“手动”，证据记录标明 `MANUAL_USER_SELECTED`，不冒充视觉识别结果。

连续确认新局号、停止或重启采集会清空选择。若局号暂时无法识别，换局时点“下一局 / 清除金牌”，再选择新金牌。首次读到当前局号不会清掉本局刚选的金牌。重新选择会立即撤下旧向听提示，等待当前手牌重新确认。手动选择仅替代金牌输入，不补全未知手牌、不改变副露和实物张数检查，不启用Executor。

### 高分手牌内部试用

默认保留严格来源检查。内测时可勾选顶部“试用识别（手牌来源未验证）”：仅让分数≥0.82、且只因模板来源数量不足被拒绝的当前手牌候选参与结构向听，不改变低分、几何、张数、多帧确认等检查。提示明确带“试用”字样，不开放公开剩余张数、危险度或Executor。

需要使用已恢复的私有参考时，先解压参考包，点“加载参考样本”选择其中的 `selected.json`。然后开始采集、手动选本局金牌并勾选试用；不需要逐张手动输入整手牌。此流程还未经过真实Windows投屏验收。样本来自已暴露开发对局，试用成功不能当独立准确率或正式晋级。

离线复现使用 `workspace.hint_alpha.replay_smoke` 的 `--manual-gold M4 --experimental-hand-packet <packet>/selected.json --allow-single-source-hand --stateful-advice`。输出保留原始识别拒绝记录，同时单独记录试用标记和人工Gold来源。

2026-10-24参考包已更新为7张，新增清晰二万、四条。下载最新参考包并重新解压，点“加载参考样本”选择新的selected.json；其他操作不变。单段开发长片试用向听183/473窗口，仍非独立实机验收。

2026-10-25：现有试用开关同时启用基于牌面上下边缘的接缝切分，修复部分静态牌面被字形误切的问题。默认关闭。离线复现追加 `--experimental-edge-seams`。单段开发长片达到229/473向听窗口，其中14窗有结构弃牌候选，不包含危险度或公开剩余张数。

2026-10-25参考包版本2新增清晰九万，共8张；请重新下载解压并加载selected.json。现有试用步骤不变。单段开发长片267/473窗口可显示结构向听，其中36窗有结构弃牌候选，尚不代表独立实机验收。

### 程序与素材同步

内置参考版本 `2026.10.25.6`（19张：16张普通手牌参考、3张开金显示参考）已随开发分支和Windows测试安装包交付。启动自动读取，不再需要从手机另传参考包或手动加载；顶部显示素材版本、张数及校验状态。程序会核对版本、清单和每张图片的SHA256；不匹配时明确显示错误，不会悄悄使用旧参考，可修复安装或手动加载。完整私人录像未纳入仓库。

试用识别仍由现有开关控制，金牌仍可开局手动选择。内置素材不等于分类器正式晋级；自动同步素材不会改变0.82、来源试用范围或Executor OFF。


### 自动开金参考试用（2026-10-25）

一万、四万、六万开金显示参考随素材包2026.10.25.6交付，启动时自动加载。
勾选“试用识别（牌面来源未验证）”后，允许有真实金皮参考支持、分数至少0.82、三个不同帧一致的开金显示结果用于只读向听。当前验证覆盖四万和六万；不是全34类自动金牌准确率承诺。
原始来源拒绝记录保留，界面标明试用来源；关闭试用会清除试用金牌记忆，手动选金仍可用。试用金牌不会成为可供正式环境或Executor消费的开局事实。普通手牌与手中金皮牌不使用开金参考。

开局旧模板将四万排为一万时，使用真实一万参考排除竞争候选：旧候选必须有开金参考且低于0.82，参考库只能有唯一类别达到0.82。缺失竞争类别或多个类别过线仍保持UNKNOWN；三帧和显式试用要求不变。
