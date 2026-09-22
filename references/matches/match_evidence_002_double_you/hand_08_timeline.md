# Hand Timeline Log

## Basic info

- Evidence ID: `match_evidence_002_double_you`
- Hand index: 8/8
- Source: archived user replay 14.mp4
- Source SHA256: f24898ecee56803c09bead267150a590143c043941d3287f436ed6e89930f51d
- Duration: 106.99 s
- Geometry: 1046x480
- Player seat: 0
- Dealer: 0
- Initial score: UNKNOWN
- Current dealer base: 30
- Gold / Jin: SOUTH
- Player flowers: —
- Opponent flowers: —
- Room options: two_player, eight_hands

## Timeline

| Time | Actor | Event | Tile | Screen evidence | Interpretation | Prompt / choice | Result | Evidence | UNKNOWN |
|---|---|---|---|---|---|---|---|---|---|
| 00:00.0 | player | REPLAY_BEGIN_STATE | UNKNOWN | Hand 8/8 begins with three highlighted SOUTH Jin visible. | Three playable Jin are visibly held; play continues. | UNKNOWN | play continues | direct_observation | — |
| 00:43.7 | player | SANJINDAO_PROMPT | UNKNOWN | Optional-action node with PASS visible; declaration text is partly covered by replay controls. | Player clarification identifies this as a Sanjindao opportunity while the same three Jin remain visible. | SANJINDAO / PASS / PASS | current prompt closes | player_confirmed | sanjindao_terminal_settlement |
| 00:51.7 | player | SANJINDAO_PROMPT | UNKNOWN | A later optional-action node appears while the same three Jin remain visible. | Later own action node can re-offer Sanjindao after an earlier PASS. | SANJINDAO / PASS / PASS | play continues toward Youjin | player_confirmed | sanjindao_terminal_settlement |
| 01:21.5 | player | YOUJIN_ANIMATION | UNKNOWN | You / 游 animation appears with three Jin still visibly in hand. | Youjin stage cannot be inferred from current Jin count alone. | UNKNOWN | Youjin stage established | direct_observation | youjin_universal_upgrade_predicate |
| 01:23.9 | player | PRE_DOUBLE_YOU_STATE | UNKNOWN | Immediately before the next upgrade, three Jin remain visible. | Pre-upgrade visual state recorded without inferring the universal trigger. | UNKNOWN | awaiting upgrade transition | direct_observation | youjin_universal_upgrade_predicate |
| 01:24.5 | system | DOUBLE_YOU_ANIMATION | UNKNOWN | Double-You / 双游 animation appears. | Replay enters Double-You. | UNKNOWN | Double-You transition | direct_observation | — |
| 01:25.5 | player | DOUBLE_YOU_ESTABLISHED | UNKNOWN | After the transition, two Jin are visibly retained. | Visible Jin count changed from three to two on this observed path. | UNKNOWN | Double-You active | direct_observation | youjin_universal_upgrade_predicate |
| 01:37.5 | system | SETTLEMENT_PAGE | UNKNOWN | Terminal page shows dealer base 30, Jin 2 fan, flower 1 fan, Double-You x8, winner +264 and loser -264. | Observed arithmetic is (30 + 2 + 1) x 8 = 264. | UNKNOWN | hand settled | direct_observation | — |

## Settlement

| Field | Value |
|---|---|
| Winner | 0 |
| Win type | DOUBLE_YOU |
| Fan | 3 |
| Multiplier | 8 |
| Dealer base | 30 |
| Net score | 264 |
| Scores before | UNKNOWN |
| Scores after | UNKNOWN |
| Next dealer | UNKNOWN |
| Evidence | direct_observation |
| Unknown rules | double_you_next_dealer |

Settlement notes:
- Direct settlement evidence confirms (30 + 3) x 8 = 264.
- Exact pre/post total scores and next dealer are not archived here and remain UNKNOWN.

## Notes

- This timeline is reconstructed only from already archived reviewed observations; missing opening/mid-hand details are not invented.
- Sanjindao prompt identity at 43.7s/51.7s uses player confirmation because the declaration label is partly obscured.

> JSON is the canonical machine-readable record. This Markdown file is a deterministic review view; UNKNOWN fields must remain UNKNOWN.
