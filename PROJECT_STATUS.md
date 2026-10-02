# PROJECT_STATUS — Current Snapshot

**核对日期：2026-10-03（北京时间）**
**集成基线：main `cdcfdea`（PR #120）**
执行任务以 GitHub Issues 为准；规则以 RULE_STATUS.md 为准；历史见 CHANGELOG.md。
本页只记录能力与集成边界，任务入口见 [TODO.md](TODO.md)。

## main 已合并能力

| 模块 | 当前基线 | 边界 |
| --- | --- | --- |
| Package | `0.2.0` | wheel 内容与依赖方向由 CI 约束 |
| Rules / Environment | 144张守恒、17/16发牌、吃碰杠、补花、普通胡 | 开金占一张实体牌，最多三张可操作金；未知规则安全停止 |
| Settlement / Match | 普通结算、庄底递增/换庄重置、8局零和总账 | 杠胡/暗杠胡正常杠番+自摸×2已接通；剩余抢杠胡终局仍阻断 |
| AI | `MeldAwareShantenAgent V0.10` | V0.6固定主对照，V0.3消融；#4未闭环前不另开Agent版本线 |
| Vision | Runtime Vision V0.2 | experimental/read-only，未通过正式独立晋级门 |
| Public reconstruction | observer、tracker、Runtime bridge、action assembler、timeline/ledger | 身份、actor、turn缺证据仍UNKNOWN；不代表完整自动流水 |
| Hint / Executor | Hint Alpha内部只读 / Executor OFF | `safe_for_executor=false` |

## 未合并的开发工作

- [Draft PR #117](https://github.com/shentianzhen1/Huian-Mahjong/pull/117)：Issue #69唯一活跃集成分支。V0.1测试目标为可信当前桌面状态上的向听数/公共危险提示；完整八局流水是离线回归目标。状态门按手牌、金、副露计数与公共牌身份分别开放能力，不能由几何稳定推定牌面正确。
- #117已有真实手牌向听检查点、副露几何/切分与分类开发实验、来源锁定回归、人工确认河牌证据和UNKNOWN机器输出的独立记录。开发样本、同场多片段、人工真值及绿色CI均不能替代独立泛化证据；具体结果以该分支源码和references为准。
- [PR #121](https://github.com/shentianzhen1/Huian-Mahjong/pull/121)：独立Flue开发工具提案，未合并；不属于运行时能力。
- 其他窗口尚未推送的新增代码未纳入本页；不可根据聊天进度推定远程已存在。

## 验证约束

- Rules/Environment覆盖率CI下限为85%；测试数量与历史覆盖率不作为当前固定指标。
- 144张守恒、无第五张同牌、最多三张可操作金、两人总分2000、局号不回退、同局剩余牌不增加。
- CONFIRMED结算需对应fixture；UNKNOWN不能作为默认倍率或官方EV。
- Vision正式晋级须使用新来源、预先锁定且未揭示的盲测批次；失败后不能在同批上调参并重新称作盲测。

## 文档入口

[README](README.md)：上手与能力边界；[TODO](TODO.md)：Open Issue索引；
[RULE_STATUS](RULE_STATUS.md)：规则事实；[RULE_EVIDENCE_MATRIX](RULE_EVIDENCE_MATRIX.md)：证据与实现缺口；
[AGENTS](AGENTS.md)：工程约束；[CHANGELOG](CHANGELOG.md)：历史。
