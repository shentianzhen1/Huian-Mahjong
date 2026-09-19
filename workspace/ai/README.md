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


## EfficiencyAgent V0.2（实验）

`EfficiencyAgent` 暂不替换稳定的 `BaselineAgent`。它保持“HU优先、可选吃碰先PASS、强制动作照做”，只替换弃牌排序：

- 先评估弃牌后的整体成组结构；
- 再按公开牌河/副露扣除可见牌，计算下一摸对手牌结构的加权改良潜力；
- 绝不读取对手暗牌、牌墙顺序或保留牌；
- 决策日志记录 shape / weighted_gain / live_improving / types，便于A/B回归。

这是轻量一层牌效率启发式，不是完整向听数、危险度或Monte Carlo。只有在配对固定seed评估稳定优于旧Baseline后，才考虑升为默认基线。


### V0.2 A/B结果

固定20个match seed、正反换座，共40场8局全部完成。结果：EfficiencyAgent 6胜，BaselineAgent 33胜，1平；平均最终分 Efficiency=925.125、Baseline=1074.875，平均分差 Efficiency-Baseline=-149.75。

结论：V0.2没有通过晋级门槛，**不得替换BaselineAgent**。这说明“手工结构分+一摸改良潜力”会产生系统性错误弃牌。下一版优先做可验证的16/17张惠安牌型向听/有效牌，再考虑公开信息危险度和Monte Carlo/EV。


## ShantenAgent V0.3（当前AI前沿）

`ShantenAgent` 使用惠安16/17张普通胡向听/有效牌引擎来排序弃牌。它保持：

- 合法HU优先；
- 可选吃碰先PASS；
- 不读取对手暗牌或牌墙顺序；
- 只把自己手牌、公开牌河、公开副露用于有效牌剩余张数。

弃牌先比较普通胡向听数，再比较公开信息下的有效牌剩余张数和有效牌种类。特殊胡继续由特殊状态机处理，不混入普通向听层。

### V0.3 A/B结果

固定20个match seed、正反换座，共40场8局，40/40完整完成：

- ShantenAgent：37胜
- BaselineAgent：3胜
- 平局：0
- 平均最终分：1114.125 vs 885.875
- 平均分差：+228.25

因此，后续AI开发不再以旧Baseline或EfficiencyAgent作为晋级门槛，**新的策略必须与ShantenAgent V0.3直接做固定牌墙+换座A/B**。

下一阶段不是继续堆手工向听启发，而是在V0.3之上增加：
1. 公开信息危险度 / 对手模型；
2. 期望得分EV；
3. 当前总分、剩余局数、庄位和连庄底的8局比赛上下文；
4. 特殊胡收益只在结算规则闭环后接入，不用猜测倍率。
