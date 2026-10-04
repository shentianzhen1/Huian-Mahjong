# Hint Alpha V0.1

第一版内部测试应用。目标不是“自动打麻将”，而是尽早把真实对局变成可复现研发数据。

## 当前已接

- Windows 窗口采集（复用 Recorder V0.2 的 WGC / PrintWindow / 屏幕区域）
- 默认自动按局录制
- PublicState 后台诊断（比分 / 局号 / 剩余牌；需要本机 Tesseract）
- Project release + RuleSnapshot + CurrentAgent 版本写入每次证据会话
- 保留证据保存/打点API；主界面按用户要求移除打点按钮
- UNKNOWN / 非 CONFIRMED / 低置信识别的 fail-closed 提示门
- 番数 / 倍率 / 庄底 / 最终净分的 Settlement Audit 核对核心
- Executor 永久关闭
- 已关闭证据会话可导出 Hand Timeline **待人工审阅草稿**；机器/OCR/用户打点均不会自动升级为 confirmed evidence

## 仍未接入本壳

- V0.10 实时合法动作提示
- 结算页番数与倍率自动读取

这些是 Issue #45 后续阶段，不允许用猜测值临时填上。

## 内部向听与候选弃牌辅助

新增“实时对局流水”页，增量读取当前会话的 `events.jsonl`，显示状态栏观察、向听观察、采集异常、人工输入和证据打点。行动方、真实摸弃牌/吃碰杠/胡牌未证实时显示未知；候选弃牌不会作为实际动作写入。实验或人工观察不会升级为确认结算。页面保留最新1000条，切换会话清空页面；完整记录保留在对应会话目录。

主界面已接入 Runtime Vision → CurrentTableSnapshot → 结构向听提示。默认仍要求正式 Vision promotion；内部验证可用 `python -m workspace.hint_alpha.app --experimental-runtime-advisory`。该开关只允许未晋级模型在所有单次状态校验通过后显示实验提示，不跳过牌身份、稳定帧、来源、实体张数或过期校验。

也可点击“人工录牌”，输入完整手牌、金牌与自家副露组数，查看结构向听和最小向听弃牌候选。人工输入明确标为未验证，不作为 Vision 或规则证据。公共牌未完整可信时不显示真实剩余张数与危险度；结构已完成也不直接宣称可胡。

停止采集、黑屏、断流、切换会话或过期结果会撤销提示。此阶段的候选弃牌是结构牌效辅助，不等同于 CurrentAgent V0.10 的完整合法动作决策；实时 V0.10 建议仍待可信合法动作上下文接入。2026-10-04向听辅助版桌面安装包已包含本节桥接代码，默认开启内部实验显示，正式Vision晋级状态不变。

## 离线测试安装器

2026-10-04采集修复版：安装入口使用 `__main__` 保护和 `freeze_support()`，Windows spawn导入不会再次创建UI；打包后使用 `runtime\python.exe -B launch.py --spawn-check` 验证。未收到首帧或黑屏会显示诊断并保留提示关闭；WGC无法得到画面时可停止后手动改用屏幕区域后端，保持小程序可见。真实微信目标画面仍需实际复测，不以spawn或Demo验证替代。

`packaging/build_test_installer.py` 使用工作区 `.build-hint` 环境生成包含 Python 3.14 x64 和采集依赖的 Windows EXE。双击后安装到当前用户 LocalAppData，运行 Doctor，并创建桌面快捷方式，无需管理员权限或安装时联网。证据保存在该次安装目录的 `data/hint_alpha`；重复安装使用新目录，保留旧数据。

构建：先 `python -m venv .build-hint`，再 `.build-hint\Scripts\python.exe -m pip install .[hint-alpha]`，最后 `.build-hint\Scripts\python.exe packaging/build_test_installer.py`。产物位于 `dist/`，附 SHA256；构建清单保存源码提交和实际依赖版本。构建目录已存在时拒绝覆盖。

测试安装器已包含结构向听与候选弃牌，完整 V0.10 合法动作建议仍未接入。Tesseract 未内置，缺失时 PublicState OCR 不可用。卸载前保留证据数据，再删除对应安装目录和快捷方式。

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

`--demo` 不连接游戏，用于检查 UI、证据目录和自动录像壳。

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
