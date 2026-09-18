# 普通局 Simulator 与批量评估

在项目根目录执行，Python 3.10+，只依赖标准库。

## 快速运行

```python
from workspace.ai import BaselineAgent
from workspace.simulator import RandomAgent, Simulator, SimulatorConfig, run_many_normal_hands

game = Simulator(config=SimulatorConfig())
result = game.run_normal_hand(
    seed=3, agents=(RandomAgent(3), BaselineAgent()), max_steps=1000)
print(result.status, result.winner, result.win_source, result.rewards)
for event in result.events:
    if "decision" in event:
        print(event["seq"], event["action"], event["decision"]["reason"])

report = run_many_normal_hands(
    range(10), agent_factories=(RandomAgent, BaselineAgent),
    swap_seats=True, max_steps=1000)
print(report.to_dict())
```

手动benchmark（100个seed，交换座位后实际200局；1000局可改count或关闭交换）：

```powershell
python -B -m workspace.simulator.benchmark --count 100 --swap-seats --max-steps 1000
```

默认单元测试只运行10局随机smoke，以及seed 0/3/7的交换座位重复回归。
单局还有固定完整144张牌墙的自摸/点炮夹具，以及明确保留未参与牌的局中16张流局夹具。

## 8局比赛目标

真实目标房按玩家确认：2人、默认8局、双方开局各1000分。每局结算的零和净得失累加到总分，第8局结束后的最终分数才是项目真正要优化的结果。

`MatchScoreState` 负责1000/1000总账；`MatchProgressState` 在此基础上继续记录当前庄家和连续坐庄次数，并自动计算下一局庄底。庄赢或流局留庄并+5，庄输换庄且回到底5。两层都只消费已经结算的真实 rewards，不猜UNKNOWN单局结算。

因此本文件下面的 `run_many_normal_hands`、单局胜率和±1/±2单位奖励都只是**单局诊断/开发基线**，不是最终AI目标。后续真实8局Simulator要把当前总分、剩余局数、庄位和连庄底传给AI；策略评估以最终分数/分差为主。

## 普通真实结算 V0.1

Environment 已提供 `finalize_ordinary_outcome(current_dealer_base=...)`。在普通 `HU_DECLARED` 后，它会自动重建胡牌手牌、调用 `FanAggregator`，并仅在 `FanResult.complete=True` 时使用已确认公式：

`(当前庄家底 + 赢家番) × 平胡1 / 自摸2`

生成真实零和 `rewards`。点炮胡牌张仍留在牌河，只为结构和番数分析临时加入赢家手牌。多金、花组/拆解歧义、任何未解决杠费、抢杠胡或杠上胡都会安全停止，不制造真实分数。

simulation-only 的 ±1/±2 仍保留为策略回归基线，与上述真实结算严格分离；下一阶段由8局 Match Simulator 消费真实结算结果。

## 模式与边界

- 无配置的 `Simulator.run()` 保留历史安全停止；`run_opening()` 始终停在抢金核验。
- 显式调用 `run_normal_hand()` 或 `Simulator(config=SimulatorConfig()).run()` 才使用普通局模拟模式。开局跳过抢金，事件标记simulation-only。
- config中的抢金、三金倒、游金链、八花游、广义抢杠和真实计分开关默认关闭；设置为True会返回 `STOPPED_UNKNOWN / unsupported_config`。
- `enable_added_kong=True`默认开启补杠候选。这里的 `ADD_KONG` 就是补杠/蓄杠/加杠：已经碰过三张，自己再摸到第4张后升级成明杠；这是唯一允许抢杠的杠，窗口支持 `ROB_KONG_HU` / PASS。`MING_GANG` 在代码中专指大明杠（别人打来一张、自己三张直接杠），不可抢；`AN_GANG` 暗杠也不可抢。原PENG与第4张保留至PASS，随后升级并必须尾摸、复用补花。
- 三张以上金不再因“时机未知”停止：玩家已确认三金倒可立即声明或选择继续，因此普通 simulation-only 基线固定走 CONTINUE 分支，并继续普通牌局；该模式不计三金倒收益，也不会据此推断游金状态。完成补杠后也继续普通牌局；八花、显式游金状态、抢杠胡/杠胡以及流局杠费边界仍会按对应规则ID停止。
- 普通局自摸使用“能胡即胡”的模拟策略；真实房间能否放弃自摸继续打仍未确认。
- 平胡赢家+1/对手−1，自摸赢家+2/对手−2，流局[0,0]。均为simulation-only单位，不含真实花/金番、庄底或特殊胡计分。
- 抢杠成功 → `ROB_KONG_SCORING_UNKNOWN`；尾摸后声明杠胡 → `GANG_HU_SCORING_UNKNOWN`；普通补杠完成后不再停止，继续行牌；若含补杠的牌局到16张流局边界，则返回 `KONG_FEE_SETTLEMENT_UNKNOWN`，不假定零杠费。
- 固定墙通过 `wall=完整144张列表` 输入；`initial_state=` 只接受可校验的局中状态（含全部实体牌归属），不能与wall同时提供，也不能输入已结束对局。
- 不接Vision、Executor，不评估真实游戏胜率。

## 结果与统计口径

`SimulationResult` 返回事件、决策理由、种子/骰子、配置、初始状态/牌墙/最终状态哈希、赢家、胡牌来源、奖励、动作步数及停止原因。
决策记录在 `event.decision`，不会加入可执行的 `Action.metadata`。头尾哈希可以核验事件链，终局事件保留完整胡牌声明。

- `COMPLETED`：仅普通胡或16张流局；winner是座位0/1，流局为None。
- `STOPPED_UNKNOWN`：unresolved记录规则ID。
- `MAX_STEPS`：达到动作步数上限；最后一步已胡会先完成结算。
- `STOPPED_LOOP`：Environment检测到重复局面，保留原因。

未完成局的rewards仍是Environment的[0,0]，但这不是结算。
批量统计将其排除在胜负、流局和平均奖励之外；`reward_samples` 是已完成局数。
无完成局时均值显示0且样本数为0，不能解释为策略期望收益。

顶层wins/losses/average_reward按座位；`by_agent.A/B` 按传入的两个factory身份统计，交换座位后身份不变。
`per_seed` 保留每次运行的seed、是否交换、双方Agent、状态、来源、奖励、步数、哈希和UNKNOWN原因。
每次创建新Agent；交换座位复用牌墙/骰子/庄位以及各Agent的随机种子。
不保存整批完整事件到内存；需要单局详细日志时单独重跑该seed。

## 保存报告与校验重放

```powershell
python -B -m workspace.simulator.benchmark --count 100 --swap-seats --max-steps 1000 --output-dir data/evaluations/run_001 --progress
python -B -m workspace.simulator.replay data/evaluations/run_001 --hand-index 1 --output data/evaluations/run_001/hand_1_trace.json
```

每次选择新的输出目录；已有目录/重放文件不会被覆盖。`run.json`保存种子、Agent、配置、源码及Python版本；`hands.jsonl`逐局写入并刷新；完整批次生成`summary.json`，`completion.json`记录完成、中断或失败。Ctrl+C后已写入的对局仍可重放。数据目录默认不提交Git。

重放索引从0开始，核对源码/运行时、摘要、状态哈希和决策事件摘要后才导出完整日志。代码或Python版本不同会拒绝，需恢复到原评估环境后重试。

`paired`只统计同一输入序号的正反座位均完成的组合；重复seed仍按输入序号区分。不完整配对单独计数，无完整配对时均值为null。`paired_average_reward_by_agent`按原Agent身份给出两局平均模拟收益，不能与按座位统计混用。

## 当前基线（2026-09-18）

seed 0–99交换座位200局：195局完成、5局UNKNOWN，0 max_steps、0死循环。剩余UNKNOWN全部为 `KONG_FEE_SETTLEMENT_UNKNOWN`；完整配对95/100组，配对平均模拟奖励Random≈-1.38421、Baseline≈+1.38421。补杠完成后普通模拟继续行牌；该结果仍是simulation-only普通局策略基线，不能解释为真实房胜率或真实8局最终得分。

## 历史命令验证（补杠响应实现前）

下列结果来自旧版本，不代表启用补杠专用窗口后的当前完成率；新增UNKNOWN分类应按当前代码重新评估。

seed 0–99交换座位200局：81局完成（自摸71、点炮2、流局8）、119局UNKNOWN（抢杠102、补杠14、三金倒时机3），无max_steps或死循环。完整配对16组/32局，配对平均模拟收益Random=-1.6875、Baseline=+1.6875；高UNKNOWN占比导致结果不能代表真实胜率。已从落盘报告成功校验重放第1号记录。

较早的小样本记录：

seed 0–9交换座位20局：7局自摸完成、13局UNKNOWN（抢杠12、补杠1），无max_steps或死循环。
完成局中BaselineAgent赢7局；有大量UNKNOWN和很小样本，不能据此推断真实胜率或策略强度。
