# Special Settlement Capture Protocol V0.1

Purpose: close Issues #1 / #2 / #4 / #5 with direct target-room evidence instead of inference.

This protocol is intentionally narrower than full-match recording. A useful capture only needs to preserve the complete causal chain around one target special event.

## Universal capture window

For every target event, preserve all of the following in one continuous recording when possible:

1. **Pre-trigger state**
   - hand index;
   - current dealer;
   - both scores;
   - current dealer base / consecutive-dealer context if visible or reconstructable;
   - gold tile;
   - player's concealed hand and exposed melds;
   - flowers;
   - opponent's relevant exposed melds;
   - remaining wall if visible.

2. **Trigger state**
   - the exact draw / flower replacement / kong / discard that created the special window;
   - the complete prompt, including all visible buttons;
   - enough hand area to verify structural eligibility;
   - no edits between trigger and declaration.

3. **Decision**
   - DECLARE/HU/PASS action;
   - if PASS, preserve the next state long enough to prove whether the same or a later prompt can reappear;
   - if DECLARE/HU, keep recording through the terminal page.

4. **Settlement page**
   - winner / loser;
   - displayed fan total and any itemized fan lines;
   - displayed multiplier if present;
   - score delta or both scores before and after;
   - any special-outcome text;
   - dealer marker on the settlement page if shown.

5. **Next-hand state**
   - next dealer;
   - next hand number;
   - both starting scores after settlement.

Do not crop away the score/dealer/status area while recording the terminal sequence.

## Evidence fields

Every reviewed target event should fill the companion JSON template.

Minimum required fields for a **terminal CONFIRMED settlement candidate**:

- issue number;
- evidence ID;
- source SHA-256;
- source session / file label;
- hand index;
- timestamps for pre-trigger, prompt, decision, settlement and next-hand state;
- dealer seat;
- winner seat;
- scores before;
- scores after;
- observed net transfer;
- displayed fan, or explicit null if the room does not show it;
- displayed multiplier, or explicit null;
- next dealer;
- exact special outcome;
- evidence level;
- reviewer notes.

Never replace an unreadable value with 0 or a guessed multiplier.

## #1 Qiangjin

Need **two different evidence goals**.

### A. Eligibility predicate evidence

At the moment Qiangjin appears, preserve:

- complete concealed hand;
- exposed melds;
- flowers;
- gold tile;
- whether the trigger was opening check, normal own draw, flower replacement completion or kong-tail draw;
- just-received tile if applicable;
- exact prompt.

This is required before replacing `working_qiangjin_eligible()` with a target-room predicate.

### B. Terminal settlement evidence

After clicking Qiangjin/Hu, preserve:

- settlement page;
- fan lines;
- multiplier;
- before/after scores;
- next dealer.

A prompt without a terminal click cannot close the settlement unknowns.

## #2 Sanjindao

The timing/PASS behavior is already confirmed. New evidence should focus on a **real terminal declaration**.

At declaration time preserve:

- all 3 playable gold tiles visible in hand;
- whether this is opening, 2→3 arrival, or a later re-prompt;
- current dealer and dealer base;
- other additive fan sources present in the winning hand.

After DECLARE preserve:

- terminal fan display;
- x3 display if the UI shows it;
- exact net score transfer;
- next dealer.

This closes whether normal fan is included before x3 and how dealer/payment flow works.

## #4 Rob-Kong Hu / Gang-Hu

Treat these as separate evidence families.

### A. Rob-Kong Hu

Must show:

- an existing PENG;
- the fourth tile arriving;
- attempted **ADD_KONG**;
- opponent's Rob-Kong Hu response;
- terminal settlement;
- whether the robbed kong contributes any kong fan;
- next dealer.

Do not use MING_GANG or AN_GANG as Rob-Kong evidence.

### B. Gang-Hu

Must show:

- completed kong kind;
- tail draw;
- winning declaration on that tail draw;
- settlement page;
- kong fan line;
- Hu multiplier / special line;
- net score;
- next dealer.

Record kong kind explicitly: MING_GANG / AN_GANG / ADDED_GANG.

## #5 Eight-Flower-You

Need one true target-room terminal declaration.

At trigger preserve:

- all 8 flowers;
- the DECLARE/PASS window;
- current dealer/base;
- gold count and any other additive fan sources, because stacking is currently unknown.

After DECLARE preserve:

- displayed fan total;
- displayed special name;
- multiplier if any;
- exact net transfer;
- next dealer.

Do not interpret the current project WORKING value of fixed 16 fan as target-room truth.

## Simultaneous-special evidence

If more than one special option appears to be eligible at the same node, do not crop to one button.

Preserve the full prompt and event order so the project can determine precedence among:
- Sanjindao;
- Qiangjin;
- Eight-Flower-You;
- ordinary Hu;
- kong-related Hu paths.

A single visible button is not enough to prove that another special was ineligible.

## Review / promotion rule

A reviewed clip may upgrade a rule to CONFIRMED only when:

- source identity is preserved;
- the trigger and decision are unambiguous;
- settlement accounting is internally consistent;
- no required field was guessed;
- the evidence is linked in RULE_EVIDENCE_MATRIX;
- a focused regression/golden fixture is added for any newly confirmed settlement formula.

Hand Timeline can be used to record the event sequence, but machine-generated Hint Alpha timeline drafts remain UNKNOWN until a human reviews the source.
