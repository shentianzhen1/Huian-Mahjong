# TODO / Open Issue Index

当前执行工作以 **GitHub Issues** 为唯一真相源。本文件只做入口索引，不复制 Issue 正文，不保留已关闭事项。

规则事实只看 `RULE_STATUS.md`；规则证据只看 `RULE_EVIDENCE_MATRIX.md`；整体快照看 `PROJECT_STATUS.md`；历史变更看 `CHANGELOG.md`。

## P0 — 特殊结算证据

- **#1 抢金** — 精确资格 + 真实终局结算。
- **#2 三金倒** — 点击【三金倒】后的真实分数、番叠加、付款、庄位与特殊窗口优先级。
- **#5 八花游** — 真实终局证据与特殊窗口优先级；当前 WORKING 规则不得进入官方 EV。

## P1 — AI / Vision / 回归维护

- **#3 游金计分回归维护** — 核心状态机及杠类结算已实现；维护既有回归，不作为P0规则缺口。

- **#6 AI EV / 8局上下文** — `CurrentAgent = MeldAwareShantenAgent V0.10` 固定为当前前沿；本轮不并行开新 Agent 版本，特殊规则 UNKNOWN 不作为正式 EV 真值。
- **#7 Vision 独立验证** — 旧8局已完成64时点同批状态栏审计并保留 false-valid 错误；新批次先用 `independent_batch_lock.py` 锁 SHA/session/帧位，再人工 truth，最后只跑已冻结 `promotion_gate.py`。
- **#69 Public Match Reconstruction V0.1** — 当前集成工作在 Draft PR #117。优先完成只读 Alpha 的当前状态、恢复与 Windows 实机验收；公开动作回放继续作证据与回归。Hand 2 正式河牌回放的 7 个 `UNKNOWN` 动作不由密集诊断候选回填。不要求人工逐张抄录八局，也不把同源候选当准确率。

## Product

- **#45 Hint Alpha V0.1** — 只读提示与证据审计；人工录牌可以独立于 Vision 提供结构向听，人工录分仅保存观察，不结算未知规则。Vision 未通过独立晋级门前不包装成正式助手；Executor 保持关闭。

## P2 — 低频 / 证据工具

- **#9 低频终局规则** — 天胡 / 天听 / 8局平分。

已关闭 Issue（例如 #4、#8）不会继续出现在本文件。需要历史请看 GitHub Closed Issues 或 `CHANGELOG.md`。
