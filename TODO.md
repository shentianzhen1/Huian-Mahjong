# TODO / Open Issue Index

当前执行工作以 **GitHub Issues** 为唯一真相源。本文件只做入口索引，不复制 Issue 正文，不保留已关闭事项。

规则事实只看 `RULE_STATUS.md`；规则证据只看 `RULE_EVIDENCE_MATRIX.md`；整体快照看 `PROJECT_STATUS.md`；历史变更看 `CHANGELOG.md`。

## P0 — 特殊结算证据

- **#1 抢金** — 精确资格 + 真实终局结算。
- **#2 三金倒** — 点击【三金倒】后的真实分数、番叠加、付款、庄位与特殊窗口优先级。
- **#3 游金计分回归 / #4 交界** — 主状态机已实现；只维护计分回归及与杠胡/抢杠胡的边界，不重新考古已关闭状态语义。
- **#4 抢杠胡 / 杠胡** — 真实付款、倍率、番叠加、庄位；这是 KONG EV 与部分游金路径的共同阻塞点。
- **#5 八花游** — 真实终局证据与特殊窗口优先级；当前 WORKING 规则不得进入官方 EV。

## P1 — AI / Vision

- **#6 AI EV / 8局上下文** — `CurrentAgent = MeldAwareShantenAgent V0.10` 固定为当前前沿；#4 闭环前不并行开新 Agent 版本。
- **#7 Vision 独立验证** — 旧8局已完成64时点同批状态栏审计并保留 false-valid 错误；新批次先用 `independent_batch_lock.py` 锁 SHA/session/帧位，再人工 truth，最后只跑已冻结 `promotion_gate.py`。
- **#69 Public Match Reconstruction V0.1** — 只读整局公开动作流水。第一局旧录像已完成 source-locked 双河区、相邻牌可见缝隙拆分、378 帧真实 detector→tracker→双 observer→assembler→严格评估；四次候选均因牌身份/独立回合 UNKNOWN 而弃权。下一步独立公共牌身份与回合线索，再扩展跨局；多源证据冲突必须 fail closed。

## Product

- **#45 Hint Alpha V0.1** — 只读提示与证据审计。Vision 未通过独立晋级门前，不包装成正式助手；Executor 保持关闭。

## P2 — 低频 / 证据工具

- **#9 低频终局规则** — 天胡 / 天听 / 8局平分。

已关闭 Issue（例如 #8）不会继续出现在本文件。需要历史请看 GitHub Closed Issues 或 `CHANGELOG.md`。
