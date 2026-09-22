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

Public Detector Calibration V0.1 位于 `public_detector_calibration.py`，并锁定 `references/vision/2026-09-22/public_detector_calibration_v0_1.json`：2 个真实开发 session、5 个对手弃牌和 5 个我方副露/杠目标已完成真实像素 bbox 复核，图片 SHA256 均验证一致；该批次永久 development-only，不进入 formal Vision promotion。

Public Tile Detector V0.1 位于 `public_tile_detector.py`：全帧几何候选 intake，不把候选直接判成弃牌/吃碰杠，也不复用 hand 模板猜公开牌身份。真实校准显示弃牌存在 `upper_protrusion` 与 `single_face` 两种尺度，副露存在普通 group 与 `3+1` 叠杠，因此 detector 不冻结单一弃牌 ROI。设计见 `references/vision/2026-09-22/public_tile_detector_v0_1.md`。

Public Candidate Tracker V0.1 位于 `public_candidate_tracker.py`：把 Public Tile Detector 的单帧 geometry candidate 变成跨帧稳定轨迹，默认连续 3 帧才 APPEARED、连续 2 帧缺失才 DISAPPEARED，并用默认 0.5s 最大观测间隔防止断流前后误续轨迹。session/超时会递增 `stream_epoch`；River/Meld Observer 在 epoch 变化后必须重新建立基线。Tracker 本身不内置河牌 ROI；只有调用方显式提供 CandidateChannel 后，稳定轨迹才可转换成 identity-UNKNOWN 的 RiverSnapshot。

Public Channel Calibration V0.1 位于 `public_channel_profiles.py`，配置见 `references/vision/2026-09-22/public_channel_profiles_v0_1.json`：把全帧 broad candidate 缩到三个 development-only channel——central action focus、upper public single、player exposed group。16 张锁定上下文帧当前从 279 个原始候选缩到 26 个 channel 候选，但这只是候选压缩，不是准确率。central/upper 的 actor/action 均必须由外部时序证据确认，禁止直接当 DISCARD。

Public Identity Shadow V0.1 已验证“直接复用 hand/draw/global 模板识别公开牌”不可行：5 张已复核公开弃牌在 detector bbox 下三种模式均为 0/5；人工 truth bbox 最好也只有 hand 模板 3/5，且平均相关度约 0.38。该实验的 source-session 精确排除实际命中 0 条模板，因此不是 leak-free 评估，但结果已经足以否决 naive cross-region reuse。公开候选继续保持 `tile_id=UNKNOWN`，下一步使用独立 `public_action / public_single / public_meld` 标签域。详见 `references/vision/2026-09-22/public_identity_shadow_v0_1.md`。

Public Identity Labels V0.1 位于 `public_identity_labels.py`，manifest 为 `references/vision/2026-09-22/public_identity_labels_v0_1.json`：独立于 hand/draw/gold 标签域，首批 17 个 approved 开发标签覆盖 `public_action=4 / public_single=1 / public_meld=12`，只覆盖 11/34 标准牌且无跨 session 同类重复，因此 runtime identity 仍固定 UNKNOWN。叠放的 3+1 补杠 face 暂不批准，避免遮挡标签污染。支持 provenance/hash 校验和本地 crop export，详见 `references/vision/2026-09-22/public_identity_labels_v0_1.md`。

Hand Context Assembler V0.1 位于 `hand_context_assembler.py`：把 PublicState 的局号/比分、独立庄家证据与 Gold 证据装成 canonical `HandContext`，并生成 UNKNOWN-only 的 `HAND_START / OPEN_GOLD` 草稿事件。不会从分数、先后手或麻将规则猜庄家，也不推庄底；座位映射未知时比分保持 UNKNOWN。设计见 `references/vision/2026-09-22/hand_context_assembler_v0_1.md`。
