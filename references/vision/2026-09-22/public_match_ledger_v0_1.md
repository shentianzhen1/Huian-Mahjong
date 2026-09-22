# Public Match Ledger V0.1

Date: 2026-09-22  
Issue: #69  
Status: deterministic review view

## Goal

Provide the human-readable whole-match ledger requested for rule review:

    第 1/8 局
    庄家：对手 ｜ 金：南
    开局比分：我方 1000 ｜ 对手 1000

    00:06.8 对手出牌：9万
    00:12.4 对手出牌：5筒
    00:13.0 我方吃：3筒 4筒 5筒（吃5筒）
    ...
    00:52.3 我方状态：游金中
    ...
    01:14.5 我方胡牌：双游

    结算：
    - 倍率：×8
    - 赢家净分：+264
    - 结算后比分：我方 1264 ｜ 对手 736

The ledger is a **view**, not a second evidence database.

## Canonical source

`HandTimeline` JSON remains canonical.

`match_ledger.py` renders the existing context / events / settlement into
Chinese text. It never creates rule or scoring values that are not present in
the Timeline.

This prevents drift between:

- machine evidence;
- audit Markdown;
- the concise ledger the user reads.

## Views

### Simple ledger

Optimized for quick replay analysis:

- hand index;
- dealer;
- Gold/Jin;
- opening score;
- public actions;
- Youjin-family status;
- Hu subtype when known;
- settlement fields when known.

Machine confidence noise is hidden unless needed.

### Audit ledger

`audit=True` appends:

- canonical Timeline evidence level;
- reconstruction grade;
- reconstruction confidence;
- evidence references.

A machine-CORROBORATED action can therefore still clearly show:

    timeline=unknown | machine=CORROBORATED

until explicit review upgrades the canonical evidence.

## Tile display

Stable IDs are translated only for presentation:

- M1..M9 -> 1万..9万
- P1..P9 -> 1筒..9筒
- S1..S9 -> 1条..9条
- E/SOUTH/W/N -> 东/南/西/北
- R/G/B -> 中/发/白
- F1..F8 -> 花1..花8

The underlying JSON keeps stable IDs.

## Action display

V0.1 has dedicated readable rendering for:

- HAND_START
- OPEN_GOLD
- DISCARD
- CHI
- PENG
- MING_GANG
- ADD_KONG
- AN_GANG if future reviewed evidence emits it
- YOUJIN_STATE
- Youjin-family animation evidence
- HU
- SETTLEMENT / SETTLEMENT_PAGE
- UNKNOWN_ACTION
- EVIDENCE_CONFLICT

Unknown event kinds fall back to actor + raw kind and are not dropped.

## Settlement display

Only known fields are shown:

- winner;
- win type;
- fan;
- multiplier;
- dealer base;
- winner net score;
- scores after;
- next dealer;
- unresolved rules.

If no settlement evidence exists, the ledger explicitly says:

    结算：待确认

## Eight-hand match index

`build_match_ledger_index()` provides:

- evidence IDs;
- recorded hand indexes;
- missing hands;
- score continuity issues;
- complete flag.

A partial match does not pretend to be complete.

### Score continuity guard

When both values are known:

    hand N scores_after
    hand N+1 initial_scores

must match.

A mismatch is surfaced as an anomaly such as:

    hand_1_scores_after_!=_hand_2_initial_scores

It is never silently repaired.

## Action -> Timeline bridge

`hand_timeline_draft_from_actions()` closes the current pipeline:

    stable visual observations
      -> TemporalActionAssembler
      -> ReconstructedAction
      -> UNKNOWN-only HandTimeline draft
      -> Public Match Ledger

The bridge calls `ReconstructedAction.to_timeline_event()`, so machine output
remains canonical evidence_level=unknown until human review.

## Non-goals

The ledger does not:

- recognize pixels;
- infer dealer from turn order;
- infer Gold from hand tiles;
- calculate unknown fan or settlement;
- infer Hu subtype from generic Hu animation;
- promote rule evidence;
- drive Hint Alpha or Executor.

## Next work

The project can now generate the final review format once observations exist.

The remaining Vision bottleneck is no longer the ledger architecture. It is
feeding reliable real-frame public facts into the pipeline:

1. player/opponent discard detection;
2. opponent meld detection;
3. meld-region tile identity;
4. Youjin/Hu/settlement public-state observation.

Those should be calibrated from reviewed real target-room frames, not guessed.
