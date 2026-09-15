# AI Baseline V0.1

`BaselineAgent` 只从 Rules 给出的合法动作中选择，返回 `AgentDecision(action, reason)`：

1. 有HU则胡。
2. 需要弃牌时依次保留金牌、对子、同花色相邻或隔一张的搭子，优先打孤张；同分按牌编码稳定选择。
3. 响应时优先PASS保留当前手牌，不主动吃碰；强制摸牌时执行DRAW。

这是一套可解释启发式，尚无EV、危险度或特殊胡策略，不能声称优于真实玩家。
`PlayerObservation` 包含自己的手牌、公有牌河/花/副露、金牌、阶段、庄位和剩余牌墙数；不暴露对手手牌与牌墙顺序。
观察内的牌区使用不可变元组，决策理由写入Simulator日志，不改变动作元数据。

RandomAgent在 `workspace.simulator` 保留兼容入口；它的 `choose_decision()` 同样提供理由。
批量对战和运行命令见 [Simulator说明](../simulator/README.md)。
