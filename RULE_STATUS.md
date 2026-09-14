# Huian Two-Player Rules Status

This file separates CONFIRMED / HIGH-CONFIDENCE / UNKNOWN rules.
Do not silently promote UNKNOWN rules.

## Confirmed / very high confidence
- Full 144-tile set is used.
- Dealer starts with 17 tiles; non-dealer starts with 16.
- Flowers do not participate in normal meld composition; they score separately.
- Player confirmation (2026-09-14): unclaimed discard + PASS advances to the next player's head draw; at 16 wall tiles the hand draws with rewards [0, 0].
- Target room is fixed: 2 players, 8 hands, 单金不平胡 checked (`single_gold_can_pinghu=False`), no trusteeship. Earlier unchecked screenshot records the option UI, not this final room choice.
- Opponent discard can offer Chi/Peng/Gang/Hu where legal; Rules should return all legal actions and AI chooses.
- In 2-player Huian, the sole opponent's discard may be Chi'd.
- After Chi or Peng, player enters discard phase and must discard.
- Ming-gang and An-gang replacement draws come from the wall tail.
- Added kong after Peng is allowed.
- Gold cannot participate in Chi/Peng/Ming-Gang/An-Gang.
- If opponent discards the current gold tile, it cannot be Chi/Peng/Gang/Hu.
- Gold is a wildcard in allowed hand/win composition.
- A triplet completed using gold is not a natural concealed-triplet fan.
- Single-gold Pinghu is a player/room setting (player clarification 2026-09-13). It is usually disabled. Default `single_gold_can_pinghu=False` preserves the observed target-room behavior; enable only for a room explicitly allowing it. The generic page's allowance does not override a room's setting.
- Double gold cannot Pinghu.
- Player confirmation (2026-09-14): 抢金 is checked only after all opening flower replacement and opening gold are complete, and before the dealer has discarded a first tile. A hand must already be a valid Hu after treating its gold copies as wildcards. Holding three or more copies of the single gold tile takes the 三金倒 branch first; it does not take 抢金. At this opening point no Chi/Peng/Gang can yet have occurred.
- Sanjindao can win without a normal complete hand when its conditions are met; player may be allowed to continue instead of immediately declaring it.
- Dealer win -> dealer stays.
- Draw -> dealer stays.
- Dealer loss -> other player becomes dealer.
- Match default is 8 hands.

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
Real screenshot evidence:
- one flower can show 1 fan
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
- exact rights of the opponent while the other player is in Youjin/Double-You/Triple-You
- which actions cancel the state in every case

## Multipliers
Real Huian screenshot confirms:
- Zimo x2 in at least one room
- Youjin x4 in at least one room

External rules suggest room-configurable groups may exist, for example:
- Youjin x3 -> Double-You x6 -> Triple-You x9 or x12 depending on ruleset
- Youjin x4 -> Double-You x8 -> Triple-You x12
Do NOT hard-code the chain until Huian room evidence confirms it.

New in-game text evidence: the user-supplied 惠安 tab lists Youjin/Double/Triple
as **4/8/16**, not 4/8/12. This supersedes external guesses about what the page
says, but is not yet a verified two-player room configuration. See the screenshot
review below; its formulas also include an outer ×3.

## Still important UNKNOWN questions
1. 抢金 remaining gaps: the exact effective Hu decomposition/options, multi-seat declaration priority, and settlement/dealer result.
2. Exact rob-kong scope: added kong only? exposed kong? concealed kong?
2. Exact Sanjindao declaration timing.
3. Exact Youjin / Double-You / Triple-You triggers and opponent permissions.
4. Exact room multiplier chain.
5. Exact open-gold procedure when a flower is revealed. External info says the flower counts for dealer, dealer replaces it, then gold is reopened; needs Huian confirmation.
6. Exact Tianhu timing relative to flower replacement/open-gold.
7. Exact Tianting definition.
8. Resolved 2026-09-14: all-PASS advances to the next player's draw.
9. 8-hand match tie handling.
10. Third real settlement to validate the scoring formula.

## External web review — 2026-09-13 (not rule confirmation)

See [source register and comparison](references/HUIAN_WEB_RULES_2026-09-13.md).
No target-room rule was promoted to CONFIRMED in this review.

- A [2022 entry tutorial](https://jingyan.baidu.com/article/3ea51489a942cf13e71bba11.html) identifies a historical 开心泉州麻将 mini-program rules menu. It does not establish the current 惠安 two-player rules or operator. The linked rule image was not successfully read.
- A [different product's 泉州 page](https://www.xinyueyouxi.com/game/219-22?doc-innerlink-%E4%BF%A1%E5%BF%B5=&region=) provides room-multiplier and scoring comparison leads. Its values must not be imported as 开心惠安 defaults. See the source register for applicability and conflicts.
- Current dealer-base observations, the A/B settlement hypothesis and all existing confirmed rules remain unchanged. No third target-room settlement was found.

Additional UNKNOWN questions exposed by the comparison:
11. Whether a natural exposed suited triplet scores fan, and the exact honor Peng value in the target room.
12. Whether added-kong fan is an incremental bonus or a total meld value.
13. Whether all eight flowers grant a special win, rather than only flower fan, and any declaration timing/multiplier. This is an external variant question, not a confirmed Huian feature.

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
- C1, clarified by player feedback: single-gold Pinghu is configurable, usually
  disabled. Generic page text and the earlier disabled gameplay setting can differ.
  Runtime now exposes `single_gold_can_pinghu` with default False; Double-gold
  Pinghu remains forbidden regardless of this setting. Record each room's choice.
- C2: page multiplier chain 4/8/16 versus external 4/8/12. Record 16 accurately;
  keep actual two-player Double/Triple multipliers unconfigured.
- C3: outer ×3 and non-winner fan adjustment text versus A/B two-player net
  evidence. Do not reinstate legacy subtraction or add ×3 to two-player results.
  Current settlement hypothesis still needs a third real settlement.

Still missing after the 2026-09-14 flow clarification: rob-kong scope,
Tianhu/Tianting definitions, extended dealer base/cap and match ties. A listed
multiplier does not establish a win type's eligibility or declaration timing.
