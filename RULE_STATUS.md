# Huian Two-Player Rules Status

## 2026-09-18 player-confirmed current-player qiangjin window

The following interaction rules are now CONFIRMED from the player's real-game clarification and are implemented in the current code:

- Qiangjin belongs only to the **current acting player** at the applicable node (opening after flower replacement/open-gold, and the corresponding current-player node after draw / flower / kong processing).
- If that player chooses **PASS / 放弃**, that qiangjin opportunity is closed for the whole turn. The opponent does **not** inherit the window, even if the opponent's hand would otherwise satisfy a qiangjin condition.
- After PASS, normal flow resumes for the same acting player: a 17-tile action node proceeds to discard; a 16-tile own node proceeds to the normal draw path.
- At any applicable current-player decision node, holding three or more gold tiles immediately offers Sanjindao first. The player may declare Sanjindao or choose PASS/continue; declining it does not end the hand and the hand may continue developing into ordinary Hu / Youjin-family outcomes. Qiangjin is not offered as the competing branch while the 3+ gold Sanjindao choice is active.
- This confirms **window ownership and PASS behavior only**. The exact qiangjin winning decomposition/eligibility, settlement multiplier/payment, terminal flow and next dealer remain UNKNOWN.
- The current helper `working_qiangjin_eligible()` is only an engineering gate for exercising the window. Its present "gold in hand and not in Youjin" condition is not itself a confirmed qiangjin hand-shape rule. Likewise, any current `QIANGJIN_MULTIPLIER` metadata must not be treated as settlement evidence.

Player confirmation also resolves the rob-kong scope for this target room:

- **ADD_KONG = 补杠 / 蓄杠 / 加杠**：已经碰出三张后，自己摸到第4张再升级成杠。它属于明杠的一种升级形态，也是目标房**唯一可以被抢杠**的杠。
- **MING_GANG = 大明杠**：对手打出一张，自己手里有三张同牌，直接杠成四张；**不能被抢杠**。
- **AN_GANG = 暗杠**：自己手里四张同牌直接暗杠；**不能被抢杠**。
- Rob-kong scoring, added-kong independent fees, flow-hand kong settlement and direct video evidence of the response UI remain unresolved.
- **点炮补成刻子不算暗刻番。** 玩家2026-09-18确认：如果胡牌张来自对手弃牌，而该牌只是把自己原有两张同牌补成三张，这一组不按自然暗刻计番。FanAggregator 对 `WinSource.DISCARD` 且胡牌张等于该刻子牌值时直接不给暗刻番；自摸形成的自然暗刻仍按现有普通1番/字牌2番规则计算。
- **碰牌番已确认。** 玩家2026-09-18确认：普通数牌（万/筒/条）碰出的明刻计0番；字牌（东南西北中发白）碰出的明刻计+1番。所有碰出来的明刻都是公开副露，均不能计入自然暗刻、双暗刻或三暗刻统计。FanAggregator 因此只为字牌PENG添加1番，数牌PENG不添加番项。
- **普通胡多拆法取最高总番。** 用户2026-09-18确认项目按此规则推进：特殊胡先判；若进入普通胡，则枚举全部合法普通胡拆分（含金牌万能替换的所有合法组合），每套独立计算完整番数，并选择总番最高的一套作为结算方案。门外已公开的吃/碰/杠副露固定，不参与重新拆分。若求解器明确提示拆分枚举被截断，则仍保持 UNKNOWN，不在不完整候选集上强行取最大值。
- **金牌按张计台，逐张累加。** 玩家2026-09-18确认：每张金牌本身计1台，2张金=2台、3张金=3台，依此累加；金作为万能牌去补顺子、刻子或将时，不因“万能用途”额外加台。金代凑成的刻子不算自然暗刻，因此不能计入双暗刻/三暗刻等暗刻类台数。该规则已进入当前 FanAggregator，并由回归覆盖。
- **花牌基础番按张线性累加，四花无额外叠加。** 玩家2026-09-18确认：每张花牌计1番，4张花=4番；即使凑齐春夏秋冬或梅兰竹菊一整组，也不因“四花成组”再额外加番。该规则现已进入 FanAggregator：四花组不再产生 `flower_groups` UNKNOWN；八花选择【过】后也按8个基础花番继续普通胡。

This file separates CONFIRMED / HIGH-CONFIDENCE / UNKNOWN rules.
Do not silently promote UNKNOWN rules.

## Implemented added-kong response contract — user implementation request

The current implementation request defines an added-kong-only response path. This is an explicit engineering contract, not new video proof of the mini-program's rob-kong interaction. The 66fe863f replay confirms a Peng upgraded to an added kong and that example's displayed fan; it does not show a rob-kong attempt.

- `ADD_KONG` is offered for an existing non-gold Peng plus its fourth tile in the declarer's hand. Gold cannot be added-konged.
- Declaration enters `ROB_KONG_WINDOW`. The original Peng and fourth hand tile remain unchanged; `pending_kong` is a logical reference, not another physical tile. Only this added-kong window offers `ROB_KONG_HU` when Rules establishes eligibility, or `PASS`.
- `PASS` commits the fourth tile once, forming `ADDED_GANG`, then requires a `wall_tail` draw through the existing flower replacement pipeline. A successful rob records winner/source and keeps the original Peng and tile accounting; it does not complete the kong or draw a replacement.
- `enable_added_kong=True` is the default. False disables added-kong candidates. Simulator `enable_rob_kong=False` remains the broad unsupported scope switch; setting it True does not enable Ming/An rob-kong.
- Kong fan table is now the **current adopted engineering rule**, subject to revision if stronger direct video evidence conflicts: 大明杠/MING_GANG 普通牌2番、字牌3番；补杠/蓄杠/加杠 ADD_KONG 按同一明杠表（普通牌2番、字牌3番）；暗杠/AN_GANG 普通牌3番、字牌4番。普通牌 ADD_KONG=2番有 66fe863f 真实录像直接支持；其余格来自惠安游戏内规则页并按用户 2026-09-18 指示先采用。2026-09-18 玩家进一步确认：**不存在独立杠费**，大明杠/暗杠/补杠都不会在杠成立时另外即时收分，流局也没有需要保留或返还的杠费；杠只通过既有杠番进入最终胡牌番数。仍 UNKNOWN 的杠类计分仅剩：抢杠胡结算 `ROB_KONG_SCORING_UNKNOWN`、杠上胡结算 `GANG_HU_SCORING_UNKNOWN`。

Remaining evidence gaps: actual-room added-kong (补/蓄/加杠) response/decline footage, independent kong fees, boundary settlement and all rob-kong/Gang-Hu scoring. Rob scope is no longer a gap: ADD_KONG is robbable; 大明杠/MING_GANG and 暗杠/AN_GANG are not. Implemented transitions and passing tests do not promote the remaining gaps to confirmed rules.

## Latest direct replay evidence — 66fe863f, 2026-09-15

[Source and frame-by-frame review](references/gameplay/2026-09-15/66fe863f_youjin100/README.md): room 206640, hand 5/8, gold M1, 单金不平胡, no trusteeship.
- Observed path: P1 Peng → fourth P1 → added kong; then Chi S789, discard S1 while retaining one gold, opponent plays, M7 appears, Youjin ×4 settles. This is one verified path, not a complete Youjin or rob-kong state machine.
- Winner is the non-dealer (own base5); opponent is 庄3/base20. Winner fan is gold1 + flower1 + triplet1 + kong2 = 5. Displayed winner value40 is `(own base5+fan5)×4`; actual +100/-100 is `(current dealer base20+fan5)×4`. The loser's 1 fan is not deducted.
- The sole kong was visibly formed by upgrading a P1 Peng; its displayed 2-fan contribution confirms this suited added-kong example. This does not confirm incremental kong fees, payments at declaration, rob-kong permissions, or flow-hand kong settlement.
- One gold can follow this Youjin path after Chi without discarding that gold. The reply/decline/cancellation branches remain unverified. Dealer-winner extra ×2 is now excluded by the 7bc12fa dealer Triple-You +608 (no extra factor).
Regression: `tests/fixtures/settlement_66fe863f.json`, `tests/test_66fe863f_evidence.py`.

## Direct replay evidence — b3892b34, 2026-09-15

[Source, frame timestamps and transcription](references/gameplay/2026-09-15/b3892b34_zimo68/README.md).
This is an in-game replay of room 745816, hand 8/8, with 单金不平胡 and no trusteeship.
- At 60/65 seconds, one gold S3 and two Chi melds are visible before/after the winning M5; all three suits are present. Ordinary self-draw therefore has no mandatory missing-suit gate in this target room.
- At 71–75 seconds, the dealer badge is 庄5, dealer base is 30, winner fan is gold 1 + flowers 2 + concealed triplet 1, and Zimo ×2 pays +68/-68: `(30 + 4) × 2 = 68`.
- This ordinary dealer self-draw has no extra dealer ×2, and the loser's displayed 4 fan is not subtracted. Combined with 7bc12fa dealer Triple-You +608, extra dealer ×2 is not applied to ordinary Zimo or to Triple-You.
- The visible natural S999 triplet supports the suited concealed-triplet 1-fan example; the loser's natural WWW supports the honor concealed-triplet 2-fan example. This is not a complete fan aggregation algorithm.
- 庄5/base30 is a directly observed pair of values, not proof of every dealer-base transition or any cap.
Regression: `tests/fixtures/settlement_b3892b34.json`, `tests/test_b3892b34_evidence.py`.

## Direct replay evidence — 7bc12fa, 2026-09-18

[Source and frame review](references/gameplay/2026-09-15/7bc12fa_video_evidence.md): in-game replay of room 673185, hand 6/8, gold M1 (一筒), 单金不平胡, trusteeship on, 2025-12-16 22:05:48. Duration 57.47s.
- Path: flower replacement; several PASS on opponent discards after tenpai; Chi; discard 一条 (waste bamboo, not gold) with Youjin badges; then Double-You splash; draw 八万 still badged; Triple-You splash; further PASS available; settlement Triple-You ×16 +608/-608.
- Winner 知止 shows **5庄**, gold 1 fan + flowers 2 fan. `(35 + 3) × 16 = 608`. Winner is the dealer; there is no extra dealer ×2 (that would be 1216).
- Entry does not require discarding gold. Chi then Youjin is allowed (same family as 66fe863f).
- This clip climbs Youjin → Double-You → Triple-You in order; no direct skip to Double/Triple. The Youjin-side player may PASS opponent discards while climbing.
- Do not equate the settlement label 5庄 with b3892b34's 庄5/base30. This hand's current dealer base in the formula is 35.
- Sanjindao UI flashed mid-hand; no Sanjindao settlement. Opponent Hu rights during the chain were not exercised on screen.

## Confirmed / very high confidence
- Full 144-tile set is used.
- Dealer starts with 17 tiles; non-dealer starts with 16.
- Flowers do not participate in normal meld composition; their fan is a separate component included before the Hu multiplier in verified ordinary settlements.
- Player confirmation (2026-09-14): unclaimed discard + PASS advances to the next player's head draw; at 16 wall tiles the hand draws with rewards [0, 0].
- Target room is fixed: 2 players, 8 hands, each player starts the match at 1000 points, 单金不平胡 checked (`single_gold_can_pinghu=False`), no trusteeship. Earlier unchecked screenshot records the option UI, not this final room choice.
- Opponent discard can offer Chi/Peng/Gang/Hu where legal; Rules must return all legal actions and AI chooses.
- In 2-player Huian, the sole opponent's discard may be Chi'd.
- Confirmed rule and system interaction (player confirmation, 2026-09-14): when one discard permits multiple Chi sequences, every legal sequence is a separate choice. The mini-program opens a Chi-option selection panel and the player selects the exact sequence; it does not auto-select and a generic Chi action must not silently choose one. Example: discard M5 with M3/M4, M4/M6 and M6/M7 available offers M3-M4-M5, M4-M5-M6 and M5-M6-M7.
- Confirmed/reconfirmed player interaction (2026-09-14): after Chi or Peng completes, that player immediately enters the discard phase and must discard one tile; there is no intervening normal draw.
- Player confirmation (2026-09-14): after a completed Ming-Gang, An-Gang, or Added-Gang, the declarer draws from the wall tail. That draw follows the normal draw/flower-processing pipeline; its provenance must be recorded as `wall_tail` rather than modeled as a separate complex replacement flow.
- Confirmed system interaction (player confirmation, 2026-09-15): flower replacement is dealt automatically by the mini-program and the interface has no obvious tile-by-tile dealing animation. Environment must model replacement as a system event rather than a player action. Vision/Recorder must infer it from the next stable state—hand count, flower count, wall remaining and opening-gold phase—not from animation presence. This observation rule does not change the confirmed wall-tail replacement source.
- Added kong after Peng is allowed.
- Current adopted kong fan table (2026-09-18; revise if later direct video conflicts): suited 大明杠=2, honor 大明杠=3; suited 补/蓄/加杠=2, honor 补/蓄/加杠=3; suited 暗杠=3, honor 暗杠=4. The suited added-kong=2 cell is directly confirmed by replay 66fe863f; the remaining cells are supported by the in-game Huian rule page and are operationally adopted by player instruction.
- Player confirmation (2026-09-14): a Hu by the kong declarer after the tail draw for any completed Ming-Gang, An-Gang, or Added-Gang is classified uniformly as Gang-Hu (杠胡). Rob-kong is a separate response path. Updated player confirmation (2026-09-18): Added-Gang/ADD_KONG (补杠=蓄杠=加杠, existing Peng + self-drawn fourth tile) is an exposed-kong upgrade and can be robbed. Big Ming-Gang/MING_GANG (opponent discard + three matching hand tiles) cannot be robbed; An-Gang/AN_GANG cannot be robbed. Actual-room response footage and rob-kong scoring remain incomplete.
- Gold cannot participate in Chi/Peng/Ming-Gang/An-Gang.
- If opponent discards the current gold tile, it cannot be Chi/Peng/Gang/Hu.
- Gold is a wildcard in allowed hand/win composition.
- A triplet completed using gold is not a natural concealed-triplet fan.
- Single-gold Pinghu is a player/room setting (player clarification 2026-09-13). It is usually disabled. Default `single_gold_can_pinghu=False` preserves the observed target-room behavior; enable only for a room explicitly allowing it. The generic page's allowance does not override a room's setting.
- Player confirmation (2026-09-14): in the target room, exactly one gold may complete a self-draw Hu when the standard structure is valid. The checked 单金不平胡 option blocks ordinary discard-win Pinghu; it does not block this self-draw.
- Player confirmation (2026-09-14): with exactly two gold tiles, Hu is allowed only by self-draw; the player cannot Hu on any opponent discard. This supersedes the older blanket statement that double gold could not Pinghu. The Rules API must carry the win source before this restriction can be implemented correctly.
- Player confirmation (2026-09-14): ordinary Hu evaluation and Youjin evaluation are separate branches. Passing or failing an ordinary structural Hu check must not silently decide Youjin eligibility.
- Player confirmation (2026-09-14): opening Qiangjin is checked after all opening flower replacement and opening gold are complete, before the first discard. A hand must already be a valid Hu after treating gold copies as wildcards, and holding three or more copies takes the Sanjindao branch first. Updated player confirmation (2026-09-18): the Qiangjin prompt at an applicable node belongs only to the current acting player; PASS closes the window for that turn and does not hand the opportunity to the opponent. The exact executable hand-shape predicate is still not fully encoded and remains a separate evidence task.
- **三金倒仅在“刚摸进第3张金”的瞬间出现。** 玩家2026-09-18结合回放确认：当手牌由2金变为3金时，当下提供【三金倒 / 过】；三金倒不是强制胡。若点【过】，该次三金倒机会永久关闭，本局后续即使仍持3金或再摸到第4金，也不会重新打开三金倒窗口。过后3/4金仍保留全部普通胡权利：满足普通4面子+1将结构时既可以自摸，也可以胡对手打出的炮牌；同时仍可发展游金/双游/三游。每张金仍按1番累计，3金=3番、4金=4番，金作万能不影响自身番数，金补出的刻子不算自然暗刻。三金倒仍是独立×3结果，三金游/三游统一为 `TRIPLE_YOU` ×16。三金倒实际结算底数、付款、终局账务和下局庄位仍UNKNOWN。
- Dealer win -> dealer stays.
- Draw -> dealer stays.
- Dealer loss -> other player becomes dealer.
- Match default is 8 hands. Player confirmation (2026-09-18): both players start at 1000 points. Each settled hand transfers its net result between the two players; after hand 8, the accumulated scores are the match result. Therefore the AI's primary objective is to maximize its own final score after 8 hands (equivalently, with equal starts and zero-sum transfers, maximize accumulated score delta / final score margin), not to maximize single-hand win count. Tie handling remains UNKNOWN.
- Player confirmation (2026-09-14): the target rules do not award complex combination fans such as 门清、碰碰胡、清一色、混一色 or similar pattern families. Such tile arrangements may still satisfy the standard Hu structure, but receive no special fan for those names.
- Confirmed in-scope Hu/settlement categories are Pinghu, Zimo, Sanjindao, Youjin, Double-You, Triple-You, Eight-Flower You (八花游), flower scoring, and repeat-dealer/base scoring. Confirmation of the category scope does not confirm every trigger, multiplier, stacking rule, or settlement formula; unresolved details below remain UNKNOWN.
- Player confirmation (2026-09-14): each flower contributes 1 fan as its base flower value. Complete-set bonuses, stacking, and the interaction with special flower outcomes remain separate questions.
- Direct replay `7bc12fa…mp4` (ingested 2026-09-18): target-room Youjin multipliers are Youjin ×4, Double-You ×8, and Triple-You/三金游 ×16. Dealer Triple-You settles +608/-608 with current dealer base 35 and winner fan 3 (gold 1 + two flowers 2): `(35 + 3) × 16 = 608`. Flower fan is inside the Hu multiplier. Extra Youjin-chain dealer ×2 is **not** applied on this dealer Triple-You (608, not 1216) and is not applied on ordinary dealer Zimo +68. Declaration-edge cases, cancellation and next dealer remain unresolved. See `references/gameplay/2026-09-15/7bc12fa_video_evidence.md`.
- **八花游触发已确认；倍率暂按项目规则×2。** 玩家确认：只要集齐全部8张花牌，即具备八花游资格，不要求普通胡结构，可直接作为特殊胡；也可选择【过】继续。PASS后8张花仍按1番/张，共8番进入普通牌局。2026-09-18 用户决定：鉴于八花游出现概率极低，项目实现中将八花游特殊胡**暂定为×2**；这一倍率属于项目人工设定，不标记为真实房间已验证规则。庄位仍按正常胜负流程处理；与其他特殊牌型并列/冲突时沿用特殊牌型通用处理框架。
- Confirmed opponent permissions during the Youjin chain (player confirmation, 2026-09-14): while one player is in Youjin, the opponent may Hu; while one player is in Double-You, the opponent may self-draw Hu; while one player is in Triple-You, the opponent may Hu only through a kong-replacement self-draw (杠上自摸胡 / 杠胡).

## High-confidence settlement evidence from real Huian screenshots
Room-settings evidence received 2026-09-13: [archived two-player creation page](references/room_settings/2026-09-13/README.md)
shows 惠安, 2 players, 8 hands, no trusteeship, and an **unchecked** 单金不平胡 option.
The room option's existence is directly observed. By its label, unchecked maps to
`single_gold_can_pinghu=True`, checked to False; this is a configuration interpretation,
not proof that a room was created or a discard win executed. Preserve the project
default False from player preference, and record the actual choice for each game.
No base/multiplier settings are visible; those unknowns remain unresolved.

Example A:
- current dealer base: 10
- winner fan components total: 12
- Zimo x2
- actual result: +44 / -44
- fits `(10 + 12) * 2 = 44`

Example B:
- current dealer: 庄2, base 15
- winner own base shown: 5
- winner fan components: Gold 1 + Flower 3 + Triplet 1 + Kong 2 = 7
- Youjin x4
- display shows 48 fan/value
- actual result: +88 / -88
- actual result fits `(current dealer base 15 + winner fan 7) * 4 = 88`
- displayed 48 fits `(winner own base 5 + 7) * 4 = 48`

Historical A/B hypothesis, now confirmed for the ordinary Pinghu/Zimo examples below:
`actual two-player net = (CURRENT DEALER BASE + WINNER FAN) * WIN-TYPE MULTIPLIER`
Winner +X, loser -X.
Ordinary examples no longer await a third settlement. Automatic fan aggregation and special-outcome settlement still require their own evidence.

## 2026-09-13 WGC capture review — additional real settlements

Archived frames and a full transcription are in
[`references/capture_review/2026-09-13`](references/capture_review/2026-09-13/README.md).

- Pinghu, winner base 10 + concealed triplet 1 = **+11/-11**.
- Pinghu, current dealer base 15 + winner flower 1 = **+16/-16**, although the winner's own displayed base is 5. This confirms the verified formula uses the **current dealer base**.
- Zimo x2, current dealer/winner base 10 + gold 1 + flowers 5 + triplet 1 + kong 2 = **+38/-38**.
- A flow settlement is explicitly **0/0** despite displayed hand fan values.

For observed Pinghu and Zimo cases, the formula
`(current dealer base + winner fan) × win-type multiplier` is now supported by
multiple direct recordings, including the dealer Zimo +68/-68 above with no extra dealer factor. The direct non-dealer Youjin +100 and the ingested dealer Triple-You +608 are separate special examples that use the same formula; 抢金、三金倒 and complete special-outcome flows remain unresolved. Independent kong fees are explicitly confirmed absent.
## Dealer base — player confirmation and observed display values

Player confirmation (2026-09-15), verbatim: “坐庄底分5分，连庄+5”. The +5 increment per repeat is confirmed. Preserve the stated sitting-dealer base of 5 as player feedback; its exact relationship to the observed dealer badge/displayed base must be reconciled against `a562bd213645d8d998e47bf62bdb45de.mp4`, which has not yet been reviewed. Do not overwrite the directly observed values below or infer a cap.
Observed:
- non-dealer: 5 base
- dealer: 10 base
- 庄2: 15 base
- 庄3: 20 base (direct 66fe863f settlement)
- 庄5: 30 base (direct b3892b34 settlement)
- current dealer base 35 (direct 7bc12fa Triple-You +608; winner badge 5庄, winner is dealer)
Each repeat adds +5 according to the player confirmation. The first dealer-label/display mapping and any cap remain UNKNOWN. Do not merge 7bc12fa's 5庄/base35 with b3892b34's 庄5/base30; the badge strings look similar and the bases differ.

## Flower scoring
Confirmed by player feedback, with supporting real screenshot evidence:
- each flower has a base value of 1 fan

Additional real screenshot evidence:
- three ordinary flowers can show 3 fan
- six flowers have shown 10 fan

A strong working explanation is:
- each ungrouped flower: 1 fan
- complete 春夏秋冬 set: likely 8 total fan for those four
- complete 梅兰竹菊 set: likely 8 total fan for those four
- all eight flowers: likely 16 total fan
This explains six flowers containing one complete set: 8 + 2 = 10.

External sources conflict (some say a four-flower set is 6). Real Huian screenshots take priority.

## Gold / triplet / kong working values
External Quanzhou-family sources and prior rules are broadly consistent with:
- gold: 1 fan each
- normal concealed triplet: 1
- honor concealed triplet: 2
- normal exposed kong: 2
- honor exposed kong: 3
- normal concealed kong: 3
- honor concealed kong: 4
Direct b3892b34 evidence supports gold 1 and the natural S999/WWW concealed-triplet examples at 1/2 fan. The direct 66fe863f sequence adds a suited P1 added-kong example contributing 2 fan. Uncovered aggregation edge cases, other kong categories and independent kong fees still need their own evidence.

## Youjin chain
Confirmed from 66fe863f and 7bc12fa (target room):
- Ordinary Hu and Youjin are separate branches.
- Entry does not require discarding gold. After tenpai, discarding a waste tile can enter Youjin (7bc12fa: 一条 or 二条 while gold remains 一筒; 66fe863f: discard S1, retain gold M1).
- Chi then Youjin is allowed.
- Upgrades are sequential in the ingested clip: Youjin → Double-You → Triple-You. Double-You / Triple-You are not “further gold actions”; gold stayed in hand while waste tiles were discarded and 八万 was drawn.
- Multipliers: 4 / 8 / 16. Dealer Triple-You uses the same formula with no extra dealer ×2.
- The Youjin-side player may PASS opponent discards while climbing the chain.

Still UNKNOWN programmatically:
- exact trigger predicate for every edge hand (whether gold must complete the pair, all wait sets)
- whether any room path can skip Youjin and enter Double-You directly (not seen in 7bc12fa)
- which actions cancel the state in every case
- opponent Hu sources during Youjin / Double-You / Triple-You beyond the 2026-09-14 oral permissions (this clip does not show the opponent winning)

The 66fe863f replay remains one Youjin ×4 path after Chi. 7bc12fa adds the climb to Triple-You ×16 and dealer-winner settlement +608.

## Multipliers
Real Huian screenshot confirms:
- Zimo x2 in at least one room
- Youjin x4 in at least one room

External rules suggest room-configurable groups may exist, for example:
- Youjin x3 -> Double-You x6 -> Triple-You x9 or x12 depending on ruleset
- Youjin x4 -> Double-You x8 -> Triple-You x12
These historical external alternatives must not override the now-confirmed target-room 4/8/16 chain.

The user-supplied 惠安 tab lists Youjin/Double/Triple as **4/8/16**, not 4/8/12.
The 2026-09-15 player confirmation now applies 4/8/16 to the target two-player
room. Flower fan is included before the Hu multiplier in the +608 recording and ordinary direct recordings. Extra Youjin-chain dealer ×2 is withdrawn from the default formula: ordinary dealer Zimo +68 and dealer Triple-You +608 both omit it. The page's outer ×3 must not be applied to the verified two-player calculation.

## Still important UNKNOWN questions
1. 抢金 remaining gaps: the exact effective Hu decomposition/options and settlement/dealer result. Current-player ownership and PASS-does-not-handoff are resolved; do not re-open them as UNKNOWN.
2. Actual-room rob-kong evidence: only Added-Gang/ADD_KONG (补杠=蓄杠=加杠) can be robbed; 大明杠/MING_GANG and 暗杠/AN_GANG cannot. Player confirmation also resolves that there is no independent kong fee and no special kong-fee accounting at flow draw. What remains UNKNOWN is the real response UI/decline footage and rob-kong/Gang-Hu scoring.
3. Sanjindao remaining gaps: non-flower base, payment, terminal settlement accounting and next dealer. Eligibility at three or more gold, immediate offer, declare/continue choice and ×3 multiplier are confirmed; declining Sanjindao simply resumes play and may lead to other hand types. Timing is no longer an UNKNOWN.
4. 三游 / 三金游 remaining gaps: these names mean the same `TRIPLE_YOU` state, distinct from 三金倒. Youjin 4/8/16 and `(current dealer base + winner fan) × Hu multiplier` are confirmed by the ingested 7bc12fa dealer Triple-You +608. Sequential climb Youjin→Double→Triple and self-PASS while climbing are confirmed in that clip. Exact predicate for every upgrade discard, cancellation, opponent Hu windows on video, payer UI and next-dealer result remain UNKNOWN.
5. Gang-Hu remaining gaps: multiplier/fan, stacking, settlement, and any room option. Its classification after all three completed kong types is confirmed.
6. Exact Youjin / Double-You / Triple-You triggers and the remaining permission windows not resolved by the confirmed opponent-rights matrix.
7. Remaining room multipliers outside ordinary Pinghu/Zimo 1/2, Sanjindao ×3 and Youjin 4/8/16. Extra Youjin-chain dealer ×2 is not used in ingested dealer Zimo +68 or dealer Triple-You +608; do not implement it until a new settlement shows it.
8. Exact open-gold procedure when a flower is revealed. External info says the flower counts for dealer, dealer replaces it, then gold is reopened; needs Huian confirmation.
9. Exact Tianhu timing relative to flower replacement/open-gold.
10. Exact Tianting definition.
11. Resolved 2026-09-14: all-PASS advances to the next player's draw.
12. 8-hand match tie handling.
13. Ordinary settlement is supported by multiple recordings; remaining work is automatic fan aggregation, unobserved special outcomes and dealer-base transition/cap rules.

## External web review — 2026-09-13 (not rule confirmation)

See [source register and comparison](references/HUIAN_WEB_RULES_2026-09-13.md).
No target-room rule was promoted to CONFIRMED in this review.

- A [2022 entry tutorial](https://jingyan.baidu.com/article/3ea51489a942cf13e71bba11.html) identifies a historical 开心泉州麻将 mini-program rules menu. It does not establish the current 惠安 two-player rules or operator. The linked rule image was not successfully read.
- A [different product's 泉州 page](https://www.xinyueyouxi.com/game/219-22?doc-innerlink-%E4%BF%A1%E5%BF%B5=&region=) provides room-multiplier and scoring comparison leads. Its values must not be imported as 开心惠安 defaults. See the source register for applicability and conflicts.
- Current dealer-base observations, the A/B settlement hypothesis and all existing confirmed rules remain unchanged. No third target-room settlement was found.

Additional UNKNOWN questions exposed by the comparison:
11. Whether a natural exposed suited triplet scores fan, and the exact honor Peng value in the target room.
12. Whether added-kong fan is an incremental bonus or a total meld value.
13. 八花游：真实触发规则已确认——集齐8张花即可直接特殊胡，不要求普通牌型；可选择【过】，过后8花按1番/张计入普通胡，共8番。特殊胡倍率在真实房间仍缺直接结算证据；项目当前人工暂定×2，后续若有真实结算图则以真实证据覆盖。庄位按正常流程。

Before adopting new web claims, verify the mini-program identity, 惠安 two-player selection, room options and current in-game rules. General 泉州 rules and another provider's official page are lower-priority external evidence for this project.

## User-supplied in-game pages — 2026-09-13

Archived five originals, checksums, transcription and conflict decisions in
[the screenshot review](references/ingame_rules/2026-09-13/README.md).
This is a new in-game source; the earlier web search result remains a historical
record of what could be found publicly at that time.

Scope: 惠安 tab visibly selected, but no two-player options/version shown. The
text refers to four players during flower replacement and includes outer ×3
settlement factors. Treat page wording as observed, not automatically as a
complete executable two-player ruleset. Existing real-game evidence takes priority.

Newly documented page statements:
- Ordinary winning structure: five groups and one pair.
- Flower replacements draw from the tail; flowers drawn during replacement wait
  until that round of four-player replacement is over; subsequent rounds start
  with dealer. This page alone did not establish two-player scheduling; later player confirmation established the dealer→opponent round-based replacement flow (see the evidence matrix).
- Opening uses two dice and counts from the wall end after the stated dealer
  replacement point; flowers require replacement/reopening until non-flower.
  Exact indexing, ownership and physical accounting remain unresolved.
- Sanjindao text covers starting hands OR three golds obtained before a draw;
  it does not specify all declaration/continuation windows.
- Youjin → Double → Triple chronology and opponent win restrictions are described;
  see the transcription. Direct double entry, cancellation and action permissions
  are not fully specified. Do not reduce double entry to merely drawing gold.
- The page lists honor Peng 1, normal/honor concealed triplets 1/2, normal/honor
  exposed kongs 2/3, concealed kongs 3/4, each gold/flower 1, each flower set 8,
  all eight flowers 16. These now have in-game textual support; flower stacking,
  added-kong fan, decomposition edges and two-player applicability remain pending.

Conflicts and preserved decisions:
- C1, clarified by player feedback: single-gold Pinghu is configurable and is
  disabled in the target room. Generic page text and the earlier disabled gameplay
  setting can differ. Runtime exposes `single_gold_can_pinghu` with default False.
  Exactly two gold tiles are self-draw-only and cannot Hu on an opponent discard;
  this newer confirmation replaces the older blanket double-gold prohibition.
- C2, resolved by 2026-09-15 player confirmation: the target two-player room uses
  Youjin/Double/Triple multipliers 4/8/16. The external 4/8/12 chain does not apply.
- C3: outer ×3 and non-winner fan adjustment text versus A/B two-player net
  evidence. Do not reinstate legacy subtraction or add the page's outer ×3 to
  two-player results. Extra Youjin-chain dealer ×2 is excluded by ordinary dealer Zimo +68 and by dealer Triple-You +608. The ingested +608 Triple-You confirms flowers are included in
  winner fan before ×16. Remaining special-outcome flows (抢金, 三金倒, 八花游, rob-kong fees) still need their own footage.

Still missing after the 2026-09-18 clarification: real 补杠/蓄杠/加杠 (ADD_KONG) rob-kong response footage/scoring and Gang-Hu scoring,
Tianhu/Tianting definitions, extended dealer base/cap and match ties. A listed
multiplier does not establish a win type's eligibility or declaration timing.
