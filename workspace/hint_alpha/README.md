# Hint Alpha V0.1

第一版内部测试应用。目标不是“自动打麻将”，而是尽早把真实对局变成可复现研发数据。

## 当前已接

- Windows 窗口采集（复用 Recorder V0.2 的 WGC / PrintWindow / 屏幕区域）
- 默认自动按局录制
- PublicState 后台诊断（比分 / 局号 / 剩余牌；需要本机 Tesseract）
- Project release + RuleSnapshot + CurrentAgent 版本写入每次证据会话
- 一键保存“识别错误 / AI建议错误 / 新规则证据 / 结算页”
- UNKNOWN / 非 CONFIRMED / 低置信识别的 fail-closed 提示门
- 番数 / 倍率 / 庄底 / 最终净分的 Settlement Audit 核对核心
- Executor 永久关闭
- 已关闭证据会话可导出 Hand Timeline **待人工审阅草稿**；机器/OCR/用户打点均不会自动升级为 confirmed evidence

## 仍未接入本壳

- 实时 hand / draw / gold -> GameState 桥接
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
