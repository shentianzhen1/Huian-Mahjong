"""Youjin structural analysis helpers.

This module owns no phase transitions. HuianRules keeps the public methods and
delegates here so the main rules engine remains focused on ordinary rule entry
points while Youjin structure/scoring helpers stay grouped together.
"""
from numbers import Integral

from huian._legacy import core
from huian._compat.qzcore.win_checker import winning_decompositions

from .context import HuContext, WinSource, YoujinStage
from .dealer_base import DEALER_WIN_MULTIPLIER
from .models import YoujinMeldDecomposition, YoujinMeldResult, YoujinScoreTerms
from .values import nonnegative_int


def is_youjin_ready_hand(rules, hand, gold_tile, open_melds=0):
    """Return whether a post-discard hand is structurally ready to enter Youjin."""
    rules._validate_hand(hand, gold_tile)
    nonnegative_int(open_melds, "open_melds")
    if open_melds > 5:
        raise ValueError("At most five melds")
    if gold_tile is None or hand.count(gold_tile) < 1:
        return False
    groups_needed = 5 - open_melds
    if len(hand) != groups_needed * 3 + 1:
        return False

    for tile in core.BASE_TILES:
        if tile == gold_tile or hand.count(tile) >= 4:
            continue
        splits = winning_decompositions(
            [*hand, tile], gold_tile, open_melds, max_solutions=64
        )
        if any(split["pair"] == (tile, "GOLD") for split in splits):
            return True
    return False


def analyze_youjin_melds(
        rules, hand, gold_tile, open_melds=0, max_decompositions=64):
    """Enumerate meld-only splits after reserving one roaming Jin."""
    rules._validate_hand(hand, gold_tile)
    nonnegative_int(open_melds, "open_melds")
    if open_melds > 5:
        raise ValueError("At most five melds")
    if (isinstance(max_decompositions, bool)
            or not isinstance(max_decompositions, Integral)
            or max_decompositions <= 0):
        raise ValueError("max_decompositions must be a positive integer")
    if not is_youjin_ready_hand(rules, hand, gold_tile, open_melds):
        return YoujinMeldResult(False, (), gold_tile, open_melds, False)

    found = {}
    truncated = False
    for sentinel in core.BASE_TILES:
        if sentinel == gold_tile or hand.count(sentinel) >= 4:
            continue
        splits = winning_decompositions(
            [*hand, sentinel], gold_tile, open_melds,
            max_solutions=max_decompositions + 1,
        )
        for split in splits:
            if split["pair"] != (sentinel, "GOLD"):
                continue
            groups = tuple(tuple(group) for group in split["groups"])
            key = tuple(sorted(groups))
            if key in found:
                continue
            found[key] = YoujinMeldDecomposition(groups=groups)
            if len(found) > max_decompositions:
                truncated = True
                break
        if truncated:
            break

    decompositions = tuple(
        found[key] for key in sorted(found)
    )[:max_decompositions]
    return YoujinMeldResult(
        legal=bool(decompositions),
        decompositions=decompositions,
        gold_tile=gold_tile,
        open_melds=open_melds,
        may_be_truncated=truncated,
    )


def youjin_entry_discards(rules, hand, gold_tile, open_melds=0):
    """Enumerate discards that leave the confirmed single-Youjin-ready shape."""
    rules._validate_hand(hand, gold_tile)
    nonnegative_int(open_melds, "open_melds")
    if open_melds > 5:
        raise ValueError("At most five melds")
    expected = (5 - open_melds) * 3 + 2
    if len(hand) != expected:
        return ()
    out = []
    for tile in sorted(set(hand)):
        candidate = list(hand)
        candidate.remove(tile)
        if is_youjin_ready_hand(rules, candidate, gold_tile, open_melds):
            out.append(tile)
    return tuple(out)


def can_youjin_kong_tail_ordinary_hu(
        rules, hand, gold_tile, open_melds=0, *, win_context):
    """Return whether a Youjin Kong-tail draw has a genuine ordinary Hu split."""
    if not isinstance(win_context, HuContext):
        raise TypeError("win_context must be HuContext")
    if win_context.source != WinSource.KONG_TAIL_DRAW:
        raise ValueError("Youjin Kong-tail ordinary Hu requires Kong-tail context")
    result = rules.analyze_hu(
        hand, gold_tile, open_melds,
        win_context=win_context,
        max_decompositions=64,
    )
    if not result.legal:
        return False
    winning_tile = win_context.winning_tile
    for decomposition in result.decompositions:
        pair = decomposition.pair
        roaming_pair = (
            pair.count("GOLD") == 1
            and pair.count(winning_tile) == 1
        )
        if not roaming_pair:
            return True
    return False


def can_youjin_upgrade_after_draw(rules, hand, gold_tile, open_melds=0):
    """Return whether the completed own draw can support the next You stage."""
    rules._validate_hand(hand, gold_tile)
    nonnegative_int(open_melds, "open_melds")
    if open_melds > 5:
        raise ValueError("At most five melds")
    expected = (5 - open_melds) * 3 + 2
    if len(hand) != expected or gold_tile is None or gold_tile not in hand:
        return False
    after_gold_discard = list(hand)
    after_gold_discard.remove(gold_tile)
    return is_youjin_ready_hand(
        rules, after_gold_discard, gold_tile, open_melds
    )


def youjin_score_terms(rules, stage, *, winner, dealer, winner_fan):
    """Return confirmed Youjin terms; fan aggregation and payer remain external."""
    try:
        stage = stage if isinstance(stage, YoujinStage) else YoujinStage(stage)
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid Youjin stage") from exc
    for name, value in (("winner", winner), ("dealer", dealer),
                        ("winner_fan", winner_fan)):
        nonnegative_int(value, name)
    if winner not in (0, 1) or dealer not in (0, 1):
        raise ValueError("winner and dealer must be seat 0 or 1")
    if stage not in rules.YOUJIN_MULTIPLIERS:
        raise ValueError("Score terms require Youjin, Double-You or Triple-You")
    return YoujinScoreTerms(
        stage=stage,
        youjin_multiplier=rules.YOUJIN_MULTIPLIERS[stage],
        dealer_multiplier=DEALER_WIN_MULTIPLIER,
        winner_fan=winner_fan,
    )
