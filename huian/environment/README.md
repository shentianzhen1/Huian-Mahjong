# M2：惠安 Environment 已确认流程

本阶段新增 `HuianEnvironment`，复用 legacy 的动作、事件与基础状态结构。旧
`QuanzhouEnvironment`、M1 的 legacy 状态入口保持兼容。这里运行的是明确初始条件的
局中场景和 Simulator 普通局模式；RandomAgent / BaselineAgent 已驱动模拟循环，
完整真实惠安牌局仍受未确认特殊规则与结算限制。

## 已实现

- `HuianGameState`：待认领弃牌引用、待结算胡声明、双方特殊状态、完整实体牌记账。
- `set_state`、`reset`：先验证再替换；必须准确包含 144 张牌，不只检查数量上限。
- 吃／碰：从对手牌河最后位置取走认领牌，消耗本家所需牌，形成副露后强制弃牌。
- 明／暗杠：执行已授权的组牌动作，随后从 `wall_tail` 补摸；动作事件记录 `kong_kind` 和 `drawn_tile`，可直接构造杠胡上下文。新宣杠的抢杠范围默认 UNKNOWN。
- 补杠专用响应：按用户本轮实现要求，非金牌PENG与第4张手牌可声明 `ADD_KONG`，进入 `ROB_KONG_WINDOW`；符合资格时可 `ROB_KONG_HU`，或PASS完成 `ADDED_GANG` 后必须尾摸。明／暗杠抢杠仍未实现。该交互尚无直接抢杠录像佐证。
- PASS：对手弃牌无人认领时，清除待认领引用，弃牌留在原牌河，下一家进入 NEED_DRAW；随后从 `wall_head` 摸牌。
- 抽到花牌：在未触及 16 张流局边界时，执行已归档的庄家优先分轮补花；补花事件附在触发动作日志。新花延至下一轮。
- 普通胡声明：实际头摸、已解决杠后尾摸或对手弃牌形成合法普通胡时，生成带来源的 `HU` 动作。执行后进入 `HU_DECLARED`，记录赢家、胡牌张、杠种或原牌河位置；实体牌不重复移动或计数。
- 原子提交：动作授权、候选状态修改、后置校验、守恒与死循环检查全部通过才提交状态和日志。
- clone、checkpoint、rollback：状态、日志、重复状态集合一起保存／恢复；过期 token 被拒绝。
- 输入／返回值隔离：调用者修改 state、返回日志或动作 metadata 不会修改环境内部数据。
- 每步校验牌数、手牌长度、副露构成、来源玩家、阶段与净分零和；不允许 `strict=False`。
- 死循环检测不包含 turn_index／last_action；另设可配置动作上限。触发后报错，不伪造流局。

## 状态导入边界

普通局中手牌按 16 张减去每副露 3 张验证；摸牌后／吃碰后多一张，杠后补牌前不多一张。
杠的第四张计入副露实体牌，不参与手牌长度公式。

`pending_discard` 为 `{player, tile, river_index}`，仅引用仍在牌河的最后一张牌，不额外计数。
`pending_kong` 为 `{kong_player, tile, meld_index}`，只引用原PENG与手中的第4张。
声明补杠时不提前搬牌；PASS后第4张才移入副露，抢胡时原PENG和该张手牌保持记账。
`ROB_KONG_HU_DECLARED`阶段的`pending_hu`保留winner、loser、robbed_tile和`rob_kong`来源。
`gold_tile` 是牌种标记，不额外算实体牌。若场景中有不在手牌、牌河、副露、花区或牌墙的
实体牌，必须显式列入 `reserved_tiles`；这只是记账区，不规定开金翻牌应放在哪里。

`special_states` 默认双方 UNKNOWN。导入正常场景时必须有依据地设置为 NORMAL，不能为了
绕过校验把实际游金／不明状态标成 NORMAL。输入场景是调用者提供的前提，环境只能验证
内部一致性，不能替代 Vision 对画面的事实核验。

导入 AFTER_MING_GANG／AFTER_AN_GANG 表示外部场景已经完成杠的响应处理、正在等待补牌。
它不代表引擎自行判定了抢杠范围。

新事件只写 `wall_head` / `wall_tail`。旧 JSONL 回放中的 `head` / `tail` 会在动作授权前
迁移为规范值；重放后产生的事件始终使用新值。非法来源或阶段不匹配仍会原子拒绝。

## 动作查询与未知规则

```python
from huian import HuianEnvironment, HuianGameState

game = HuianEnvironment()
game.reset(seed=42)  # 仅建立 144 张确定性牌墙，停在 READY。
# game.legal_actions() 此时抛 UnknownRuleError：开局流程仍待证据。
```

`legal_actions()` 仅在完整动作集合可确定时返回列表，未知时抛异常。
`action_report()` 显式返回 `known_actions` 与 `unresolved`，并有 `complete` 属性；这不是
供 AI 当作完整列表使用的替代接口。

对手打牌后的普通场景可以执行 PASS、吃／碰及已确认资格的点炮 `HU`；真实摸牌后的合法普通胡可以声明自摸 `HU`。声明后自动番数与结算仍明确报告为 UNKNOWN。
`step(action)` 可以执行独立已知动作。特殊状态、当前手中金牌等尚未明确的权限仍阻断动作。

玩家确认（2026-09-14）：牌墙到 16 张立即流局。头摸或已解决杠后的尾摸由 17 降到 16 时，
同一原子步骤进入 TERMINAL，原因 WALL_16、奖励 [0, 0]，庄家不变。最后摸到的实体牌保留
在手牌中（包括花牌），终局无后续动作。合法的 16 张局中导入也直接流局；少于 16 张的
非终局导入被拒绝。含补杠或待响应补杠的场景不套用上述零分流局：先保留响应与
胡声明，涉及补杠结算时返回UNKNOWN。补杠补花不会跨16张边界，也不会假定杠费为零。
Rules 已提供三金倒资格及“声明/继续”决策对象，也能从摸牌事件区分普通自摸和杠胡；
普通胡资格已经接入 `HU_DECLARED`。三金倒窗口现已部分确认并接入：开局持有全部3张可操作金、2→3金、以及此前点【过】后后续自己的摸牌仍保持恰好3金时可再次提示；PASS只关闭当前提示。补杠响应已接入，游金链的完整入口/升级/取消状态机仍未接入。
开局及中途补花已接入；开出的普通金实体归属已确认并实现：从可摸牌墙移出，保留在公开/预留区，最多只剩3张可操作金。仅“开金翻到花后继续重开”的完整实体流程仍待补证据。
终局导入可校验净分，但不表示环境重新验证了终局获胜资格或自动算出了该净分。

## 已观察结算的显式终局

`finalize_observed_outcome()` 只用于录像、结算页或 Vision 已经确认的结果。调用方必须
明确提供赢家、当前庄底、赢家番数和 `PINGHU` 或 `ZIMO`。已有 `HU_DECLARED` 时还会
核对赢家和自摸／点炮来源。Environment 只调用对应的已观察结算插件、写入零和奖励并记录
带原声明的 `END_HAND` 事件；它不会自行聚合番项、确定
抢金优先级或结算任何特殊胡。

```python
state, event = game.finalize_observed_outcome(
    winner=1, current_dealer_base=15, winner_fan=1, win_type="PINGHU"
)
# state.rewards == [-16, 16]
```

抢金终局、三金倒真实终局、游金链未知状态转换、抢杠胡/杠胡等仍会安全阻断，直到有单独证据与对应插件实现。已确认的三金倒重复提示窗口和游金4/8/16计分事实不再视为UNKNOWN。
抢杠声明停止并报告 `ROB_KONG_SCORING_UNKNOWN`；杠后尾摸胡报告
`GANG_HU_SCORING_UNKNOWN`；补杠尾摸不胡报告 `ADD_KONG_SCORING_UNKNOWN`。
这些分支保留事件和胡声明，既不使用普通simulation-only奖励，也不走普通已观察结算。

`RulesConfig(enable_added_kong=True)`默认开启补杠候选，False可禁用候选。PASS事件
记录原碰索引及第4张牌；回放先规范化该审计metadata，再授权与执行，防止重复搬牌。
## 抢杠的实验配置

```python
from huian import HuianRules, HuianRulesAdapter, RulesConfig, HuianEnvironment

rules = HuianRules(RulesConfig(experimental_no_rob_kong=True))
game = HuianEnvironment(HuianRulesAdapter(rules))
```

此开关只用于测试“假定该场景无抢杠”时明暗杠的实体牌转换和尾摸。默认 False 表示
明／暗杠抢杠范围 UNKNOWN，不能解释为“允许抢杠”。补杠专用窗口不依赖此实验开关。该假设不是惠安规则确认，每个事件都会记录
完整 RulesConfig。正式模拟成绩不能混入这个实验配置的对局。

## 演示与测试

在项目根目录用可用的 Python 运行：

```text
python -B -m huian.environment.demo
python -B -m unittest discover -s tests -v
```

演示从明确的局中 fixture 执行吃牌、弃牌、回滚；不保存文件、不发牌、不模拟完整游戏。
另在两个 legacy 目录各运行其 unittest 套件，以检查旧基线。

下一步补齐真实开金、特殊胡牌时序及补杠/抢杠/杠胡结算证据，再扩展完整真实规则循环。
