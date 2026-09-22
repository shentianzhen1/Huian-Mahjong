# PROJECT_STATUS — Current Snapshot

**Snapshot date:** 2026-09-22  
**Execution truth:** GitHub Issues  
**Rule truth:** `RULE_STATUS.md` + `RULE_EVIDENCE_MATRIX.md`  
**History:** `CHANGELOG.md` only

本文件只保留一页当前快照，不复制 TODO / Issue 正文。

## Current Baselines

| Area | Current baseline | Status |
| --- | --- | --- |
| Package metadata | `0.2.0` | umbrella wheel 内容 + workspace dependency DAG 均由 CI 锁定；真实多 distribution 拆分按 core → AI/Vision → Simulator → Hint 顺序迁移 |
| Rules / Environment | evidence-driven Huian 2-player rules | 普通规则与普通真实结算基本闭环；特殊结算仍有 P0 缺口 |
| Match | 2 players × 8 hands, 1000/1000 start, zero-sum | ordinary-real MatchRunner 可完整跑普通路径 |
| AI | `CurrentAgent = MeldAwareShantenAgent V0.10` | 固定当前前沿；V0.6 主对照，V0.3 消融基线 |
| Vision | Runtime Vision V0.2 | **experimental read-only**；formal promotion blocked |
| Hint Alpha | V0.1 internal advisory | 只读，不点击；本地 Doctor 区分 Demo / Live Capture / PublicState OCR readiness |
| Executor | off | Vision 独立晋级 + 后续单独安全门之前不启用 |

## What Is Working

- **Rules / Environment**
  - 144 张实体牌守恒、庄17/闲16、补花、开金实体占牌、吃/碰/三类杠、普通胡、16张流局。
  - 金作为万能牌但不能参与副露；开出的金固定占 1 张实体牌，因此最多 3 张可操作金。
  - 普通番数聚合与普通平胡 / 自摸真实结算已接通；普通多拆法取最高番。
  - 8 局总账从 1000/1000 开始，双方分数零和；庄家连庄底 +5，换庄重置。

- **Evaluation provenance**
  - 项目 release、RuleSnapshot fingerprint、Agent version 分开记录；保存型评估升级为 schema v3。
  - runtime `source_digest` 只覆盖 `huian` / `mahjong_framework` / `workspace.ai` / `workspace.simulator`，冻结的 `legacy_code` 不再污染重放身份。

- **AI**
  - V0.10 仅在 CHI/PENG 窗口做副露前后牌效比较；手里有金时保持保守。
  - 对 V0.6 两批独立评估合计 200 seed-pair / 400 场：V0.10 239 胜、V0.6 159 胜、2 平，平均配对最终分差 +54.805。
  - V0.13 KONG 与 V0.14 PublicRollout 均未晋级；不要重新扩大这些已关闭实验。

- **Vision / PublicState**
  - V0.1 静态 hand+draw 严格 leave-session-out：147/149 = **98.66%**。
  - Gold 同批时序：193/196 = **98.47%**，8/8 session 多数票正确；这不是外部泛化率。
  - Runtime Vision V0.2 已加入动态几何、`draw_visual` 时序、session 隔离、只读 runtime reader。
  - Public Match Reconstruction 已进入 observer 阶段：`public_observers.py` 用稳定 river/meld 快照差分生成 `DISCARD` / `MELD_DELTA`，不写死弃牌方向或副露排序；多重/漏帧变化 fail closed 并重建基线。`runtime_public_adapter.py` 已把现有底部 Runtime Vision 接到我方 `MeldSnapshot` / `HAND_DELTA`；meld 身份仍保持 UNKNOWN，等待独立 meld-region 识别证据。
  - PublicState 同批8局已补 64 时点状态栏审计：primary remaining 44/63 正确；只在 primary 无法解析时启用右缘收窄 fallback 后为 54/63，63/63 可读。仍有 9 个 false-valid 误读，不能作为 Executor 依据，也不属于独立泛化证据。
  - Phase 5C 已揭示且有 1 个语义区域 gate 失败，因此不能作为正式泛化证据。
  - 独立晋级门与 Phase 5E source-disjoint 锁已落地（#49 / #50）；新增 `independent_batch_lock.py` 作为新录像进入正式盲测前的本地锁定器，先固定 SHA256 / session / 20-50-80% 帧位，再允许人工 truth。
  - `safe_for_executor=false` 保持不变。

## Open Blockers

当前 Open Issues：**#1–#7、#9、#45、#69**。

P0 只保留真实结算证据缺口：
- **#1** 抢金：精确资格与真实终局。
- **#2** 三金倒：真实点击后的分数 / 付款 / 庄位 / 叠加。
- **#3** 游金：状态机主链已闭环；只剩计分回归与 #4 边界。
- **#4** 抢杠胡 / 杠胡：共同计分阻塞点，优先于新 Agent。
- **#5** 八花游：真实终局证据与特殊窗口优先级。

P1：
- **#6** AI：CurrentAgent 固定 V0.10；#4 未闭环前不并行开新版本。
- **#7** Vision：只做 source-disjoint 新批次并运行冻结的 `promotion_gate.py`。
- **#69** Public Match Reconstruction：基础 observation/action/evidence 契约与 river/meld observer 已落地；现有 Runtime Vision 已接我方 meld/hand-delta bridge。下一阻塞是用真实帧校准双方弃牌河、对手副露低层 segmentation/identity，再接时序 assembler。

Product / P2：
- **Hand Timeline V0.1**：结构化 JSON + 确定性 Markdown 已实现；首个真实样例使用归档 match_evidence_002 / 14.mp4，只写已有审计观察，缺失过程保持 UNKNOWN。
- **#45** Hint Alpha 继续 internal/read-only；新增本地 Doctor 与自检脚本，Hint Alpha evidence session 记录 project release + RuleSnapshot + Agent provenance；Hand Timeline 草稿桥仍保持 UNKNOWN-only。
- **#9** 低频终局规则等待直接证据。

## Current Priority Order

1. 收集 #1 / #2 / #4 / #5 的真实终局结算证据；#3 只做回归与 #4 交界。
2. 新录 source-disjoint Vision 批次，锁定后只跑既定 promotion gate，不用结果反调阈值。
3. 推进 #69 Public Match Reconstruction V0.1：先完成 river/meld 稳定快照 observer，再用已复核真实帧接低层弃牌/副露 detector；最终把局号/庄家/开金、双方弃牌、副露、游金状态、胡牌/结算重建成可审计 Hand Timeline；冲突保持 UNKNOWN。
4. 已完成 Hand Timeline V0.1；后续审阅旧/新录像时按需生成 timeline，并用 Hint Alpha UNKNOWN-only 草稿桥辅助人工复核。
5. Vision 未正式晋级前，Hint Alpha 不升级为“正式助手”；Executor 继续关闭。
6. #4 未闭环前，不开启新的 Agent 版本线。

## Required Regression Invariants

- **Core coverage gate:** `huian.rules + huian.environment` measured baseline is **88%** on the 385-test suite; CI fails below **85%** aggregate coverage. This is a regression floor, not a target to game.

任何 Rules / Environment / Settlement 改动至少保持：

- 144 张实体牌守恒；不存在第 5 张同牌。
- 开出的金占 1 张实体牌，最多 3 张可操作金。
- 双人单局 / 8 局结算保持零和。
- 局号不回退；同局剩余牌不增加。
- 每个 CONFIRMED 真实结算规则应有对应 golden fixture / focused regression。
- UNKNOWN 不能被静默替换成 0、默认倍率或 AI reward。

## Documentation Map

- `README.md` — 5 分钟上手、能力边界、文档索引。
- GitHub Issues — **当前执行工作的唯一真相源**。
- `TODO.md` — Open Issue 索引，不复制执行细节。
- `RULE_STATUS.md` — 规则确认 / UNKNOWN 的唯一真相源。
- `RULE_EVIDENCE_MATRIX.md` — 规则证据与状态机缺口。
- `PROJECT_STATUS.md` — 本页当前集成快照。
- `CHANGELOG.md` — 历史，不用于判断当前状态。
- `references/` — 评估、证据、审计与失败实验归档。
