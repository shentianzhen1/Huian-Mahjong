"""Stable, ruleset-neutral contracts for Mahjong variants.

These contracts describe boundaries only.  They intentionally do not assume a
player count, tile set, gold/wildcard convention, scoring system or opening
procedure.
"""
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class MahjongRulesPlugin(Protocol):
    """Rules service consumed by a deterministic game environment."""

    variant_id: str

    def validate_state(self, state: Any) -> None:
        """Reject an impossible state without mutating it."""

    def action_report(self, state: Any) -> Any:
        """Return known actions and explicitly unresolved alternatives."""

    def authorize_action(self, state: Any, action: Any) -> None:
        """Reject actions outside the supported legal action set."""

    def reward(self, state: Any) -> list[int]:
        """Return terminal rewards in seat order."""


@runtime_checkable
class MahjongOpeningPlugin(Protocol):
    """Variant-owned deterministic opening procedure."""

    variant_id: str

    def plan_opening(self, wall: list[str], dealer: int, dice_total: int) -> Any:
        """Produce an auditable opening plan without mutating the input wall."""