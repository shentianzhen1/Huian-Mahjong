# PROJECT_STATUS — Current Snapshot

**Snapshot date:** 2026-09-22  
**Execution truth:** GitHub Issues  
**Rule truth:** `RULE_STATUS.md` + `RULE_EVIDENCE_MATRIX.md`  
**History:** `CHANGELOG.md` only

本文件只保留一页当前快照，不复制 TODO / Issue 正文。

## Current Baselines

| Area | Current baseline | Status |
| --- | --- | --- |
| Package metadata | `0.1.0` | 第一阶段边界收紧：legacy_code 不再安装；运行时兼容层迁入 `huian._compat` |
| Rules / Environment | evidence-driven Huian 2-player rules | 普通规则与普通真实结算基本闭环；特殊结算仍有 P0 缺口 |
| Match | 2 players × 8 hands, 1000/1000 start, zero-sum | ordinary-real MatchRunner 可完整跑普通路径 |
| AI | `CurrentAgent = MeldAwareShantenAgent V0.10` | 固定当前前沿；V0.6 主对照，V0.3 消融基线 |
| Vision | Runtime Vision V0.2 | **experimental read-only**；formal promotion blocked |
| Hint Alpha | V0.1 internal advisory | 只读，不点击 |
| Executor | off | Vision 独立晋级 + 后续单独安全门之前不启用 |

## What Is Working

- **Rules / Environment**
  - 144 张实体牌守恒、庄17/闲16、补花、开金实体占牌、吃/碰/三类杠、普通胡、16张流局。
  - 金作为万能牌但不能参与副露；开出的金固定占 1 张实体牌，因此最多 3 张可操作金。
  - 普通番数聚合与普通平胡 / 自摸真实结算已接通；普通多拆法取最高番。
  - 8 局总账从 1000/1000 开始，双方分数零和；庄家连庄底 +5，换庄重置。

- **AI**
  - V0.10 仅在 CHI/PENG 窗口做副露前后牌效比较；手里有金时保持保守。
  - 对 V0.6 两批独立评估合计 200 seed-pair / 400 场：V0.10 239 胜、V0.6 159 胜、2 平，平均配对最终分差 +54.805。
  - V0.13 KONG 与 V0.14 PublicRollout 均未晋级；不要重新扩大这些已关闭实验。

- **Vision / PublicState**
  - V0.1 静态 hand+draw 严格 leave-session-out：147/149 = **98.66%**。
  - Gold 同批时序：193/196 = **98.47%**，8/8 session 多数票正确；这不是外部泛化率。
  - Runtime Vision V0.2 已加入动态几何、`draw_visual` 时序、session 隔离、只读 runtime reader。
  - Phase 5C 已揭示且有 1 个语义区域 gate 失败，因此不能作为正式泛化证据。
  - 独立晋级门与 Phase 5E source-disjoint 锁已落地（#49 / #50）；下一步只接受全新独立批次。
  - `safe_for_executor=false` 保持不变。

## Open Blockers

当前 Open Issues：**#1–#7、#9、#45、#47**。

P0 只保留真实结算证据缺口：
- **#1** 抢金：精确资格与真实终局。
- **#2** 三金倒：真实点击后的分数 / 付款 / 庄位 / 叠加。
- **#3** 游金：状态机主链已闭环；只剩计分回归与 #4 边界。
- **#4** 抢杠胡 / 杠胡：共同计分阻塞点，优先于新 Agent。
- **#5** 八花游：真实终局证据与特殊窗口优先级。

P1：
- **#6** AI：CurrentAgent 固定 V0.10；#4 未闭环前不并行开新版本。
- **#7** Vision：只做 source-disjoint 新批次并运行冻结的 `promotion_gate.py`。

Product / P2：
- **#45** Hint Alpha 继续 internal/read-only。
- **#47** hand timeline 作为“录像 → 规则证据”的统一流水格式。
- **#9** 低频终局规则等待直接证据。

## Current Priority Order

1. 收集 #1 / #2 / #4 / #5 的真实终局结算证据；#3 只做回归与 #4 交界。
2. 新录 source-disjoint Vision 批次，锁定后只跑既定 promotion gate，不用结果反调阈值。
3. 推进 #47 hand timeline，把录像转成可审计证据链。
4. Vision 未正式晋级前，Hint Alpha 不升级为“正式助手”；Executor 继续关闭。
5. #4 未闭环前，不开启新的 Agent 版本线。

## Required Regression Invariants

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
