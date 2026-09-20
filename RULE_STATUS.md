# Huian Two-Player Rules Status

## 2026-09-20 Youjin own-turn flowers / concealed Kong / added Kong confirmed

Latest player confirmation extends the established Youjin/Double-You own progression turn without changing the non-Kong path:

- **No Kong selected:** behavior is unchanged. After the opponent misses and discards, the Youjin player takes the existing one-card progression draw; if a free Jin exists, upgrade remains optional; otherwise the current stage settles as before.
- **Flowers do not interrupt Youjin.** If the Youjin player's progression draw is a flower, normal automatic flower replacement continues from the wall tail, including repeated flower replacements, until a non-flower effective draw is obtained. The Youjin stage remains active throughout.
- **Concealed Kong is allowed while Youjin is active.** If the completed own draw/replacement leaves four identical non-Jin tiles, the player may declare AN_GANG; the Kong completes normally and the replacement tile is drawn from the wall tail.
- **Added Kong is allowed while Youjin is active.** An existing PENG may be upgraded when the player draws the fourth tile. Existing confirmed rob scope remains unchanged: ADD_KONG keeps its rob-Kong response window; AN_GANG is not robbable.
- **Kong-tail Jin / freed Jin:** if the tail draw creates a discardable Jin, the player may discard Jin and upgrade single→double or double→triple.
- **Kong-tail ordinary tile:** when no ordinary Hu/special-settlement/upgrade is selected, the player must discard one non-Jin tile. The current Youjin stage is preserved and play returns to the opponent's one-draw response window; the discard is a Youjin-chain discard and opens no ordinary Chi/Peng/Gang/discard-Hu claim window.
- **Kong-tail tile that genuinely completes an ordinary Hu:** the player may choose ordinary self-draw Hu, or choose to settle the current Youjin stage instead. Ordinary Hu eligibility must have a legal decomposition beyond the trivial "roaming Jin + just-drawn tail tile as the pair"; otherwise every Kong-tail tile would be falsely treated as an ordinary Hu.
- **Kong fan remains additive** in any later settlement; there is still no independent immediate Kong fee.
- The ordinary Gang-Hu scoring formula remains `GANG_HU_SCORING_UNKNOWN`. Allowing the Hu action does not invent its multiplier/stacking.

Implementation uses `YOUJIN_KONG_CHOICE` and `YOUJIN_KONG_AFTER_DRAW`; declining the Kong explicitly returns to the pre-existing progression logic.

## 2026-09-20 Youjin / Double-You / Triple-You progression confirmed

Player confirmation now closes the normal sequential progression after an established Youjin stage:

1. **Every established stage gives the opponent exactly one self-draw opportunity.**
   - Youjin, Double-You and Triple-You all use the same one-draw interception window.
   - If the opponent self-draws, the Youjin chain is intercepted.
   - If the opponent does not self-draw, the opponent **must discard one tile**; that special response discard enters the river but opens no ordinary claim window.

2. **After a missed opponent response, single Youjin / Double-You gives the Youjin player one draw.**
   - If the new tile is the natural tile that replaces a wildcard gold already completing a meld, that wildcard gold becomes free.
   - If the new tile is itself gold, it directly creates a new free gold.
   - The structural condition is therefore not a hard-coded tile list: after the draw, one gold must be discardable while the remaining concealed hand still has the confirmed "all remaining melds + one roaming gold" Youjin-ready structure.

3. **Upgrade is optional.**
   - Single Youjin + free gold: player may discard one gold to enter Double-You, or decline and settle current Youjin ×4.
   - Double-You + free gold: player may discard one gold to enter Triple-You, or decline and settle current Double-You ×8.
   - If the Youjin player's extra draw does not create a free gold, the current stage settles automatically.

4. **Triple-You has no further upgrade draw.**
   - Triple-You gives the opponent its one self-draw opportunity.
   - If the opponent does not Hu, Triple-You settles immediately at ×16.

5. **Settlement formula remains the directly confirmed target-room formula:**
   `(current dealer base + winner fan) × stage multiplier`, with ×4 / ×8 / ×16 and no extra dealer multiplier.

The Environment now enforces the corrected response sequence: opponent DRAW → self-Hu if available, otherwise mandatory DISCARD → only then return to the Youjin player's continuation draw (single/double) or current-stage settlement (triple). Response discards enter the river but do not open an ordinary claim window. A dedicated `finalize_youjin_outcome()` applies the confirmed formula once audited dealer-base/fan inputs are provided.

**2026-09-20 response-discard correction (latest player confirmation):** the earlier interpretation that a missed response draw remains in hand is superseded. Correct target-room behavior is: after the opponent's one response draw, if they do not Hu, they **must discard one tile**. The hand therefore returns to its normal concealed size before the Youjin chain continues.

- The mandatory response discard is a special-chain discard: it is recorded in the river for physical accounting, but it does **not** open ordinary Chi/Peng/Gang/discard-Hu responses.
- Single/Double-You: after that discard, control returns to the Youjin player for the confirmed one-card progression draw.
- Triple-You: after that discard, the current Triple-You settles at ×16.
- The prior 18/19-tile retained-response model, `youjin_response_tiles`, subset Hu solver, and `youjin_response_extra_tile_scoring` blocker are retired.
- If the opponent's response draw itself is a legal self-Hu, **HU is optional**: the responder may choose Hu, or deliberately decline it and discard one tile instead. Choosing the discard continues the Youjin chain exactly like any other missed response.

External Quanzhou/Xiamen rules broadly support the same single→double→triple structure, "natural tile frees gold" logic and optional upgrade behavior, but public sources conflict on Triple-You response and scoring. They are retained only as low-priority cross-checks at `references/gameplay/2026-09-20/quanzhou_youjin_external_crosscheck.md`; target Huian two-player evidence remains authoritative.


## 2026-09-20 single-Youjin Environment entry/response window

The original single-Youjin entry implementation remains valid, but its old "stop after opponent miss" boundary has now been superseded by the confirmed progression section above:

- `youjin_entry_discards()` still exposes optional YOUJIN beside the same ordinary DISCARD.
- Choosing ordinary discard declines only the current Youjin offer and does not lock later progression.
- Choosing YOUJIN still discards the entry tile, establishes single Youjin, skips the ordinary discard-claim window and gives the opponent one self-draw response.
- After an opponent miss, Environment now continues into the confirmed Youjin-player draw / optional upgrade / current-stage settlement flow instead of stopping at the retired `youjin_stage_success_resolution` unknown.
- If the opponent can self-Hu in that response window, Hu is optional: the player may decline Hu and discard one tile to continue the Youjin chain.

## 2026-09-20 single-Youjin structural eligibility confirmed

Player clarification closes the core **single-Youjin hand-shape predicate**:

- After the intended entry discard, the concealed hand is a Youjin-ready shape when **exactly one gold can be reserved as the roaming singleton** and all other concealed tiles already form every remaining required meld.
- Any additional gold tiles are still ordinary wildcards inside those melds. The roaming gold is the **extra** gold left after the meld structure is complete; it is not determined by total gold count.
- In the ~01:06 example, three golds are visible: two are consumed as wildcards to complete the meld structure, while the third is the extra roaming gold. That is why the game offers single Youjin.
- Equivalently, after entry the next ordinary drawn tile can pair with the reserved roaming gold to complete the ordinary Hu structure.
- The rule works at the structural level and is not “three gold = Youjin”. A hand with a different gold count can qualify if it has the same complete-melds-plus-one-roaming-gold shape.

Implementation: `HuianRules.is_youjin_ready_hand()` checks the post-discard structure and `youjin_entry_discards()` enumerates which current discards create it. These functions only expose eligibility; they do not auto-declare Youjin or guess Double-/Triple-You upgrades.

## 2026-09-20 match_evidence_002 Youjin-offer / Double-You path clarification

Target-room replay + player clarification now adds a concrete mid-hand path:

- Around **01:06**, the player already has a visible **Youjin option** while holding three playable gold tiles. Two gold tiles are being used as the pair/wildcards to complete the current structure involving S3/S4 and M5/M5/M6.
- Selecting the Youjin option at that moment would discard M9 and enter **single Youjin**.
- The player instead **declines the Youjin option**, continues normal play, and discards M9 without entering Youjin.
- Later the player **Chi claims S2**, then discards one gold tile and enters **Double-You**.
- Therefore a visible single-Youjin offer is **optional**, not an automatic state transition; declining it does **not** permanently lock the hand out of later Youjin-family progression.
- This is direct evidence that later Double-You can be reached after an earlier declined single-Youjin opportunity. It does not yet prove that every Chi+discard-gold pattern is a universal Double-You trigger.

Implementation consequence: `youjin_offer_rule()` records an optional offer whose decline keeps ordinary play alive and does not set a permanent Youjin lockout. Exact universal stage-entry/upgrade predicates remain evidence-gated.

## 2026-09-20 Youjin-family opponent response correction

Player clarification from the target Huian two-player room now confirms a common opponent interception rule for all three established Youjin stages:

- **Youjin / Double-You / Triple-You each give the opponent exactly one draw opportunity to self-draw Hu.**
- If the opponent self-draws on that opportunity, the opponent wins and the pending Youjin stage is intercepted.
- If the opponent does not self-draw Hu on that opportunity, the current Youjin stage succeeds.
- This supersedes the older working note that Triple-You / 三游 / 三金游 could only be intercepted by kong-replacement self-draw.
- This correction does **not** close the remaining timing gap: the exact point at which a successful stage settles versus remains eligible for a further upgrade is still UNKNOWN and must not be inferred.

The response rule is now exposed by `youjin_opponent_response_rule()`; stage entry/upgrade continues to be explicit and evidence-gated rather than inferred from gold count.

## 2026-09-19 match_evidence_001 complete eight-hand replay

A complete anonymized target-room match (`match_evidence_001`, 惠安2人 / 单金不平胡 / 无托管) was reviewed from eight replay videos covering hand 1/8 through 8/8. Both players start at 1000; the final ledger is **1113 / 887**. Source hashes and the hand-by-hand table are archived at `references/gameplay/2026-09-19/match_evidence_001_full_8hand/README.md`.

Direct conclusions:

- **First sitting dealer current settlement base = 10.** The non-dealer own displayed base is 5. The earlier player wording “坐庄底分5分，连庄+5” is now reconciled with the UI: becoming dealer adds the dealer +5 on top of the ordinary 5-base display, so the first dealer settlement base is 10, not 5.
- **Repeat dealer adds +5 each hand, with no cap while the same dealer keeps the seat.** This match directly shows 10 → 15 → 20 → 25; older direct target evidence reaches 30/35. Player confirmation 2026-09-19 closes the remaining boundary: if the same dealer continues through later hands, the sequence keeps rising by +5 (40, 45, ... as applicable) until the fixed 8-hand match ends. Once the dealer loses, that chain ends and the new dealer resets to 10.
- **All 8 hands satisfy the same net formula:** `(current dealer settlement base + winner fan) × Hu-method multiplier`. The loser fan is not subtracted.
- **Dealer Youjin has no extra dealer ×2.** Hand 5 is a dealer Youjin with gold2 + flowers2 = 4 fan and settles exactly `(15+4)×4 = 76`, not 152. Together with the earlier dealer Triple-You +608, this closes the old extra-dealer-multiplier hypothesis for the target room.
- **Simple Youjin can coexist with two gold tiles.** Hand 5 ends as `游金×4` while the settlement explicitly lists `金牌2番`; both golds count +1 fan. Therefore Youjin/Double/Triple stage is not the same thing as current gold-tile count.
- **Ordinary self-draw with two gold is directly reconfirmed.** Hand 1: gold2 + flower1, `(10+3)×2=26`.
- **Suited concealed kong = 3 fan is directly confirmed.** Hand 6 shows the fourth suited tile being drawn into three concealed copies, a concealed-kong declaration, and settlement `杠牌3番`. This upgrades that kong-table cell from rule-page-only evidence to target-room CONFIRMED.

Observed hand formulas:
1. Zimo: `(10+3)×2=26`
2. Youjin: `(15+2)×4=68`
3. Zimo: `(10+1)×2=22`
4. Zimo: `(10+2)×2=24`
5. Dealer Youjin: `(15+4)×4=76`
6. Pinghu: `(20+5)×1=25`
7. Pinghu: `(25+3)×1=28`
8. Zimo: `(10+8)×2=36`

## 2026-09-19 special-multiplier evidence normalization

A re-review of the archived Huian two-player replay evidence separates **direct target-room settlements** from **in-game rule-page multipliers**:

- **Youjin ×4 — CONFIRMED by target two-player settlement.** Replay `66fe863f` settles `(current dealer base 20 + winner fan 5) × 4 = 100`.
- **Double-You ×8 — CONFIRMED by direct target-room settlement.** match_evidence_002 ends at 双游×8 with dealer base30, gold2 fan + flower1 fan = winner fan3, and settles exactly `(30+3)×8=264` (+264/-264). This also confirms no extra dealer ×2 on Double-You.
- **Triple-You / 三游 ×16 — CONFIRMED by target two-player settlement.** The archived +608 hand settles `(current dealer base 35 + winner fan 3) × 16 = 608`.
- **Sanjindao ×3 — confirmed as the adopted target-room multiplier from player confirmation plus the in-game page, but its direct settlement/payment/dealer flow is still unresolved.** Multiplier evidence and executable settlement readiness remain separate.
- **Rob-Kong Hu ×2 — CONFIRMED multiplier.** Player confirmation establishes that 抢杠胡 uses the same Hu multiplier as ordinary self-draw, therefore ×2; the Huian in-game rules page independently lists 抢杠 ×2. `ROB_KONG_SCORING_UNKNOWN` is narrowed to the remaining payment/dealer-continuation and settlement-flow details, so automatic settlement remains disabled until those details are closed.
- **Eight-Flower You:** collecting all eight flowers and the DECLARE/PASS window are confirmed; PASS keeps 8 ordinary flower fan. Project working rule updated 2026-09-20: DECLARE uses the in-game “八花齐16番” as a **fixed special 16 fan**, applies no extra Hu multiplier (×1), and does not stack the ordinary +8 flower fan or other additive fan. This remains WORKING until a real target-room Eight-Flower terminal settlement is captured.
- **Qiangjin and Gang-Hu multipliers remain UNKNOWN.** No archived target-room settlement or sufficiently scoped in-game multiplier rule closes those branches.
- The in-game page also lists **Tianhu ×4** and **Tianting ×4**, but current two-player target-room enablement/trigger semantics are not confirmed, so they are evidence leads only and are not enabled as executable special outcomes.
- The two ~57.47s Triple-You evidence records (`21d61237...` and `7bc12fa...`) are treated as likely duplicate representations of the same hand unless future source hashing proves otherwise; they must not be counted as two independent settlement samples.

This normalization changes evidence labels, not the already observed numerical outcomes. Special branches with incomplete payment/dealer rules continue to stop safely rather than infer a final score.

## 2026-09-18 player-confirmed current-player qiangjin window

The following interaction rules are now CONFIRMED from the player's real-game clarification and are implemented in the current code:

- Qiangjin belongs only to the **current acting player** at the applicable node (opening after flower replacement/open-gold, and the corresponding current-player node after draw / flower / kong processing).
- If that player chooses **PASS / 放弃**, that qiangjin opportunity is closed for the whole turn. The opponent does **not** inherit the window, even if the opponent's hand would otherwise satisfy a qiangjin condition.
- After PASS, normal flow resumes for the same acting player: a 17-tile action node proceeds to discard; a 16-tile own node proceeds to the normal draw path.
- Sanjindao is an optional current-player choice, not a once-per-hand lockout. Confirmed entry evidence includes **(a)** the opening check after opening flower replacement/open-gold is complete when the current actor already holds 3+ gold; **(b)** mid-hand when a valid draw changes the player from 2 gold to exactly 3; and **(c)** after a prior PASS, a later own draw while the player still holds exactly 3 gold can offer Sanjindao again. Sanjindao outranks Qiangjin at an eligible node. PASS closes only that current prompt; it does not permanently disable later Sanjindao, ordinary Hu, or Youjin-family play. Current evidence does not yet generalize the later-draw recheck to four gold.
- This confirms **window ownership and PASS behavior only**. The exact qiangjin winning decomposition/eligibility, settlement multiplier/payment, terminal flow and next dealer remain UNKNOWN.
- The current helper `working_qiangjin_eligible()` is only an engineering gate for exercising the window. Its present "gold in hand and not in Youjin" condition is not itself a confirmed qiangjin hand-shape rule. Likewise, any current `QIANGJIN_MULTIPLIER` metadata must not be treated as settlement evidence.

Player confirmation also resolves the rob-kong scope for this target room:

- **ADD_KONG = 补杠 / 蓄杠 / 加杠**：已经碰出三张后，自己摸到第4张再升级成杠。它属于明杠的一种升级形态，也是目标房**唯一可以被抢杠**的杠。
- **MING_GANG = 大明杠**：对手打出一张，自己手里有三张同牌，直接杠成四张；**不能被抢杠**。
- **AN_GANG = 暗杠**：自己手里四张同牌直接暗杠；**不能被抢杠**。
- Rob-kong multiplier is now confirmed as ×2, the same as ordinary self-draw. Remaining rob-kong gaps are payment/dealer continuation, full terminal settlement flow, and direct video evidence of the response UI.
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
- Kong fan table is now the **current adopted engineering rule**, subject to revision if stronger direct video evidence conflicts: 大明杠/MING_GANG 普通牌2番、字牌3番；补杠/蓄杠/加杠 ADD_KONG 按同一明杠表（普通牌2番、字牌3番）；暗杠/AN_GANG 普通牌3番、字牌4番。普通牌 ADD_KONG=2番有 66fe863f 真实录像直接支持；其余格来自惠安游戏内规则页并按用户 2026-09-18 指示先采用。2026-09-18 玩家进一步确认：**不存在独立杠费**，大明杠/暗杠/补杠都不会在杠成立时另外即时收分，流局也没有需要保留或返还的杠费；杠只通过既有杠番进入最终胡牌番数。仍 UNKNOWN 的杠类计分仅剩：抢杠胡的付款/庄位/终局流程 `ROB_KONG_SCORING_UNKNOWN`（倍率×2已确认）、杠上胡结算 `GANG_HU_SCORING_UNKNOWN`。

Remaining evidence gaps: actual-room added-kong (补/蓄/加杠) response/decline footage, independent kong fees, boundary settlement and all rob-kong/Gang-Hu scoring. Rob scope is no longer a gap: ADD_KONG is robbable; 大明杠/MING_GANG and 暗杠/AN_GANG are not. Implemented transitions and passing tests do not promote the remaining gaps to confirmed rules.

## Latest direct replay evidence — 66fe863f, 2026-09-15

[Source and frame-by-frame review](references/gameplay/2026-09-15/66fe863f_youjin100/README.md): anonymized replay `evidence_66fe863f`, hand 5/8, gold M1, 单金不平胡, no trusteeship.
- Observed path: P1 Peng → fourth P1 → added kong; then Chi S789, discard S1 while retaining one gold, opponent plays, M7 appears, Youjin ×4 settles. This is one verified path, not a complete Youjin or rob-kong state machine.
- Winner is the non-dealer (own base5); opponent is 庄3/base20. Winner fan is gold1 + flower1 + triplet1 + kong2 = 5. Displayed winner value40 is `(own base5+fan5)×4`; actual +100/-100 is `(current dealer base20+fan5)×4`. The loser's 1 fan is not deducted.
- The sole kong was visibly formed by upgrading a P1 Peng; its displayed 2-fan contribution confirms this suited added-kong example. This does not confirm incremental kong fees, payments at declaration, rob-kong permissions, or flow-hand kong settlement.
- One gold can follow this Youjin path after Chi without discarding that gold. The reply/decline/cancellation branches remain unverified. Dealer-winner extra ×2 is now excluded by the 7bc12fa dealer Triple-You +608 (no extra factor).
Regression: `tests/fixtures/settlement_66fe863f.json`, `tests/test_66fe863f_evidence.py`.

## Direct replay evidence — b3892b34, 2026-09-15

[Source, frame timestamps and transcription](references/gameplay/2026-09-15/b3892b34_zimo68/README.md).
This is an anonymized in-game replay `evidence_b3892b34`, hand 8/8, with 单金不平胡 and no trusteeship.
- At 60/65 seconds, one gold S3 and two Chi melds are visible before/after the winning M5; all three suits are present. Ordinary self-draw therefore has no mandatory missing-suit gate in this target room.
- At 71–75 seconds, the dealer badge is 庄5, dealer base is 30, winner fan is gold 1 + flowers 2 + concealed triplet 1, and Zimo ×2 pays +68/-68: `(30 + 4) × 2 = 68`.
- This ordinary dealer self-draw has no extra dealer ×2, and the loser's displayed 4 fan is not subtracted. Combined with 7bc12fa dealer Triple-You +608, extra dealer ×2 is not applied to ordinary Zimo or to Triple-You.
- The visible natural S999 triplet supports the suited concealed-triplet 1-fan example; the loser's natural WWW supports the honor concealed-triplet 2-fan example. This is not a complete fan aggregation algorithm.
- 庄5/base30 is a directly observed pair of values, not proof of every dealer-base transition or any cap.
Regression: `tests/fixtures/settlement_b3892b34.json`, `tests/test_b3892b34_evidence.py`.

## Direct replay evidence — 7bc12fa, 2026-09-18

[Source and frame review](references/gameplay/2026-09-15/7bc12fa_video_evidence.md): anonymized in-game replay `evidence_7bc12fa`, hand 6/8, gold M1 (一筒), 单金不平胡, trusteeship on, 2025-12-16 22:05:48. Duration 57.47s.
- Path: flower replacement; several PASS on opponent discards after tenpai; Chi; discard 一条 (waste bamboo, not gold) with Youjin badges; then Double-You splash; draw 八万 still badged; Triple-You splash; further PASS available; settlement Triple-You ×16 +608/-608.
- The anonymized winner (`seat_0`) shows **5庄**, gold 1 fan + flowers 2 fan. `(35 + 3) × 16 = 608`. Winner is the dealer; there is no extra dealer ×2 (that would be 1216).
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
- **开出的金牌是4张同牌中的一张实体牌，并固定留在开金区，不能回到牌墙或摸牌区。** 因此开金后剩余可操作金最多3张；Environment 必须把开出的那张金从可摸牌墙移出但继续计入144张实体牌守恒。
- If opponent discards the current gold tile, it cannot be Chi/Peng/Gang/Hu.
- Gold is a wildcard in allowed hand/win composition.
- A triplet completed using gold is not a natural concealed-triplet fan.
- Single-gold Pinghu is a player/room setting (player clarification 2026-09-13). It is usually disabled. Default `single_gold_can_pinghu=False` preserves the observed target-room behavior; enable only for a room explicitly allowing it. The generic page's allowance does not override a room's setting.
- Player confirmation (2026-09-14): in the target room, exactly one gold may complete a self-draw Hu when the standard structure is valid. The checked 单金不平胡 option blocks ordinary discard-win Pinghu; it does not block this self-draw.
- Player confirmation (2026-09-14): with exactly two gold tiles, Hu is allowed only by self-draw; the player cannot Hu on any opponent discard. This supersedes the older blanket statement that double gold could not Pinghu. The Rules API must carry the win source before this restriction can be implemented correctly.
- Player confirmation (2026-09-14): ordinary Hu evaluation and Youjin evaluation are separate branches. Passing or failing an ordinary structural Hu check must not silently decide Youjin eligibility.
- Player confirmation (2026-09-14): opening Qiangjin is checked after all opening flower replacement and opening gold are complete, before the first discard. A hand must already be a valid Hu after treating gold copies as wildcards, and holding three or more copies takes the Sanjindao branch first. Updated player confirmation (2026-09-18): the Qiangjin prompt at an applicable node belongs only to the current acting player; PASS closes the window for that turn and does not hand the opportunity to the opponent. The exact executable hand-shape predicate is still not fully encoded and remains a separate evidence task.
- **三金倒的“过”只关闭当前这一次提示，不再视为本局永久关闭。** 已确认入口至少包括：① 开局补花/开金完成后的当前玩家检查，手里已有全部3张可操作金时可提示；② 对局中有效摸牌由2金变3金时可提示；③ match_evidence_002 + 玩家确认进一步证明，已经点【过】后，只要后续自己的摸牌节点仍保留3张金，系统可以再次给出【三金倒 / 过】。因此“过一次后本局永不再弹”的旧规则作废。2026-09-20玩家进一步确认：开出的金本身占用4张同牌中的1张并留在开金区，不能再进入摸牌区，因此一局最多只有3张可操作金；此前“4金重复窗口”不是UNKNOWN，而是物理不可能。过三金倒后普通自摸/点炮和游金/双游/三游路线都继续有效；同一录像最终进入游金并以双游×8结算。每张手中金仍按1番累计，最多+3番；三金倒仍为独立×3结果，三金游/三游统一为 `TRIPLE_YOU` ×16。三金倒实际结算底数、付款、终局账务和下局庄位仍UNKNOWN。
- Dealer win -> dealer stays.
- Draw -> dealer stays.
- Dealer loss -> other player becomes dealer.
- Match default is 8 hands. Player confirmation (2026-09-18): both players start at 1000 points. Each settled hand transfers its net result between the two players; after hand 8, the accumulated scores are the match result. Therefore the AI's primary objective is to maximize its own final score after 8 hands (equivalently, with equal starts and zero-sum transfers, maximize accumulated score delta / final score margin), not to maximize single-hand win count. Tie handling remains UNKNOWN.
- Player confirmation (2026-09-14): the target rules do not award complex combination fans such as 门清、碰碰胡、清一色、混一色 or similar pattern families. Such tile arrangements may still satisfy the standard Hu structure, but receive no special fan for those names.
- Confirmed in-scope Hu/settlement categories are Pinghu, Zimo, Sanjindao, Youjin, Double-You, Triple-You, Eight-Flower You (八花游), flower scoring, and repeat-dealer/base scoring. Confirmation of the category scope does not confirm every trigger, multiplier, stacking rule, or settlement formula; unresolved details below remain UNKNOWN.
- Player confirmation (2026-09-14): each flower contributes 1 fan as its base flower value. Complete-set bonuses, stacking, and the interaction with special flower outcomes remain separate questions.
- Direct replay `7bc12fa…mp4` confirms Triple-You/三游 ×16; `66fe863f` confirms Youjin ×4; **match_evidence_002 directly confirms terminal Double-You ×8** with `(dealer base30 + gold2 + flower1)×8=264`. Dealer Triple-You settles +608/-608 with current dealer base 35 and winner fan 3 (gold 1 + two flowers 2): `(35 + 3) × 16 = 608`. Flower fan is inside the Hu multiplier. Extra Youjin-chain dealer ×2 is **not** applied on this dealer Triple-You (608, not 1216) and is not applied on ordinary dealer Zimo +68. Declaration-edge cases, cancellation and next dealer remain unresolved. See `references/gameplay/2026-09-15/7bc12fa_video_evidence.md`.
- **八花游触发已确认；项目结算改为固定16番、无额外倍数。** 集齐8花即可DECLARE/PASS，不要求普通胡结构。DECLARE时按项目WORKING规则固定记16番，倍率×1，不再叠加8张花的普通8番、金牌番、刻子/杠番或其他附加番；因此项目公式为 `当前庄底 + 16`。若选择【过】，8张花仍按1番/张共8番保留到后续普通/其他胡法。真实目标房八花游终局结算仍未直接观察，未来若有高优先级实战证据冲突，以实战覆盖项目规则。
- Confirmed opponent response during the Youjin chain (updated 2026-09-20): Youjin, Double-You and Triple-You each give the opponent exactly one ordinary draw opportunity to self-draw Hu; if the opponent does not self-draw on that opportunity, the current Youjin stage succeeds.

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
## Dealer base — complete-match mapping

The 2026-09-19 match_evidence_001 complete 8-hand replay resolves the earlier field-mapping ambiguity.

Confirmed target-room mapping:
- non-dealer own displayed base: **5**
- newly sitting dealer current settlement base: **10**
- second consecutive dealer hand: **15**
- third consecutive dealer hand: **20**
- fourth consecutive dealer hand: **25**
- dealer loss: opponent becomes dealer and resets to **10**
- each additional consecutive dealer hand adds **+5**

This directly reconciles the earlier player wording “坐庄底分5分，连庄+5”: the ordinary player base is 5 and sitting dealer contributes another +5 to the settlement base. The simulator must therefore use 10, not 5, for the first dealer hand.

Older direct target evidence also reaches dealer base 30 and 35. Player confirmation 2026-09-19 confirms there is **no cap during a continuous dealer streak**: every retained-dealer hand adds +5 until the 8-hand match ends. Thus a dealer who keeps all eight hands follows 10→15→20→25→30→35→40→45. If the dealer loses at any point, the new dealer starts a new streak at 10.

## Flower scoring

CONFIRMED for the target room:
- each flower = **1 fan**
- flower fan is strictly linear
- 4 flowers = 4 fan; completing 春夏秋冬 or 梅兰竹菊 does **not** add a separate four-flower group bonus
- after declining Eight-Flower-You, all 8 flowers remain **8 ordinary fan**

The game-internal generic page item “八花齐16番” is retained only as a separate evidence lead for the special eight-flower context; it must not override the player-confirmed linear ordinary flower fan and must not be read as “Eight-Flower-You ×16”.

## Gold / triplet / kong working values
External Quanzhou-family sources and prior rules are broadly consistent with:
- gold: 1 fan each
- normal concealed triplet: 1
- honor concealed triplet: 2
- normal exposed kong: 2
- honor exposed kong: 3
- normal concealed kong: 3
- honor concealed kong: 4
Direct b3892b34 evidence supports gold 1 and the natural S999/WWW concealed-triplet examples at 1/2 fan. The direct 66fe863f sequence confirms a suited added-kong at 2 fan. Match evidence 001 hand 6 directly confirms a suited concealed kong at 3 fan. Honor-kong cells and suited big-Ming-kong remain HIGH_CONFIDENCE from the in-game rule page unless stronger target-room evidence appears. Independent kong fees are confirmed absent.

## Youjin chain
Confirmed from 66fe863f and 7bc12fa (target room):
- Ordinary Hu and Youjin are separate branches.
- Entry does not require discarding gold. After tenpai, discarding a waste tile can enter Youjin (7bc12fa: 一条 or 二条 while gold remains 一筒; 66fe863f: discard S1, retain gold M1).
- Chi then Youjin is allowed.
- The archived 7bc12fa clip shows a sequential Youjin → Double-You → Triple-You climb using non-gold waste-tile play. match_evidence_002 adds a different observed path: the player is visibly in Youjin while holding **3 gold**, then reaches Double-You and terminates with **2 gold**. Therefore the stage is not defined by gold count, and the project must not assert that upgrades can never involve a gold leaving the hand. The universal upgrade predicate remains unresolved.
- Multipliers: Youjin ×4, Double-You ×8 and Triple-You ×16 are now all direct-settlement CONFIRMED in the target room. match_evidence_002 closes the former Double-You evidence gap with +264/-264. Dealer Youjin hand 5 in match_evidence_001 and the earlier dealer Triple-You +608 both prove there is no extra dealer ×2.
- The Youjin-side player may PASS opponent discards while climbing the chain.

Still UNKNOWN programmatically:
- exact trigger predicate for every edge hand (whether gold must complete the pair, all wait sets)
- whether any room path can skip Youjin and enter Double-You directly (not seen in 7bc12fa)
- which actions cancel the state in every case
- opponent Hu sources during Youjin / Double-You / Triple-You beyond the 2026-09-14 oral permissions (this clip does not show the opponent winning)

The 66fe863f replay remains one Youjin ×4 path after Chi. Match evidence 001 adds a second Youjin ×4 settlement and, crucially, a dealer Youjin with two gold tiles settling +76 without extra dealer ×2. 7bc12fa adds the climb to Triple-You ×16 and dealer-winner settlement +608.

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
room. Flower fan is included before the Hu multiplier in the +608 recording and ordinary direct recordings. Extra Youjin-chain dealer ×2 is now directly rejected for the target room: match_evidence_001 hand 5 is dealer Youjin and settles +76 as `(15+4)×4`, while the earlier dealer Triple-You settles +608 as `(35+3)×16`. The page's outer ×3 must not be applied to the verified two-player calculation.

## Still important UNKNOWN questions
1. 抢金 remaining gaps: the exact effective Hu decomposition/options and settlement/dealer result. Current-player ownership and PASS-does-not-handoff are resolved; do not re-open them as UNKNOWN.
2. Actual-room rob-kong evidence: only Added-Gang/ADD_KONG (补杠=蓄杠=加杠) can be robbed; 大明杠/MING_GANG and 暗杠/AN_GANG cannot. Player confirmation also resolves that there is no independent kong fee and no special kong-fee accounting at flow draw. What remains UNKNOWN is the real response UI/decline footage and rob-kong/Gang-Hu scoring.
3. Sanjindao remaining gaps: non-flower base, payment, terminal settlement accounting and next dealer. Timing now includes opening 3+ gold, the first 2→3 gold arrival, and a later own-draw recheck while exactly 3 gold remain after an earlier PASS. DECLARE/PASS is optional; PASS closes only the current prompt. ×3 is confirmed. The four-gold later-draw recheck remains UNKNOWN.
4. 三游 / 三金游 remaining gaps: these names mean the same `TRIPLE_YOU` state, distinct from 三金倒. Youjin-family 4/8/16 and `(current dealer base + winner fan) × Hu multiplier` are all directly confirmed: Youjin examples, match_evidence_002 Double-You +264, and 7bc12fa Triple-You +608. Sequential climb Youjin→Double→Triple and self-PASS while climbing are confirmed in that clip. Exact predicate for every upgrade discard, cancellation, opponent Hu windows on video, payer UI and next-dealer result remain UNKNOWN.
5. Gang-Hu remaining gaps: multiplier/fan, stacking, settlement, and any room option. Its classification after all three completed kong types is confirmed.
6. Exact Youjin / Double-You / Triple-You triggers and the remaining permission windows not resolved by the confirmed opponent-rights matrix.
7. Remaining room multipliers outside ordinary Pinghu/Zimo 1/2, Sanjindao ×3, and the fully confirmed Youjin chain ×4/×8/×16. The extra Youjin-chain dealer ×2 hypothesis is closed as false for the target room by dealer Youjin +76 and dealer Triple-You +608.
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
13. 八花游：真实触发规则已确认——集齐8张花即可直接特殊胡，不要求普通牌型；可选择【过】，过后8花按1番/张计入普通胡，共8番。项目WORKING结算现统一为固定16番、×1、无其他番叠加，即 `当前庄底+16`；真实房间终局仍缺直接结算证据，后续若有真实结算图则以真实证据覆盖。庄位按正常流程。

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
