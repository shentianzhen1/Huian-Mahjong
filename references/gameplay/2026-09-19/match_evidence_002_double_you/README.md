# match_evidence_002 — opening three-gold continuation and terminal Double-You

Date reviewed: 2026-09-19  
Source: user-uploaded `14.mp4` (binary intentionally not committed)  
SHA256: `f24898ecee56803c09bead267150a590143c043941d3287f436ed6e89930f51d`  
Duration: ~106.99 s  
Geometry: 1046×480

All player/room identifiers are intentionally omitted.

## Direct observations

- ~0 s: hand 8/8 replay begins with the bottom player visibly holding **three gold tiles** (three highlighted SOUTH tiles). Play continues.
- ~81.5 s: a **You / 游** animation appears while those **three gold tiles are still visibly in hand**.
- ~83.9 s: immediately before the next upgrade, the hand still visibly contains the three gold tiles.
- ~84.5–85.5 s: **Double-You / 双游** animation appears; after the transition the visible hand contains **two gold tiles**.
- ~95–100 s: terminal settlement page shows:
  - dealer/current base: **30**
  - **gold 2 fan**
  - **flower 1 fan**
  - **Double-You ×8**
  - winner **+264**
  - loser **-264**

The arithmetic is exact:

```text
(30 + 2 + 1) × 8 = 264
```

## Rule consequences

### Sanjindao / 三金倒

This replay is consistent with the already documented opening branch: a hand may begin the first actionable state with three golds and continue after declining the optional Sanjindao result.

Therefore the project must not encode Sanjindao as *only* "a normal in-hand draw changed 2 gold -> 3 gold".

The one-shot entry has two evidence-backed forms:

1. **opening check** after opening flower replacement/open-gold is complete, when the current acting player already has **3+ gold**;
2. **mid-hand third-gold arrival**, when a valid draw changes the player from 2 gold to exactly 3.

PASS/continue permanently closes Sanjindao for that hand. Merely still holding 3 gold later, or later reaching a fourth gold, must not reopen it.

The replay UI does not preserve the original Sanjindao prompt, so it is evidence for the continued-play state, not a direct screenshot of the DECLARE/PASS popup.

### Youjin / 游金 chain

The Youjin stage is **not determined by current gold count**.

This replay directly shows **Youjin while three gold tiles remain in hand**. It then reaches Double-You and terminates with two gold tiles.

Therefore these old simplifications are invalid:

- "Youjin means exactly one gold remains";
- "Double-You means exactly two golds";
- "upgrade stages are never associated with a gold leaving the hand".

Gold count remains an independent fan term (+1 fan per gold). The exact trigger/upgrade predicate is still a state-machine evidence task and should not be replaced by a new gold-count heuristic.

### Double-You / 双游

This is the first archived target-room terminal **Double-You ×8** settlement.

It directly confirms:

- multiplier = **×8**;
- winner fan is added to current dealer base before the ×8 multiplier;
- two retained golds contribute **2 fan**;
- one flower contributes **1 fan**;
- no additional dealer ×2 is applied.

## What remains unknown

- exact universal predicate for entering Youjin / upgrading to Double-You / Triple-You;
- whether the observed 3-gold -> 2-gold transition is a required Double-You mechanism or only one legal path;
- complete cancellation/response windows;
- Sanjindao terminal payment/dealer flow.

