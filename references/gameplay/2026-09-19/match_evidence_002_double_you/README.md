# match_evidence_002 — opening three-gold continuation and terminal Double-You

Date reviewed: 2026-09-19  
Source: user-uploaded `14.mp4` (binary intentionally not committed)  
SHA256: `f24898ecee56803c09bead267150a590143c043941d3287f436ed6e89930f51d`  
Duration: ~106.99 s  
Geometry: 1046×480

All player/room identifiers are intentionally omitted.

## Direct observations

- ~0 s: hand 8/8 replay begins with the bottom player visibly holding **three gold tiles** (three highlighted SOUTH tiles). Play continues.
- ~43.7 s and again ~51.7 s: while those same **three gold tiles** remain visible, the replay shows an optional-action node with a visible **PASS / 过** button. The replay controller partly covers the declaration button text, so the button label itself is not independently readable from the recording; the player clarification identifies these repeated nodes as Sanjindao choices. This is the key correction: passing one Sanjindao prompt does **not** permanently close Sanjindao for the hand.
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

This replay plus the player's clarification corrects the previous "one-shot for the whole hand" model.

Confirmed behavior now is:

1. **Opening check** after opening flower replacement/open-gold is complete can offer Sanjindao when the current actor already has **3+ gold**.
2. A normal mid-hand **2 gold -> 3 gold** arrival can offer Sanjindao.
3. Choosing **PASS / 过 closes only that current prompt**. It does **not** permanently disable Sanjindao for the rest of the hand.
4. A later own draw while the player still holds the same **3 gold** can offer Sanjindao again. The replay contains repeated PASS nodes while the same three highlighted SOUTH tiles remain visible.
5. Passing Sanjindao does not remove ordinary Hu or the Youjin-family branch; this same hand later enters Youjin and terminates as Double-You.

Player clarification on 2026-09-20 closes the former four-gold edge: the opened gold indicator is itself one of the four physical copies and stays in the public indicator area, so it cannot later be drawn. Only three playable gold copies exist; four playable golds are physically impossible.

Multiplier evidence is separate from terminal-settlement evidence:
- Sanjindao multiplier = **×3** is confirmed/adopted from player confirmation plus the in-game rule page.
- This replay does **not** contain a terminal Sanjindao settlement page, so payer/base/fan/dealer-flow details remain unresolved.

### Youjin / 游金 chain

The Youjin stage is **not determined by current gold count**.

This replay directly shows **Youjin while three gold tiles remain in hand**. It then reaches Double-You and terminates with two gold tiles. Because the player had already passed Sanjindao earlier, it also directly supports that a Sanjindao PASS does not block the later Youjin/Double-You route.

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

