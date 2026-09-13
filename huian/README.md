# Huian M1: explicit rules boundary

Update: [M2 Environment](environment/README.md) now provides atomic, fully accounted
mid-hand transitions through `HuianEnvironment` / `HuianGameState`. The M1 legacy
entry points described below remain supported. Neither entry point runs a complete game yet.

M1 adds a rules service and a conservative Environment adapter. All files under
`legacy_code/` remain unchanged. No Simulator or full-game entry point is enabled.
The bundled legacy packages are loaded from their checked project paths, without
adding directories to `sys.path`; existing `qzenv.Action` identities are preserved.

## Usage from the repository root

```python
from huian import HuianRules, HuianRulesAdapter, RulesConfig

rules = HuianRules(RulesConfig("current_dealer_plus_winner_v1"))
result = rules.settle(
    winner=1, current_dealer_base=15, winner_fan=7, multiplier=4
)
assert result.rewards == (-88, 88)
assert result.status == "HIGH_CONFIDENCE"

# Import huian first when legacy directories are not already on Python's path.
from qzenv import QuanzhouEnvironment
environment = QuanzhouEnvironment(HuianRulesAdapter(rules))
```

`settle` accepts an externally verified winner fan total. It does not calculate
that total, extrapolate dealer bases, or supply any default room multiplier.
The formula requires explicit opt-in and retains HIGH_CONFIDENCE status pending
a third real settlement. Test values A/B are transcribed from RULE_STATUS.md;
they do not constitute new screenshot evidence or new rule confirmation.

`can_win` and `ting_tiles` check ordinary structural wins only. They do not decide
special-win eligibility or phase permissions. `meld_options` returns local
composition candidates, not all legal actions. Gold is excluded from every Chi
candidate as well as Peng and kong candidates. `calculate_fan` explicitly raises
until the aggregation policy is implemented; it never falls back to legacy fan
totals or silently ignores flower groups.

Player clarification (2026-09-13): single-gold Pinghu is configurable and usually
disabled. Use `RulesConfig(single_gold_can_pinghu=True)` only for a room explicitly
allowing it; default False preserves the previously observed setting. Double-gold
Pinghu stays forbidden. Both ordinary Hu and Ting queries respect the setting;
M2 phase-level gold/special-state blocking is unchanged. Events record this option
with the other rule settings.

## Adapter scope

The adapter validates represented tile zones, meld composition, gold exclusions
and two-player zero-sum rewards. It supports DISCARD only in AFTER_CHI/AFTER_PENG,
with a matching latest meld, correct hand size, known gold, and no gold in the
acting hand. It blocks gold-related ambiguity. All other nonterminal phases raise
`UnknownRuleError`; a READY state after reset is deliberately not playable yet.
Terminal states return no actions. Always use the default `step(..., strict=True)`.

This is partial-state validation, not complete 144-tile conservation: the legacy
state cannot yet represent opened indicator ownership and all claim history.
It also lacks per-player Youjin history. Unknown phases must not be caught and
converted into PASS, an empty legal-action list, or an artificial drawn hand.
Complete phase transitions, atomic failure handling and full-game loop guards
belong to M2/M3. Legacy `strict=False` remains an unsafe testing escape hatch.

## Uncertainty registry

`rules/config.py:UNKNOWN_RULES` tracks the unresolved questions from RULE_STATUS
and the migration audit. It includes rob-kong, Sanjindao, Youjin entry/upgrades,
opponent permissions/cancellation, room multipliers, flower-open-gold, Tianhu,
Tianting, PASS, match ties, extended dealer bases, flower groups, fan edge cases,
honor pung fan, indicator accounting, deal/replacement order, the exact 16-tile
boundary, added-kong details, decomposition scoring and three-plus-gold Pinghu.
Configuration does not promote an uncertain rule to confirmed evidence.

## Tests

Run each command in its indicated directory using an available Python interpreter:

```text
repository root:                    python -B -m unittest discover -s tests -v
legacy_code/core_v0.1.1:             python -B -m unittest discover -s tests -v
legacy_code/environment_v0.1:        python -B -m unittest discover -s tests -v
```

Verified on 2026-09-13 with Python 3.12.14: Huian 22/22, Core 9/9,
Environment 9/9. The legacy score-34 test remains a compatibility test only.
The new tests cover A/B settlement, UNKNOWN blocking, gold constraints, fifth
copies, negative wall counts, legal action enforcement, seed reproducibility,
clone/rollback and zero-sum validation. No complete-game simulation is claimed.
