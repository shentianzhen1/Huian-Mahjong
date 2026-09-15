# Huian Two-Player Rules Status

This file separates CONFIRMED / HIGH-CONFIDENCE / UNKNOWN rules.
Do not silently promote UNKNOWN rules.

## Implemented added-kong response contract — user implementation request

The current implementation request defines an added-kong-only response path. This is an explicit engineering contract, not new video proof of the mini-program's rob-kong interaction. The 66fe863f replay confirms a Peng upgraded to an added kong and that example's displayed fan; it does not show a rob-kong attempt.

- `ADD_KONG` is offered for an existing non-gold Peng plus its fourth tile in the declarer's hand. Gold cannot be added-konged.
- Declaration enters `ROB_KONG_WINDOW`. The original Peng and fourth hand tile remain unchanged; `pending_kong` is a logical reference, not another physical tile. Only this added-kong window offers `ROB_KONG_HU` when Rules establishes eligibility, or `PASS`.
- `PASS` commits the fourth tile once, forming `ADDED_GANG`, then requires a `wall_tail` draw through the existing flower replacement pipeline. A successful rob records winner/source and keeps the original Peng and tile accounting; it does not complete the kong or draw a replacement.
- `enable_added_kong=True` is the default. False disables added-kong candidates. Simulator `enable_rob_kong=False` remains the broad unsupported scope switch; setting it True does not enable Ming/An rob-kong.
- Scoring remains UNKNOWN: successful rob → `ROB_KONG_SCORING_UNKNOWN`; declared kong-tail Hu → `GANG_HU_SCORING_UNKNOWN`; completed added-kong tail draw without Hu → `ADD_KONG_SCORING_UNKNOWN`. These paths do not receive ordinary simulation rewards or assumed zero-fee drawn-hand settlement. Flower replacement stops at the 16-tile boundary instead of crossing it.

Remaining evidence gaps: actual-room added-kong response/decline footage, exposed/concealed-kong rob permissions, independent kong fees, boundary settlement and all rob-kong/Gang-Hu scoring. Implemented transitions and passing tests do not promote those gaps to confirmed rules.

## Latest direct replay evidence — 66fe863f, 2026-09-15

[Source and frame-by-frame review](references/gameplay/2026-09-15/66fe863f_youjin100/README.md): room 206640, hand 5/8, gold M1, 单金不平胡, no trusteeship.
- Observed path: P1 Peng → fourth P1 → added kong; then Chi S789, discard S1 while retaining one gold, opponent plays, M7 appears, Youjin ×4 settles. This is one verified path, not a complete Youjin or rob-kong state machine.
- Winner is the non-dealer (own base5); opponent is 庄3/base20. Winner fan is gold1 + flower1 + triplet1 + kong2 = 5. Displayed winner value40 is `(own base5+fan5)×4`; actual +100/-100 is `(current dealer base20+fan5)×4`. The loser's 1 fan is not deducted.
- The sole kong was visibly formed by upgrading a P1 Peng; its displayed 2-fan contribution confirms this suited added-kong example. This does not confirm incremental kong fees, payments at declaration, rob-kong permissions, or flow-hand kong settlement.
- One gold can follow this Youjin path after Chi without discarding that gold. The reply/decline/cancellation branches and dealer-winner Youjin multiplier remain unverified.
Regression: `tests/fixtures/settlement_66fe863f.json`, `tests/test_66fe863f_evidence.py`.

## Direct replay evidence — b3892b34, 2026-09-15

[Source, frame timestamps and transcription](references/gameplay/2026-09-15/b3892b34_zimo68/README.md).
This is an in-game replay of room 745816, hand 8/8, with 单金不平胡 and no trusteeship.
- At 60/65 seconds, one gold S3 and two Chi melds are visible before/after the winning M5; all three suits are present. Ordinary self-draw therefore has no mandatory missing-suit gate in this target room.
- At 71–75 seconds, the dealer badge is 庄5, dealer base is 30, winner fan is gold 1 + flowers 2 + concealed triplet 1, and Zimo ×2 pays +68/-68: `(30 + 4) × 2 = 68`.
- This ordinary dealer self-draw has no extra dealer ×2, and the loser's displayed 4 fan is not subtracted. It does not determine a dealer multiplier for the Youjin chain.
- The visible natural S999 triplet supports the suited concealed-triplet 1-fan example; the loser's natural WWW supports the honor concealed-triplet 2-fan example. This is not a complete fan aggregation algorithm.
- 庄5/base30 is a directly observed pair of values, not proof of every dealer-base transition or any cap.
Regression: `tests/fixtures/settlement_b3892b34.json`, `tests/test_b3892b34_evidence.py`.


## Confirmed / very high confidence
- Full 144-tile set is used.
- Dealer starts with 17 tiles; non-dealer starts with 16.
- Flowers do not participate in normal meld composition; their fan is a separate component included before the Hu multiplier in verified ordinary settlements.
- Player confirmation (2026-09-14): unclaimed discard + PASS advances to the next player's head draw; at 16 wall tiles the hand draws with rewards [0, 0].
- Target room is fixed: 2 players, 8 hands, 单金不平胡 checked (`single_gold_can_pinghu=False`), no trusteeship. Earlier unchecked screenshot records the option UI, not this final room choice.
- Opponent discard can offer Chi/Peng/Gang/Hu where legal; Rules must return all legal actions and AI chooses.
- In 2-player Huian, the sole opponent's discard may be Chi'd.
- Confirmed rule and system interaction (player confirmation, 2026-09-14): when one discard permits multiple Chi sequences, every legal sequence is a separate choice. The mini-program opens a Chi-option selection panel and the player selects the exact sequence; it does not auto-select and a generic Chi action must not silently choose one. Example: discard M5 with M3/M4, M4/M6 and M6/M7 available offers M3-M4-M5, M4-M5-M6 and M5-M6-M7.
- Confirmed/reconfirmed player interaction (2026-09-14): after Chi or Peng completes, that player immediately enters the discard phase and must discard one tile; there is no intervening normal draw.
- Player confirmation (2026-09-14): after a completed Ming-Gang, An-Gang, or Added-Gang, the declarer draws from the wall tail. That draw follows the normal draw/flower-processing pipeline; its provenance must be recorded as `wall_tail` rather than modeled as a separate complex replacement flow.
- Confirmed system interaction (player confirmation, 2026-09-15): flower replacement is dealt automatically by the mini-program and the interface has no obvious tile-by-tile dealing animation. Environment must model replacement as a system event rather than a player action. Vision/Recorder must infer it from the next stable state—hand count, flower count, wall remaining and opening-gold phase—not from animation presence. This observation rule does not change the confirmed wall-tail replacement source.
- Added kong after Peng is allowed.
- Player confirmation (2026-09-14): a Hu by the kong declarer after the tail draw for any completed Ming-Gang, An-Gang, or Added-Gang is classified uniformly as Gang-Hu (杠胡). Rob-kong is a separate response path. Its added-kong-only engineering contract is implemented above; actual-room response evidence and Ming/An rob-kong scope remain incomplete.
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
- Player-reported real-game video evidence `7bc12fa…mp4` (2026-09-15): target-room Youjin multipliers are Youjin ×4, Double-You ×8, and Triple-You/三金游 ×16. The recorded Triple-You settlement is +608/-608 with current dealer base 35 and winner fan 3 (gold line 1 + two flowers 2): `(35 + 3) × 16 = 608`. Winner fan, including flower fan, is therefore inside the Hu multiplier. This supersedes the earlier same-day statement that flower water was added after multiplication. For Youjin-chain dealer winners, a further ×2 remains player feedback without direct dealer-Youjin settlement verification; it must not be applied universally to ordinary wins. The non-video-verified payer flow, declaration timing and next dealer remain unresolved. See `references/gameplay/2026-09-15/7bc12fa_video_evidence.md`.
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
multiple direct recordings, including the dealer Zimo +68/-68 above with no extra dealer factor. The direct non-dealer Youjin +100 and player-reported Triple-You +608 are separate special examples; 抢金、三金倒、独立杠费 and complete special-outcome flows remain unresolved.
## Dealer base — player confirmation and observed display values

Player confirmation (2026-09-15), verbatim: “坐庄底分5分，连庄+5”. The +5 increment per repeat is confirmed. Preserve the stated sitting-dealer base of 5 as player feedback; its exact relationship to the observed dealer badge/displayed base must be reconciled against `a562bd213645d8d998e47bf62bdb45de.mp4`, which has not yet been reviewed. Do not overwrite the directly observed values below or infer a cap.
Observed:
- non-dealer: 5 base
- dealer: 10 base
- 庄2: 15 base
- 庄3: 20 base (direct 66fe863f settlement)
- 庄5: 30 base (direct b3892b34 settlement)
- current dealer base 35 (player-reported +608 Triple-You; winner/dealer identity not directly ingested)
Each repeat adds +5 according to the new player confirmation. The first dealer-label/display mapping and any cap remain UNKNOWN; the observed 庄3/base20 and 庄5/base30 samples themselves are confirmed.

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

The 66fe863f replay directly adds one entry path: Chi S789, discard S1 from a gold-plus-S1 pair-compatible structure, retain gold M1, opponent plays, M7 appears, Youjin ×4 wins. Pair compatibility is structural analysis, not a client decomposition display. Refusing/cancelling this path, upgrades and other action windows remain unknown.

The existence of Youjin and its separation from ordinary Hu are confirmed. The
items above remain unknown only for the executable state-machine details.

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
room. Flower fan is included before the Hu multiplier in the +608 report and ordinary direct recordings. Extra Youjin-chain dealer ×2 remains player feedback awaiting direct verification; ordinary dealer Zimo +68 has no such extra factor. The page's outer ×3 must not be applied to the verified two-player calculation.

## Still important UNKNOWN questions
1. 抢金 remaining gaps: the exact effective Hu decomposition/options, multi-seat declaration priority, and settlement/dealer result.
2. Actual-room rob-kong scope and response evidence: the added-kong-only contract is implemented, but Ming/An rob-kong and all rob-kong scoring remain UNKNOWN; the existing replay does not verify the response window.
3. Sanjindao remaining gaps: exact action-offer windows at opening/mid-hand/after flower or kong; how declining it interacts with the opening 抢金 check; non-flower base, payment, terminal flow and next dealer. Eligibility at three or more gold, the declare/continue choice and ×3 multiplier are confirmed.
4. 三游 / 三金游 remaining gaps: these names mean the same `TRIPLE_YOU` state, distinct from 三金倒. Youjin 4/8/16 and `(current dealer base + winner fan) × Hu multiplier` are supported by the +608 video report; flowers are one fan each inside winner fan. The exact shared executable trigger sequence, payer, terminal transition and next-dealer result remain UNKNOWN.
5. Gang-Hu remaining gaps: multiplier/fan, stacking, settlement, and any room option. Its classification after all three completed kong types is confirmed.
6. Exact Youjin / Double-You / Triple-You triggers and the remaining permission windows not resolved by the confirmed opponent-rights matrix.
7. Remaining room multipliers outside ordinary Pinghu/Zimo 1/2, Sanjindao ×3 and Youjin 4/8/16; extra Youjin-chain dealer ×2 still needs direct dealer-Youjin verification.
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
  two-player results. Extra Youjin-chain dealer ×2 remains player feedback; ordinary dealer Zimo +68 directly excludes an extra ×2 for that case. The +608 Triple-You report confirms flowers are included in
  winner fan before ×16. The full settlement flow still needs direct video ingestion.

Still missing after the 2026-09-14 flow clarification: rob-kong scope,
Tianhu/Tianting definitions, extended dealer base/cap and match ties. A listed
multiplier does not establish a win type's eligibility or declaration timing.
