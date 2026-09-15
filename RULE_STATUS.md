# Huian Two-Player Rules Status

This file separates CONFIRMED / HIGH-CONFIDENCE / UNKNOWN rules.
Do not silently promote UNKNOWN rules.

## Confirmed / very high confidence
- Full 144-tile set is used.
- Dealer starts with 17 tiles; non-dealer starts with 16.
- Flowers do not participate in normal meld composition; they score separately.
- Player confirmation (2026-09-14): unclaimed discard + PASS advances to the next player's head draw; at 16 wall tiles the hand draws with rewards [0, 0].
- Target room is fixed: 2 players, 8 hands, 单金不平胡 checked (`single_gold_can_pinghu=False`), no trusteeship. Earlier unchecked screenshot records the option UI, not this final room choice.
- Opponent discard can offer Chi/Peng/Gang/Hu where legal; Rules must return all legal actions and AI chooses.
- In 2-player Huian, the sole opponent's discard may be Chi'd.
- Confirmed rule and system interaction (player confirmation, 2026-09-14): when one discard permits multiple Chi sequences, every legal sequence is a separate choice. The mini-program opens a Chi-option selection panel and the player selects the exact sequence; it does not auto-select and a generic Chi action must not silently choose one. Example: discard M5 with M3/M4, M4/M6 and M6/M7 available offers M3-M4-M5, M4-M5-M6 and M5-M6-M7.
- Confirmed/reconfirmed player interaction (2026-09-14): after Chi or Peng completes, that player immediately enters the discard phase and must discard one tile; there is no intervening normal draw.
- Player confirmation (2026-09-14): after a completed Ming-Gang, An-Gang, or Added-Gang, the declarer draws from the wall tail. That draw follows the normal draw/flower-processing pipeline; its provenance must be recorded as `wall_tail` rather than modeled as a separate complex replacement flow.
- Added kong after Peng is allowed.
- Player confirmation (2026-09-14): a Hu by the kong declarer after the tail draw for any completed Ming-Gang, An-Gang, or Added-Gang is classified uniformly as Gang-Hu (杠胡). This does not answer whether or when another player may rob a kong; rob-kong remains a separate UNKNOWN response window.
- Gold cannot participate in Chi/Peng/Ming-Gang/An-Gang.
- If opponent discards the current gold tile, it cannot be Chi/Peng/Gang/Hu.
- Gold is a wildcard in allowed hand/win composition.
- A triplet completed using gold is not a natural concealed-triplet fan.
- Single-gold Pinghu is a player/room setting (player clarification 2026-09-13). It is usually disabled. Default `single_gold_can_pinghu=False` preserves the observed target-room behavior; enable only for a room explicitly allowing it. The generic page's allowance does not override a room's setting.
- Player confirmation (2026-09-14): in the target room, exactly one gold may complete a self-draw Hu when the standard structure is valid. The checked 单金不平胡 option blocks ordinary discard-win Pinghu; it does not block this self-draw.
- Player confirmation (2026-09-14): with exactly two gold tiles, Hu is allowed only by self-draw; the player cannot Hu on any opponent discard. This supersedes the older blanket statement that double gold could not Pinghu. The Rules API must carry the win source before this restriction can be implemented correctly.
- Player confirmation (2026-09-14): ordinary Hu evaluation and Youjin evaluation are separate branches. Passing or failing an ordinary structural Hu check must not silently decide Youjin eligibility.
- Player confirmation (2026-09-14): 抢金 is checked only after all opening flower replacement and opening gold are complete, and before the dealer has discarded a first tile. A hand must already be a valid Hu after treating its gold copies as wildcards. Holding three or more copies of the single gold tile takes the 三金倒 branch first; it does not take 抢金. At this opening point no Chi/Peng/Gang can yet have occurred.
- Player confirmation (2026-09-15): `can_sanjindao = hand_gold_count >= 3`; ordinary complete-hand structure is not required for this eligibility check. Sanjindao is an optional action, not an automatic terminal: the player may declare it immediately or continue through the Youjin route. 三金游 and Triple-You (三游) are two names for the same state, represented canonically as `TRIPLE_YOU`; it follows the same trigger flow as 二金游. 三金倒 is a separate ×3 outcome, while 三游 is ×16. The exact executable sequence, non-flower base, payer and full settlement remain UNKNOWN.
- Dealer win -> dealer stays.
- Draw -> dealer stays.
- Dealer loss -> other player becomes dealer.
- Match default is 8 hands.
- Player confirmation (2026-09-14): the target rules do not award complex combination fans such as 门清、碰碰胡、清一色、混一色 or similar pattern families. Such tile arrangements may still satisfy the standard Hu structure, but receive no special fan for those names.
- Confirmed in-scope Hu/settlement categories are Pinghu, Zimo, Sanjindao, Youjin, Double-You, Triple-You, Eight-Flower You (八花游), flower scoring, and repeat-dealer/base scoring. Confirmation of the category scope does not confirm every trigger, multiplier, stacking rule, or settlement formula; unresolved details below remain UNKNOWN.
- Player confirmation (2026-09-14): each flower contributes 1 fan as its base flower value. Complete-set bonuses, stacking, and the interaction with special flower outcomes remain separate questions.
- Player confirmation (2026-09-15): target-room Youjin multipliers are Youjin ×4, Double-You ×8, and Triple-You/三金游 ×16. If the winner is the dealer, the non-flower component receives a further ×2 dealer multiplier. Flower water is additive at 1 point per flower and is added after these multipliers; it is not multiplied by the Youjin or dealer factors. This confirms the arithmetic terms, not the unresolved base component, payer, declaration timing, or next dealer.
- Player confirmation (2026-09-14): 八花游 exists in the target rules. Its existence is confirmed; exact declaration timing, relation to ordinary flower fan, multiplier, and settlement remain UNKNOWN.
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

Current scoring hypothesis (HIGH CONFIDENCE, not final):
`actual two-player net = (CURRENT DEALER BASE + WINNER FAN) * WIN-TYPE MULTIPLIER`
Winner +X, loser -X.
Need at least one additional real settlement to confirm.

## 2026-09-13 WGC capture review — additional real settlements

Archived frames and a full transcription are in
[`references/capture_review/2026-09-13`](references/capture_review/2026-09-13/README.md).

- Pinghu, winner base 10 + concealed triplet 1 = **+11/-11**.
- Pinghu, current dealer base 15 + winner flower 1 = **+16/-16**, although the winner's own displayed base is 5. This confirms the verified formula uses the **current dealer base**.
- Zimo x2, current dealer/winner base 10 + gold 1 + flowers 5 + triplet 1 + kong 2 = **+38/-38**.
- A flow settlement is explicitly **0/0** despite displayed hand fan values.

For observed Pinghu and Zimo cases, the formula
`(current dealer base + winner fan) × win-type multiplier` is now supported by
multiple direct recordings. It remains unconfirmed for 抢金、三金倒、游金、杠分和
other special outcomes.
## Dealer base hypothesis
Observed:
- non-dealer: 5 base
- dealer: 10 base
- 庄2: 15 base
External rule info also says each repeat dealer adds +5.
Likely sequence: 5 / 10 / 15 / 20 / ...
Still needs real-game confirmation for 庄3+ and any cap.

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
Treat as working values until Huian settlement evidence confirms edge cases.

## Youjin chain
Player feedback and external sources broadly agree:
- Youjin occurs when the hand is otherwise complete and gold participates in the pair; discarding the other pair tile can enter Youjin.
- next draw may complete/succeed in Youjin.
- Double-You and Triple-You are upgrades involving further gold actions.

Still UNKNOWN programmatically:
- exact trigger condition for all edge cases
- whether Double-You can be entered directly or must pass through Youjin
- exact Triple-You chronological sequence
- during Youjin, the exact Hu sources/windows covered by the confirmed general Hu right
- during Double-You, whether the opponent has any Hu right beyond the confirmed self-draw
- which actions cancel the state in every case

The existence of Youjin and its separation from ordinary Hu are confirmed. The
items above remain unknown only for the executable state-machine details.

## Multipliers
Real Huian screenshot confirms:
- Zimo x2 in at least one room
- Youjin x4 in at least one room

External rules suggest room-configurable groups may exist, for example:
- Youjin x3 -> Double-You x6 -> Triple-You x9 or x12 depending on ruleset
- Youjin x4 -> Double-You x8 -> Triple-You x12
Do NOT hard-code the chain until Huian room evidence confirms it.

The user-supplied 惠安 tab lists Youjin/Double/Triple as **4/8/16**, not 4/8/12.
The 2026-09-15 player confirmation now applies 4/8/16 to the target two-player
room, with a separate dealer-winner ×2 and additive flower water. The page's
outer ×3 belongs to other displayed formula context and must not be applied to
this target-room calculation.

## Still important UNKNOWN questions
1. 抢金 remaining gaps: the exact effective Hu decomposition/options, multi-seat declaration priority, and settlement/dealer result.
2. Exact rob-kong scope: added kong only? exposed kong? concealed kong?
3. Sanjindao remaining gaps: exact action-offer windows at opening/mid-hand/after flower or kong; how declining it interacts with the opening 抢金 check; non-flower base, payment, terminal flow and next dealer. Eligibility at three or more gold, the declare/continue choice and ×3 multiplier are confirmed.
4. 三游 / 三金游 remaining gaps: these names mean the same `TRIPLE_YOU` state, distinct from 三金倒. Youjin 4/8/16, dealer-winner ×2, and additive one-point-per-flower terms are confirmed. The exact shared executable trigger sequence, non-flower base component, payer, terminal transition and next-dealer result remain UNKNOWN.
5. Gang-Hu remaining gaps: multiplier/fan, stacking, settlement, and any room option. Its classification after all three completed kong types is confirmed.
6. Exact Youjin / Double-You / Triple-You triggers and the remaining permission windows not resolved by the confirmed opponent-rights matrix.
7. Exact room multiplier chain.
8. Exact open-gold procedure when a flower is revealed. External info says the flower counts for dealer, dealer replaces it, then gold is reopened; needs Huian confirmation.
9. Exact Tianhu timing relative to flower replacement/open-gold.
10. Exact Tianting definition.
11. Resolved 2026-09-14: all-PASS advances to the next player's draw.
12. 8-hand match tie handling.
13. Third real settlement to validate the scoring formula.

## External web review — 2026-09-13 (not rule confirmation)

See [source register and comparison](references/HUIAN_WEB_RULES_2026-09-13.md).
No target-room rule was promoted to CONFIRMED in this review.

- A [2022 entry tutorial](https://jingyan.baidu.com/article/3ea51489a942cf13e71bba11.html) identifies a historical 开心泉州麻将 mini-program rules menu. It does not establish the current 惠安 two-player rules or operator. The linked rule image was not successfully read.
- A [different product's 泉州 page](https://www.xinyueyouxi.com/game/219-22?doc-innerlink-%E4%BF%A1%E5%BF%B5=&region=) provides room-multiplier and scoring comparison leads. Its values must not be imported as 开心惠安 defaults. See the source register for applicability and conflicts.
- Current dealer-base observations, the A/B settlement hypothesis and all existing confirmed rules remain unchanged. No third target-room settlement was found.

Additional UNKNOWN questions exposed by the comparison:
11. Whether a natural exposed suited triplet scores fan, and the exact honor Peng value in the target room.
12. Whether added-kong fan is an incremental bonus or a total meld value.
13. Resolved in part by player confirmation: 八花游 exists. Its declaration timing, interaction with the eight individual flower fans, multiplier and settlement remain UNKNOWN.

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
  with dealer. Two-player scheduling remains unresolved.
- Opening uses two dice and counts from the wall end after the stated dealer
  replacement point; flowers require replacement/reopening until non-flower.
  Exact indexing, ownership, turn order and physical accounting remain unresolved.
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
  two-player results. Target-room dealer winners instead apply ×2 to the non-flower
  component, and flowers add afterward at one point each. The non-flower base and
  full settlement flow still need direct evidence.

Still missing after the 2026-09-14 flow clarification: rob-kong scope,
Tianhu/Tianting definitions, extended dealer base/cap and match ties. A listed
multiplier does not establish a win type's eligibility or declaration timing.
