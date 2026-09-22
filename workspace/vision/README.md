# vision

窗口采集验证器已在 `capture_validator/` 实现。项目根目录运行
`START_CAPTURE_VALIDATOR.bat`，详见 `capture_validator/README.md`。
此工具只验证画面采集／保存，不连接 Rules、AI 或 Executor。

离线牌面识别原型位于 `tiles_v0_1/`，只处理自己的手牌区、新摸牌区和金牌展示区。使用流程见 `tiles_v0_1/README.md`，架构边界见 `VISION_V0_1_DESIGN.md`。

Public Match Reconstruction V0.1 位于 `public_match_reconstruction.py`，负责把已经观察到的公开画面事实转换成可审计的整局动作流水。CHI/PENG/明杠要求弃牌、手牌变化、副露变化相互一致；证据不足或冲突时保持 UNKNOWN / EVIDENCE_CONFLICT。设计见 `references/vision/2026-09-22/public_match_reconstruction_v0_1.md`。该模块只读，不修改 Rules、AI、Hint Alpha 或 Executor。

Public Observers V0.1 位于 `public_observers.py`：用稳定快照差分观察双方公开弃牌河与副露 group，不假定弃牌河增长方向、换行方式或副露 group 顺序。稳定 +1 河牌才产生 `DISCARD`；副露新增或 3→4 变化产生 `MELD_DELTA`；漏帧、多重变化、身份不完整均保持 UNKNOWN/ambiguous。设计见 `references/vision/2026-09-22/public_observers_v0_1.md`。

Runtime Public Adapter V0.1 位于 `runtime_public_adapter.py`，把现有 Runtime Vision V0.2 的底部动态几何接入 Public Observers：生成我方 `MeldSnapshot`，并从前后稳定 runtime report 生成我方 `HAND_DELTA`。当前 meld 区没有独立身份分类器，因此副露牌面身份保持 UNKNOWN，不复用 hand 模板冒充已解决。设计见 `references/vision/2026-09-22/runtime_public_adapter_v0_1.md`。

Temporal Action Assembler V0.1 位于 `action_assembler.py`：把已稳定的 `DISCARD / HAND_DELTA / MELD_DELTA` 按 actor 与时间窗口组合成 CHI/PENG/MING_GANG/ADD_KONG；时序参数属于采集启发式，不属于麻将规则。过期、重复或多组合歧义均 fail closed 为 UNKNOWN。设计见 `references/vision/2026-09-22/temporal_action_assembler_v0_1.md`。

Public Match Ledger V0.1 位于 `match_ledger.py`：直接从 canonical `HandTimeline` 渲染中文整局流水，不另造展示真相源；支持简洁/审计两种视图、1/8~8/8、庄家、金、双方出牌、吃碰杠、游金状态、胡牌和结算，并检查相邻局比分连续性。设计见 `references/vision/2026-09-22/public_match_ledger_v0_1.md`。

Public Detector Calibration V0.1 位于 `public_detector_calibration.py`，并锁定 `references/vision/2026-09-22/public_detector_calibration_v0_1.json`：已有 2 个真实开发 session、5 个对手弃牌事实和 5 个我方副露/杠事实，图片 SHA256 均可验证；bbox 仍为 pending，禁止从文字描述猜坐标。该批次永久 development-only，不进入 formal Vision promotion。
