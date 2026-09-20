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

`MatchScoreState` 负责1000/1000总账；`MatchProgressState` 在此基础上继续记录当前庄家和连续坐庄次数，并自动计算下一局庄底。庄赢或流局留庄并使下一局当前庄底+5；庄输换庄后，新庄当前结算底重置为10。闲家自身显示底仍为5。两层都只消费已经结算的真实 rewards，不猜UNKNOWN单局结算。

因此 `run_many_normal_hands`、单局胜率和±1/±2单位奖励仍只是**单局诊断/开发基线**。`run_real_ordinary_match()` 已提供第一条整场真实计分路径：每局读取 MatchProgress 的 dealer/current_dealer_base，普通平胡/自摸走 FanAggregator+Settlement，再把真实 rewards 写回1000/1000总账；规则 UNKNOWN 会停在当前局。

## 标准8局 AI A/B

AI晋级不再使用单局 `run_many_normal_hands()` 的±1/±2统计，而使用 `run_paired_real_matches()`：

```python
from workspace.ai import ShantenAgent, BaselineAgent
from workspace.simulator import run_paired_real_matches

report = run_paired_real_matches(
    range(20),
    agent_factories=(ShantenAgent, BaselineAgent),
    agent_names=("ShantenV03", "Baseline"),
    max_steps=1000,
    initial_dealer=0,
)
print(report.average_final_score_by_agent)
print(report.average_score_delta_a_minus_b)
print(report.match_wins_by_agent, report.ties)
print(report.deal_ins_by_agent)
print(report.average_deal_ins_per_match_by_agent)
print(report.win_source_counts)
print(report.unknown_reasons)
```

每个seed固定跑原座位和交换座位两场8局比赛；Agent身份跟factory走，不跟座位走。只有同seed两个座位顺序都完整结束的pair才进入最终分/点炮比较，不完整pair只计入完成率与UNKNOWN，不补成0分或平局。

2026-09-19 当前标准基线（20 seed×换座=40场完整8局）：

- ShantenAgent V0.3：38胜 / BaselineAgent：2胜 / 0平；
- 平均最终分：1150.75 vs 849.25；
- 平均分差：+301.5；
- 点炮：12 vs 43，即0.300 vs 1.075次/场；
- 320个单局的胡牌来源：自摸265、点炮胡55；
- UNKNOWN=0。

旧37:3、+228.25属于历史代码快照，不能再作为当前晋级门槛。

### 当前晋级基线：MeldAware V0.10

项目当前正式策略入口为 `workspace.ai.CurrentAgent`，等价于 `MeldAwareShantenAgent V0.10`；`TenpaiRiskTieBreakAgent V0.6`保留固定主对照，`ShantenAgent V0.3`保留牌效消融基线。

V0.6晋级使用300个互不重叠seed pair、每个seed原座位+换座两场，共600场完整8局。A/B随机seed已改为跟Agent身份走，避免换座时改变随机策略内部采样流。合并结果：V0.6 322胜、V0.3 275胜、3平；平均配对最终分差+18.9633，约95% CI +2.3881～+35.5385；点炮319 vs 350。

后续策略晋级应以 `CurrentAgent V0.10` 为主对照，并继续保留V0.6/V0.3结果。V0.10晋级证据见 `references/ai/2026-09-19/meld_aware_v010_promotion.md`；V0.6历史证据见 `references/ai/2026-09-19/v06_promotion.md`。

保存型单局评估现可使用 `--agent-a current` 或 `--agent-a shanten_v03` 显式选择当前策略或旧基线。

### V0.14 Rollout候选 pilot

`PublicRolloutAgent V0.14` 当前只作为实验候选。标准25-pair方向性测试：

```powershell
python -B -m workspace.simulator.rollout_benchmark --pairs 25 --seed-start 400000
```

该命令直接调用 `run_paired_real_matches()`，使用固定牌墙、正反换座和Agent身份稳定RNG比较 V0.14 candidate vs V0.10。pilot只用于判断是否值得扩大样本，不能作为晋级证据；正式晋级仍需更大独立seed确认。


## 普通点炮概率离线校准

`estimate_ordinary_deal_in_probabilities()` 只从玩家可见信息构造实体未见牌池并抽样可能的对手暗手。它不读取真实对手暗牌或未来牌墙，当前只估计普通点炮胡，不包含游金、三金倒、抢金等特殊状态。

`run_ordinary_deal_in_calibration()` 用双方ShantenAgent V0.3跑普通局。出牌方仅用公开信息记录预测；下一次对手响应时，Environment若在 `AFTER_DISCARD` 提供合法HU，就将上一张弃牌标为真实点炮，否则标为非点炮。校准器本身同样不读取隐藏手牌。

```python
from workspace.simulator import run_ordinary_deal_in_calibration

report = run_ordinary_deal_in_calibration(
    range(100), mc_samples=16, max_steps=1000)
print(report.auc)
print(report.brier_score, report.constant_base_rate_brier)
print(report.mean_prediction_positive, report.mean_prediction_negative)
for bucket in report.bins:
    print(bucket)
```

校准通过前，该概率只属于研究特征，**不得直接解释为真实房间放铳率，也不得接管默认AI**。至少应检查AUC是否明显高于0.5、Brier是否优于常数基础率、正样本预测均值是否高于负样本，以及风险分档是否大体随预测值上升。

## 普通真实结算 V0.1

Environment 已提供 `finalize_ordinary_outcome(current_dealer_base=...)`。在普通 `HU_DECLARED` 后，它会自动重建胡牌手牌、调用 `FanAggregator`，并仅在 `FanResult.complete=True` 时使用已确认公式：

`(当前庄家底 + 赢家番) × 平胡1 / 自摸2`

生成真实零和 `rewards`。点炮胡牌张仍留在牌河，只为结构和番数分析临时加入赢家手牌。多金和普通花组已解决；玩家确认不存在独立杠费，因此完成过杠不会额外阻断普通结算。普通多拆法已改为枚举全部合法拆分并取最高总番，不再因此停止；普通数牌PENG=0番、字牌PENG=+1番、3+金点炮均已解决；普通路径当前不再因这些规则停止。抢杠胡、杠上胡等特殊结算仍会安全停止。

simulation-only 的 ±1/±2 仍保留为策略回归基线，与上述真实结算严格分离；下一阶段由8局 Match Simulator 消费真实结算结果。

## room541913 真实完整8局校验

2026-09-19完整目标房录像直接校验了 MatchProgress 的庄底与总账语义：新庄当前结算底10、连庄+5、换庄重置10；8局从1000/1000累加到1113/887，且每局均满足真实公式。结构化回归夹具位于 `tests/fixtures/settlement_room541913_8hands.json`。

玩家2026-09-19已确认：同一庄家持续连庄时庄底不上封顶，每局继续+5直到固定8局结束。因此整场若同一庄家连续坐庄8手，当前庄底依次为10、15、20、25、30、35、40、45；如果中途庄家输掉，则新庄重新从10开始。

## Ordinary-real 8局基线

2026-09-18 首次整场级回归使用10个match seed，并将 RandomAgent / BaselineAgent 交换座位，共20场；每场目标8局、1000/1000起分。

3+金点炮与PENG番规则落地后，同口径结果达到：20/20场完整跑完8局；160/160局全部真实结算，平均8局/场，规则UNKNOWN为0。这个结果只代表当前 ordinary-real 普通规则路径已闭环，不代表所有特殊胡都完成。

这说明 MatchRunner / dealer-base / 总账链路已经可运行，当前整场完成率主要受真实计分证据缺口限制，而不是8局状态机限制。未完成整场的部分比分只用于审计，不作为最终AI成绩。

### UNKNOWN 证据报告

每次 `STOPPED_UNKNOWN` 现在都会生成结构化 `unknown_evidence`：包括规则ID、state hash、手牌、花牌、副露、牌河、金牌、墙余量、pending Hu/Kong、最近动作，以及可复现的 seed/骰子/步数。普通胡发生拆牌歧义时，还会记录全部合法拆解和逐解番数。进入8局 MatchRunner 后，还会附上当前第几局、庄家、庄底、比分和 hand seed。

可直接运行 `python -m workspace.simulator.rule_gap_benchmark --count 10 --max-examples 2`，按交换座位的 ordinary-real 8局比赛统计各 UNKNOWN 次数、平均已结算局数，并为每个规则缺口保留代表证据。该工具只整理证据，不会替未知规则猜值。

## 模式与边界

- 无配置的 `Simulator.run()` 保留历史安全停止；`run_opening()` 始终停在抢金核验。
- 显式调用 `run_normal_hand()` 或 `Simulator(config=SimulatorConfig()).run()` 才使用普通局模拟模式。开局跳过抢金，事件标记simulation-only。
- config中的抢金、三金倒、游金链、八花游、广义抢杠和真实计分开关默认关闭；设置为True会返回 `STOPPED_UNKNOWN / unsupported_config`。
- `enable_added_kong=True`默认开启补杠候选。这里的 `ADD_KONG` 就是补杠/蓄杠/加杠：已经碰过三张，自己再摸到第4张后升级成明杠；这是唯一允许抢杠的杠，窗口支持 `ROB_KONG_HU` / PASS。`MING_GANG` 在代码中专指大明杠（别人打来一张、自己三张直接杠），不可抢；`AN_GANG` 暗杠也不可抢。原PENG与第4张保留至PASS，随后升级并必须尾摸、复用补花。
- 三金倒只在第三金到手瞬间触发；ordinary-only 基线固定走 CONTINUE 分支。PASS后3/4金仍可普通自摸或点炮胡，第四金不会重开三金倒。八花游固定走PASS分支，保留8个基础花番继续普通牌局。完成任何杠后普通行牌继续，16张照常0/0流局；显式游金状态、抢杠胡/杠胡等特殊路径仍按对应规则ID停止。
- 普通局自摸使用“能胡即胡”的模拟策略；真实房间能否放弃自摸继续打仍未确认。
- 平胡赢家+1/对手−1，自摸赢家+2/对手−2，流局[0,0]。均为simulation-only单位，不含真实花/金番、庄底或特殊胡计分。
- 抢杠成功 → `ROB_KONG_SCORING_UNKNOWN`；尾摸后声明杠胡 → `GANG_HU_SCORING_UNKNOWN`。大明杠/暗杠/补杠都没有独立杠费，普通杠后继续行牌，16张流局统一0/0。
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

## 当前基线（2026-09-19）

ordinary-real规则链路基线仍保持：10个match seed×交换座位共20场，20/20场完整8局、160/160局全部真实结算、平均8局/场、普通规则UNKNOWN=0。AI当前正式晋级基线为上方的 CurrentAgent / TenpaiRisk V0.6；V0.3对Baseline的38:2结果继续保留为基础牌效能力记录。

历史 simulation-only 100seed×换座曾在旧“杠费未知”版本得到195/200完成、5个 `KONG_FEE_SETTLEMENT_UNKNOWN`；该规则ID已退役，不能再视为当前基线。simulation-only结果仍只用于策略回归，不能解释为真实房胜率或真实8局最终得分。

## 历史命令验证（补杠响应实现前）

下列结果来自旧版本，不代表启用补杠专用窗口后的当前完成率；新增UNKNOWN分类应按当前代码重新评估。

seed 0–99交换座位200局：81局完成（自摸71、点炮2、流局8）、119局UNKNOWN（抢杠102、补杠14、三金倒时机3），无max_steps或死循环。完整配对16组/32局，配对平均模拟收益Random=-1.6875、Baseline=+1.6875；高UNKNOWN占比导致结果不能代表真实胜率。已从落盘报告成功校验重放第1号记录。

较早的小样本记录：

seed 0–9交换座位20局：7局自摸完成、13局UNKNOWN（抢杠12、补杠1），无max_steps或死循环。
完成局中BaselineAgent赢7局；有大量UNKNOWN和很小样本，不能据此推断真实胜率或策略强度。
