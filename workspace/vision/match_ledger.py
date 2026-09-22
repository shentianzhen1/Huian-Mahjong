"""Human-readable public hand/match ledger views.

HandTimeline JSON remains the canonical evidence record. This module only
renders deterministic Chinese review views and a lightweight match index.
UNKNOWN stays explicit and no rule/scoring values are invented.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from huian.evidence.timeline import (
    HandContext,
    HandSettlement,
    HandTimeline,
)
from workspace.vision.public_match_reconstruction import ReconstructedAction


SCHEMA_VERSION = "public_match_ledger_v0_1"

_HONOR_ZH = {
    "E": "东",
    "SOUTH": "南",
    "W": "西",
    "N": "北",
    "R": "中",
    "G": "发",
    "B": "白",
}

_STATE_ZH = {
    "NORMAL": "普通状态",
    "YOUJIN": "游金中",
    "DOUBLE_YOU": "双游中",
    "TRIPLE_YOU": "三游中",
    "UNKNOWN": "游金状态待确认",
}

_WIN_ZH = {
    "PINGHU": "平胡",
    "RON": "点炮胡",
    "ZIMO": "自摸",
    "SELF_DRAW": "自摸",
    "QIANGJIN": "抢金",
    "SANJINDAO": "三金倒",
    "YOUJIN": "游金",
    "DOUBLE_YOU": "双游",
    "TRIPLE_YOU": "三游",
    "ROB_KONG": "抢杠胡",
    "GANG_HU": "杠胡",
    "EIGHT_FLOWER_YOU": "八花游",
}


def tile_zh(tile_id: str | None) -> str:
    if not tile_id or tile_id == "UNKNOWN":
        return "未知牌"
    if tile_id in _HONOR_ZH:
        return _HONOR_ZH[tile_id]
    if len(tile_id) == 2 and tile_id[1].isdigit():
        rank = tile_id[1]
        if tile_id[0] == "M":
            return f"{rank}万"
        if tile_id[0] == "P":
            return f"{rank}筒"
        if tile_id[0] == "S":
            return f"{rank}条"
        if tile_id[0] == "F":
            return f"花{rank}"
    return tile_id


def _clock(seconds: float) -> str:
    minutes = int(seconds // 60)
    remainder = seconds - minutes * 60
    return f"{minutes:02d}:{remainder:04.1f}"


def _actor_zh(actor: str) -> str:
    return {
        "player": "我方",
        "opponent": "对手",
        "system": "系统",
        "unknown": "未知方",
    }.get(actor, actor)


def _seat_actor(seat: int | None, player_seat: int | None) -> str:
    if seat is None or player_seat is None:
        return "未知"
    return "我方" if seat == player_seat else "对手"


def _score_view(
    scores: tuple[int, int] | None,
    player_seat: int | None,
) -> str:
    if scores is None:
        return "未知"
    if player_seat is None:
        return f"座位0 {scores[0]} ｜ 座位1 {scores[1]}"
    opponent_seat = 1 - player_seat
    return f"我方 {scores[player_seat]} ｜ 对手 {scores[opponent_seat]}"


def _meld_zh(values: object) -> str:
    if not isinstance(values, (list, tuple)) or not values:
        return "副露牌待确认"
    return " ".join(tile_zh(str(value)) for value in values)


def _win_type_zh(value: object) -> str:
    if value is None or value == "":
        return "胡法待确认"
    text = str(value)
    return _WIN_ZH.get(text.upper(), text)


def _detail(event, key: str):
    return event.details.get(key) if isinstance(event.details, dict) else None


def _simple_event_text(event) -> str:
    actor = _actor_zh(event.actor)
    kind = event.kind.upper()

    if kind == "HAND_START":
        return "开局"
    if kind == "OPEN_GOLD":
        return f"开金：{tile_zh(event.tile)}"
    if kind == "DISCARD":
        return f"{actor}出牌：{tile_zh(event.tile)}"
    if kind == "CHI":
        claimed = _detail(event, "claimed_tile")
        meld = _detail(event, "meld")
        return (
            f"{actor}吃：{_meld_zh(meld)}"
            f"（吃 {tile_zh(str(claimed)) if claimed else '未知牌'}）"
        )
    if kind == "PENG":
        claimed = _detail(event, "claimed_tile")
        meld = _detail(event, "meld")
        return (
            f"{actor}碰：{_meld_zh(meld)}"
            f"（碰 {tile_zh(str(claimed)) if claimed else '未知牌'}）"
        )
    if kind == "MING_GANG":
        meld = _detail(event, "meld")
        return f"{actor}明杠：{_meld_zh(meld)}"
    if kind == "ADD_KONG":
        return f"{actor}补杠：{tile_zh(event.tile)}"
    if kind == "AN_GANG":
        return f"{actor}暗杠：{tile_zh(event.tile)}"
    if kind == "YOUJIN_STATE":
        state = _detail(event, "state") or event.result or "UNKNOWN"
        return f"{actor}状态：{_STATE_ZH.get(str(state), str(state))}"
    if kind in {"YOUJIN_ANIMATION", "DOUBLE_YOU_ANIMATION", "TRIPLE_YOU_ANIMATION"}:
        state = {
            "YOUJIN_ANIMATION": "游金",
            "DOUBLE_YOU_ANIMATION": "双游",
            "TRIPLE_YOU_ANIMATION": "三游",
        }[kind]
        return f"{actor}出现{state}动画"
    if kind == "HU":
        subtype = _detail(event, "subtype") or event.result
        return f"{actor}胡牌：{_win_type_zh(subtype)}"
    if kind in {"SETTLEMENT", "SETTLEMENT_PAGE"}:
        subtype = _detail(event, "subtype") or _detail(event, "win_type")
        if subtype:
            return f"结算：{_win_type_zh(subtype)}"
        return "出现结算页面"
    if kind == "UNKNOWN_ACTION":
        reasons = _detail(event, "reconstruction_unknown_reasons")
        if isinstance(reasons, (list, tuple)) and reasons:
            return f"{actor}动作待确认（{', '.join(str(x) for x in reasons)}）"
        return f"{actor}动作待确认"
    if kind == "EVIDENCE_CONFLICT":
        return f"{actor}公开动作证据冲突"
    if event.tile:
        return f"{actor} {event.kind}：{tile_zh(event.tile)}"
    return f"{actor} {event.kind}"


def _audit_suffix(event) -> str:
    grade = _detail(event, "reconstruction_evidence_grade")
    confidence = _detail(event, "reconstruction_confidence")
    bits = [f"timeline={event.evidence_level}"]
    if grade:
        bits.append(f"machine={grade}")
    if confidence is not None:
        bits.append(f"confidence={confidence}")
    if event.evidence_refs:
        bits.append("refs=" + ",".join(event.evidence_refs))
    return " [" + " | ".join(bits) + "]"


def render_hand_ledger_zh(
    timeline: HandTimeline,
    *,
    audit: bool = False,
    total_hands: int = 8,
) -> str:
    if total_hands < timeline.hand_index:
        raise ValueError("total_hands cannot be smaller than hand_index")

    context = timeline.context
    dealer_actor = _seat_actor(context.dealer, context.player_seat)
    gold = tile_zh(context.gold_tile) if context.gold_tile else "待确认"

    lines = [
        f"## 第 {timeline.hand_index}/{total_hands} 局",
        f"庄家：{dealer_actor} ｜ 金：{gold}",
        f"开局比分：{_score_view(context.initial_scores, context.player_seat)}",
        "",
    ]

    for event in timeline.events:
        text = f"{_clock(event.timestamp_seconds)}  {_simple_event_text(event)}"
        if audit:
            text += _audit_suffix(event)
        lines.append(text)

    settlement = timeline.settlement
    if (
        settlement.winner is not None
        or settlement.win_type is not None
        or settlement.scores_after is not None
        or settlement.net_score is not None
    ):
        lines.extend(["", "结算："])
        if settlement.winner is not None:
            lines.append(
                f"- 赢家：{_seat_actor(settlement.winner, context.player_seat)}"
            )
        lines.append(f"- 胡法：{_win_type_zh(settlement.win_type)}")
        if settlement.fan is not None:
            lines.append(f"- 番：{settlement.fan}")
        if settlement.multiplier is not None:
            lines.append(f"- 倍率：×{settlement.multiplier}")
        if settlement.dealer_base is not None:
            lines.append(f"- 当前庄底：{settlement.dealer_base}")
        if settlement.net_score is not None:
            sign = "+" if settlement.net_score > 0 else ""
            lines.append(f"- 赢家净分：{sign}{settlement.net_score}")
        if settlement.scores_after is not None:
            lines.append(
                f"- 结算后比分：{_score_view(settlement.scores_after, context.player_seat)}"
            )
        if settlement.next_dealer is not None:
            lines.append(
                f"- 下一庄：{_seat_actor(settlement.next_dealer, context.player_seat)}"
            )
        if settlement.unknown_rules:
            lines.append("- 仍待确认：" + "、".join(settlement.unknown_rules))
    elif not any(event.kind.upper() in {"SETTLEMENT", "SETTLEMENT_PAGE"} for event in timeline.events):
        lines.extend(["", "结算：待确认"])

    return "\n".join(lines).rstrip() + "\n"


@dataclass(frozen=True)
class MatchLedgerIndex:
    evidence_ids: tuple[str, ...]
    hand_indexes: tuple[int, ...]
    missing_hands: tuple[int, ...]
    score_continuity_issues: tuple[str, ...]
    complete: bool
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "evidence_ids": list(self.evidence_ids),
            "hand_indexes": list(self.hand_indexes),
            "missing_hands": list(self.missing_hands),
            "score_continuity_issues": list(self.score_continuity_issues),
            "complete": self.complete,
        }


def build_match_ledger_index(
    timelines: Iterable[HandTimeline],
    *,
    total_hands: int = 8,
) -> MatchLedgerIndex:
    hands = sorted(tuple(timelines), key=lambda item: item.hand_index)
    indexes = tuple(item.hand_index for item in hands)
    if len(set(indexes)) != len(indexes):
        raise ValueError("duplicate hand_index in match ledger")
    if any(index < 1 or index > total_hands for index in indexes):
        raise ValueError("hand_index outside match ledger range")

    expected = set(range(1, total_hands + 1))
    missing = tuple(sorted(expected - set(indexes)))
    issues: list[str] = []

    for previous, current in zip(hands, hands[1:]):
        after = previous.settlement.scores_after
        before = current.context.initial_scores
        if after is not None and before is not None and after != before:
            issues.append(
                f"hand_{previous.hand_index}_scores_after"
                f"_!=_hand_{current.hand_index}_initial_scores"
            )

    return MatchLedgerIndex(
        evidence_ids=tuple(item.evidence_id for item in hands),
        hand_indexes=indexes,
        missing_hands=missing,
        score_continuity_issues=tuple(issues),
        complete=not missing and not issues,
    )


def render_match_ledger_zh(
    timelines: Iterable[HandTimeline],
    *,
    audit: bool = False,
    total_hands: int = 8,
) -> str:
    hands = sorted(tuple(timelines), key=lambda item: item.hand_index)
    index = build_match_ledger_index(hands, total_hands=total_hands)

    lines = [
        "# 惠安二人麻将整局流水",
        "",
        f"已记录：{len(hands)}/{total_hands} 局",
    ]
    if index.missing_hands:
        lines.append(
            "缺失局：" + "、".join(str(value) for value in index.missing_hands)
        )
    if index.score_continuity_issues:
        lines.append(
            "分数连续性异常：" + "、".join(index.score_continuity_issues)
        )

    if hands:
        first_scores = hands[0].context.initial_scores
        if first_scores is not None:
            lines.append(
                "起始比分："
                + _score_view(first_scores, hands[0].context.player_seat)
            )
        last_scores = hands[-1].settlement.scores_after
        if last_scores is not None:
            lines.append(
                "当前/最终比分："
                + _score_view(last_scores, hands[-1].context.player_seat)
            )

    lines.append("")
    for position, hand in enumerate(hands):
        if position:
            lines.extend(["", "---", ""])
        lines.append(
            render_hand_ledger_zh(
                hand,
                audit=audit,
                total_hands=total_hands,
            ).rstrip()
        )
    lines.append("")
    return "\n".join(lines)


def hand_timeline_draft_from_actions(
    *,
    evidence_id: str,
    hand_index: int,
    actions: Iterable[ReconstructedAction],
    context: HandContext,
    settlement: HandSettlement | None = None,
    source_sha256: str | None = None,
    duration_seconds: float | None = None,
    geometry: str | None = None,
    source_label: str | None = None,
    notes: tuple[str, ...] = (),
) -> HandTimeline:
    """Build the UNKNOWN-only HandTimeline draft used by the ledger.

    ReconstructedAction.to_timeline_event() deliberately keeps canonical
    evidence_level=unknown, even for machine DIRECT/CORROBORATED events.
    """
    ordered = sorted(tuple(actions), key=lambda item: item.timestamp_seconds)
    return HandTimeline(
        evidence_id=evidence_id,
        hand_index=hand_index,
        source_sha256=source_sha256,
        duration_seconds=duration_seconds,
        geometry=geometry,
        context=context,
        events=tuple(action.to_timeline_event() for action in ordered),
        settlement=settlement or HandSettlement(),
        source_label=source_label,
        notes=notes,
    )
