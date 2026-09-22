# 开发与证据流程（当前执行入口仍为 GitHub Issues）

本页只规定**怎样推进工作**，不是新的进度或规则真相源。当前任务、优先级以 GitHub Issues 为准；规则事实看 `RULE_STATUS.md`，具体证据看 `RULE_EVIDENCE_MATRIX.md`；`PROJECT_STATUS.md` 只记录集成快照。

## 一次只推进一个可验收的切片

1. **选 Issue**：一个 PR 解决一个可说明的行为、证据或 CI 缺口。不要把标注、模型、评分规则和 UI 混在同一 PR。
2. **先确定证据级别**：写明来源视频 SHA256、session、帧号/时间、标注者和直接可见事实。实战截图、玩家实测、游戏规则页、外部资料不得混级。
3. **列出 UNKNOWN 与安全边界**：候选牌不是弃牌，APPEARED 不是出牌；画面里的 player/opponent 不自动等于 seat 0/1。证据冲突时保留 UNKNOWN，不推动 Rules、AI 或 Executor。
4. **先有验证样例，再改实现**：添加相应单元测试、真实帧回归或固定牌墙样例；若是新规则，先更新规则证据、RuleSnapshot 和 golden fixture。
5. **本地跑最小测试 → PR 的相关 CI → 合并**；PR 必须写明测试结果、仍未知事项和下一阶段需要的具体证据。
6. **合并后更新 Issue**：记录已验收的范围和下一个阻塞点；只有集成里程碑改变时才同步精简的 `PROJECT_STATUS.md`。`TODO.md` 不另建重复待办。

## 分支与合并纪律（避免重复劳动）

- 同一时段只维持**一个主要功能开发 PR**；P0 特殊结算可并行采证，但证据缺口不应触发未经确认的规则/AI 实现。新的 #69 切片必须明确依赖前一个已合并契约，避免多个分支分别维护同一条流水线。
- 每次开工先获取远端 `main` 的完整 SHA、Open Issues、Open PR 和最近 Actions。新分支从最新 `main` 创建；如已有待审 PR，优先完成其审查/合并，不直接在过期分支上继续叠代码。
- 提交 PR 时固定 base/head SHA、受影响层、真实数据来源、已执行测试及剩余 UNKNOWN；**新推送会使旧检查失效**，必须按最新 head 重新确认合并门槛。
- 合并后核对 `main` 的集成状态，在对应 Issue 留一条简短验收记录（成果 / 回归 / 下一个阻塞），不要同步复制整个 Issue 到 `TODO`、`PROJECT_STATUS` 或入口文档。
- 已合并且无独立未合入提交的短期分支应删除；建议仓库启用 *Automatically delete head branches*。清理历史分支前先按 PR 合并关系和 `main` 差异逐条审计；未合并实验、独立证据或仍需复现的分支须保留或先归档，**禁止按名称、日期或“看起来很旧”批量删除**。
- 流程改动用一份现有文档更新和一个聚焦 PR 验证；不再新增平行的状态页、交接页、路线图或重复任务清单。

## CI 分工（按风险匹配成本）

| 修改类型 | 最小验证 | 不应混淆的晋级结论 |
| --- | --- | --- |
| `references/vision/**/*.json`、`references/gameplay/**` | Evidence Contracts：SHA256、标注与校准关联、座位映射、真实帧 | 旧来源开发回归 ≠ 新来源泛化 |
| `references/rules/**/*.json`、`tests/fixtures/**/*.json` | Evidence Contracts：UNKNOWN 模板和真实结算 fixture 契约 | fixture 通过 ≠ 新特殊规则确认 |
| `workspace/vision/**` / `dataset/tiles_*/**` | Vision Regression + 核心代码相关测试 | CI 通过 ≠ Runtime Vision 正式晋级 |
| Rules、Environment、Simulator、AI 代码 | Tests：核心回归、coverage、安装包边界及适用评估 | 单测通过 ≠ 策略提升 |
| 纯文档 | Tests/Vision 的轻量 Scope 检查确认无代码变化，重型测试自动跳过；人工审查真相源 | 文档中不得伪造测试或规则证据 |

Tests 和 Vision Regression 对所有 PR 都创建 Scope 检查，以免纯文档 PR 因路径过滤而缺失仓库必需检查；重型 job 只在对应代码/数据变更时运行。PR 更新后的旧测试自动取消，main 分支结果保留。

手动运行的 AI Paired Evaluation、Gold/Youjin Shadow 和正式 Vision source-disjoint promotion 是**独立实验**，不是每个 PR 的默认 CI。新的 Vision 正式批次必须先锁来源和 holdout，再用冻结的 `promotion_gate.py`；看过答案后不可调参再把同批当盲测。

## Public Match Reconstruction #69：收敛为三道验收

**A. 可定位**：开局局号、玩家视角、庄家标记、Gold 及公共牌几何各自保留证据来源。已归档的开发校准和初始 V0.1 标签是回归基线；不要为“增加覆盖”改写旧截图真值或调低门槛。新来源独立追加带版本的 manifest 与测试。

**B. 可归属**：用连续真实帧验证出牌区出现/消失、actor/turn、HAND_DELTA 与 MELD_DELTA 的交叉一致性。逐个统计误轨迹、遗漏和 UNKNOWN；断流或多解时禁止拼接成确定动作。

**C. 可复盘**：机器事件进入 HandTimeline 和中文整场流水账，支持核对 1/8–8/8、吃碰杠、游金及结算。每条关键事件须能跳回原始时间戳/截图；机器重建不得自动提升为规则 CONFIRMED 证据。

完成 A/B/C 的开发回归也不代表 Vision 正式晋级：Issue #7 的新来源盲测、阈值和 Executor 独立安全门保持不变。

## PR 模板（写在 PR 正文即可）

- **Issue / 目标**：具体解决哪个阻塞，哪些功能明确不做。
- **证据**：来源 session/SHA256，是否开发数据或独立 holdout；若无新证据写明。
- **变更**：数据契约、观察者、重建、展示或规则中的哪一层，是否改变规则快照。
- **验证**：本地命令、相关 CI 链接、实际通过与失败结果；若测试仍在运行，不写“已通过”。
- **UNKNOWN / 风险**：会如何 fail closed，用户需要补录什么证据。
- **合并条件**：复现样例、相关 CI、Issue 更新；不允许用“多写了代码”替代验收。

## 当前排期边界

Public Match Reconstruction #69 优先做独立来源的公开牌身份与连续真实帧误轨迹，再做 actor/turn 和整局自动流水；P0 #1/#2/#4/#5 单独收集真实结算证据。#4 未闭环前不启动新 Agent 版本；Hint Alpha 保持只读，Executor 关闭。不要为了方便出结果，把 UNKNOWN 变成默认结算或自动点击。
