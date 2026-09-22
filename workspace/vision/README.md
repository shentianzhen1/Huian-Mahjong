# vision

窗口采集验证器已在 `capture_validator/` 实现。项目根目录运行
`START_CAPTURE_VALIDATOR.bat`，详见 `capture_validator/README.md`。
此工具只验证画面采集／保存，不连接 Rules、AI 或 Executor。

离线牌面识别原型位于 `tiles_v0_1/`，只处理自己的手牌区、新摸牌区和金牌展示区。使用流程见 `tiles_v0_1/README.md`，架构边界见 `VISION_V0_1_DESIGN.md`。

Public Match Reconstruction V0.1 位于 `public_match_reconstruction.py`，负责把已经观察到的公开画面事实转换成可审计的整局动作流水。CHI/PENG/明杠要求弃牌、手牌变化、副露变化相互一致；证据不足或冲突时保持 UNKNOWN / EVIDENCE_CONFLICT。设计见 `references/vision/2026-09-22/public_match_reconstruction_v0_1.md`。该模块只读，不修改 Rules、AI、Hint Alpha 或 Executor。

Public Observers V0.1 位于 `public_observers.py`：用稳定快照差分观察双方公开弃牌河与副露 group，不假定弃牌河增长方向、换行方式或副露 group 顺序。稳定 +1 河牌才产生 `DISCARD`；副露新增或 3→4 变化产生 `MELD_DELTA`；漏帧、多重变化、身份不完整均保持 UNKNOWN/ambiguous。设计见 `references/vision/2026-09-22/public_observers_v0_1.md`。
