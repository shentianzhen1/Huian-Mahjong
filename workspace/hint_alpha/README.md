# Hint Alpha V0.1

第一版内部测试应用。目标不是“自动打麻将”，而是尽早把真实对局变成可复现研发数据。

## 当前已接

- Windows 窗口采集（复用 Recorder V0.2 的 WGC / PrintWindow / 屏幕区域）
- 默认自动按局录制
- PublicState 后台诊断（比分 / 局号 / 剩余牌；需要本机 Tesseract）
- RuleSnapshot + CurrentAgent 版本写入每次证据会话
- 一键保存“识别错误 / AI建议错误 / 新规则证据 / 结算页”
- UNKNOWN / 非 CONFIRMED / 低置信识别的 fail-closed 提示门
- 番数 / 倍率 / 庄底 / 最终净分的 Settlement Audit 核对核心
- Executor 永久关闭

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
START_HINT_ALPHA.bat
```

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
