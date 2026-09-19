# Match evidence 001 — complete 8-hand Huian 2-player replay evidence (2026-09-19)

This directory records one complete target-room match supplied as eight replay videos.
The raw videos are not committed here; hashes and settlement facts are preserved so the
analysis is reproducible against the original uploads.

Target-room settings visible on settlement pages: **惠安2人 / 单金不平胡 / 无托管**.
Players are anonymized as **seat_0** and **seat_1**. Both begin at **1000**.

## Source files

| Hand | Upload | Duration | Resolution | SHA256 |
|---|---|---:|---|---|
| 1 | 3.mp4 | 62.379s | 1046×480 | `1560c1e04a632f07dc5f53947ba3080ed93ff927a7bd028a457f3415b0bc69a3` |
| 2 | 4.mov | 133.517s | 960×448 | `bddbad4e396e31136988b5c9254cbf230290112a4a0111dec85f197cee75d053` |
| 3 | 5.mov | 204.793s | 960×448 | `bdec79b6ba7252126524046ee2c48aa086b40b4ae5224c78b902df32873def75` |
| 4 | 9.mov | 112.069s | 1046×480 | `7f9a338589a86c05c3b89e854d2b8c6aacf3cabb7be4d0d48b80dae76dadfe15` |
| 5 | 10.mp4 | 144.551s | 960×448 | `02f7874493d224b290d7957c62b552e877ec7dacd3a712ee9fbdc3c81225e245` |
| 6 | 11.mp4 | 94.344s | 1046×480 | `d50f6722982adb0fdfe3ad8e0b9d1f4155defcfbefebd77e8f10cbc4d3b19a78` |
| 7 | 12.mp4 | 142.413s | 960×448 | `4043cc011c1b12d1ade88afd98c30e77dca8b364b7d0b8c595b3ca16bcdb7757` |
| 8 | 13.mp4 | 98.862s | 1046×480 | `4333a11966bd364f3388b2bf3677900eed50faf6b0d6739cf9399e901de196fc` |

## Settlement timeline

Seat 0 = seat_0; seat 1 = seat_1.

| Hand | Dealer / displayed dealer base | Winner | Method | Winner fan | Formula | Net | Scores after |
|---|---|---|---|---:|---|---:|---|
| 1 | seat_0 / 10 | seat_0 | 自摸×2 | 金2 + 花1 = 3 | (10+3)×2 | +26 | 1026 / 974 |
| 2 | seat_0（连2）/ 15 | seat_1 | 游金×4 | 金1 + 花1 = 2 | (15+2)×4 | +68 | 958 / 1042 |
| 3 | seat_1 / 10 | seat_0 | 自摸×2 | 花1 = 1 | (10+1)×2 | +22 | 980 / 1020 |
| 4 | seat_0 / 10 | seat_0 | 自摸×2 | 花2 = 2 | (10+2)×2 | +24 | 1004 / 996 |
| 5 | seat_0（连2）/ 15 | seat_0 | 游金×4 | 金2 + 花2 = 4 | (15+4)×4 | +76 | 1080 / 920 |
| 6 | seat_0（连3）/ 20 | seat_0 | 平胡×1 | 花1 + 刻1 + 杠3 = 5 | (20+5)×1 | +25 | 1105 / 895 |
| 7 | seat_0（连4）/ 25 | seat_1 | 平胡×1 | 花2 + 刻1 = 3 | (25+3)×1 | +28 | 1077 / 923 |
| 8 | seat_1 / 10 | seat_0 | 自摸×2 | 金1 + 花3 + 刻1 + 杠3 = 8 | (10+8)×2 | +36 | **1113 / 887** |

All eight hands exactly satisfy:

`actual net = (current dealer displayed settlement base + winner fan) × method multiplier`

The losing player's displayed fan is not subtracted.

## Rules materially strengthened by this match

### First sitting dealer settlement base is 10, not 5

The prior player wording “坐庄底分5分，连庄+5” had an unresolved mapping to the UI.
This match resolves it operationally:

- non-dealer own displayed base = 5;
- a player who newly becomes dealer displays/settles with current dealer base = **10**;
- consecutive dealer hands add **+5**: 10 → 15 → 20 → 25 in this match;
- when the dealer loses, the opponent becomes dealer and resets to **10**, not 5.

Therefore simulator settlement must use 10 for the first sitting dealer. This replay by itself does not reach the end of a maximum dealer streak; older target evidence reaches dealer base 35. Player confirmation on 2026-09-19 later resolves that boundary: while the same dealer keeps the seat, there is no cap and each continuation adds +5 until the fixed 8-hand match ends; if the dealer loses, the new dealer resets to 10.

### Youjin ×4 with two gold tiles

Hand 5 ends as **游金×4** while the winner settlement explicitly lists **金牌2番 + 花牌2番**.
Thus simple Youjin is not synonymous with “exactly one gold in hand”; a hand may settle as Youjin
while carrying two gold tiles, and both gold tiles still contribute their ordinary +1 fan each.

This is also a second direct target-room Youjin ×4 settlement after the archived +100 sample.

### Ordinary self-draw with two gold tiles

Hand 1 settles ordinary **自摸×2** with **金牌2番 + 花牌1番**, giving
`(dealer base 10 + fan 3) ×2 = 26`. This directly reinforces the already adopted
“two gold may ordinary self-draw” rule.

### Suited concealed kong = 3 fan

In hand 6, immediately before the kong the acting player's separated drawn suited tile matches
three identical suited tiles already concealed in hand. The replay then shows the **杠** declaration;
the settlement explicitly lists **杠牌3番**. This upgrades the suited `AN_GANG` 3-fan table cell
from rule-page-only evidence to direct target-room confirmation.

Hands 7/8 also display 3-fan kong components, but hand 6 is the clearest action-to-settlement sample.

## What this match does not resolve

No Qiangjin, Sanjindao declaration, Double-You final settlement, Triple-You final settlement,
Eight-Flower-You declaration, Rob-Kong Hu, or Gang-Hu occurs in these eight hands.
This replay alone does not establish the dealer-base cap, but the later 2026-09-19 player confirmation does: no cap during a continuous dealer streak, +5 per keep until hand 8; dealer change resets to 10.

Structured regression data: `tests/fixtures/settlement_match_evidence_001_8hands.json`.
