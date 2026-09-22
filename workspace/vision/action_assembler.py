"""Temporal assembly of public Vision observations into auditable actions.

The assembler consumes already-stable RawObservation facts. It does not inspect
pixels and does not ask Rules whether an action is legal. It only correlates
public evidence by actor, timestamp, and the existing fail-closed
reconstructors.

Timing values are observer heuristics, not Mahjong rules. Callers must choose
them for the capture/replay mode being used.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from workspace.vision.public_match_reconstruction import (
    EvidenceGrade,
    ObservationKind,
    PublicActionKind,
    RawObservation,
    ReconstructedAction,
    direct_action,
    reconstruct_add_kong,
    reconstruct_claimed_meld,
)


_DIRECT_KINDS = frozenset({
    ObservationKind.HAND_START,
    ObservationKind.GOLD,
    ObservationKind.DISCARD,
    ObservationKind.YOUJIN_STATE,
    ObservationKind.HU,
    ObservationKind.SETTLEMENT,
})


@dataclass(frozen=True)
class AssemblyConfig:
    """Capture/replay timing heuristics, deliberately separate from Rules."""

    claim_window_seconds: float
    assembly_delay_seconds: float

    def __post_init__(self) -> None:
        if self.claim_window_seconds <= 0:
            raise ValueError("claim_window_seconds must be positive")
        if self.assembly_delay_seconds < 0:
            raise ValueError("assembly_delay_seconds must be nonnegative")
        if self.assembly_delay_seconds > self.claim_window_seconds:
            raise ValueError(
                "assembly_delay_seconds cannot exceed claim_window_seconds"
            )


@dataclass
class _Pending:
    sequence: int
    observation: RawObservation
    consumed: bool = False


def _capture_scope(observation: RawObservation) -> tuple[str | None, int | None]:
    """Require explicit source lineage; never infer it from timestamps or UI position."""
    session = observation.details.get("source_session")
    epoch = observation.details.get("stream_epoch")
    if session is not None and (not isinstance(session, str) or not session):
        raise ValueError("source_session must be a nonempty string or None")
    if epoch is not None and (
        isinstance(epoch, bool) or not isinstance(epoch, int) or epoch < 0
    ):
        raise ValueError("stream_epoch must be a nonnegative integer or None")
    return session, epoch


class TemporalActionAssembler:
    """Correlate DISCARD / HAND_DELTA / MELD_DELTA into public actions.

    Input timestamps must be nondecreasing. This keeps replay/live behavior
    deterministic and makes expiration explicit. Upstream observers may have
    different detection latency; assembly_delay_seconds provides a short grace
    period before unresolved melds are judged.
    """

    def __init__(self, config: AssemblyConfig):
        self.config = config
        self._pending: list[_Pending] = []
        self._sequence = 0
        self._watermark = 0.0
        self._seen_any = False
        self._scope: tuple[str | None, int | None] | None = None

    @property
    def watermark(self) -> float:
        return self._watermark

    def ingest(self, observation: RawObservation) -> tuple[ReconstructedAction, ...]:
        """Add one stable observation and return newly assembled actions."""
        timestamp = observation.timestamp_seconds
        scope = _capture_scope(observation)
        scope_changed = self._scope is not None and scope != self._scope
        # A different recorded session may restart its own relative clock at zero.
        # Within one capture scope, timestamps must remain monotonic.
        if self._seen_any and timestamp < self._watermark and not scope_changed:
            raise ValueError(
                "TemporalActionAssembler requires nondecreasing observation timestamps"
            )
        output: list[ReconstructedAction] = []
        if self._scope is None:
            self._scope = scope
        elif scope_changed:
            output.extend(self._close_capture_scope(next_scope=scope))
            self._scope = scope

        self._seen_any = True
        self._watermark = timestamp

        pending = _Pending(self._sequence, observation)
        self._sequence += 1
        self._pending.append(pending)

        if observation.kind in _DIRECT_KINDS:
            output.append(direct_action(observation))

        output.extend(self._resolve_ready_melds())
        output.extend(self._expire_unresolved_melds())
        self._prune()
        return tuple(output)

    def ingest_many(
        self,
        observations: Iterable[RawObservation],
    ) -> tuple[ReconstructedAction, ...]:
        output: list[ReconstructedAction] = []
        for observation in observations:
            output.extend(self.ingest(observation))
        return tuple(output)

    def advance_time(self, timestamp_seconds: float) -> tuple[ReconstructedAction, ...]:
        """Advance the assembly watermark when no new visual fact arrives."""
        if timestamp_seconds < self._watermark:
            raise ValueError("cannot move assembler watermark backwards")
        self._seen_any = True
        self._watermark = float(timestamp_seconds)
        output = list(self._resolve_ready_melds())
        output.extend(self._expire_unresolved_melds())
        self._prune()
        return tuple(output)

    def flush(self) -> tuple[ReconstructedAction, ...]:
        """Expire every unresolved meld while preserving UNKNOWN semantics."""
        if not self._pending:
            return ()
        latest_meld = max(
            (
                item.observation.timestamp_seconds
                for item in self._pending
                if not item.consumed
                and item.observation.kind == ObservationKind.MELD_DELTA
            ),
            default=self._watermark,
        )
        return self.advance_time(
            max(
                self._watermark,
                latest_meld + self.config.claim_window_seconds + 1e-6,
            )
        )

    def _close_capture_scope(
        self,
        *,
        next_scope: tuple[str | None, int | None],
    ) -> list[ReconstructedAction]:
        """Expire incomplete melds and drop all prior candidates on a source/epoch change."""
        actions: list[ReconstructedAction] = []
        for item in self._pending:
            if item.consumed or item.observation.kind != ObservationKind.MELD_DELTA:
                continue
            anchor = item.observation
            related = [
                old.observation
                for old in self._pending
                if not old.consumed
                and old.observation.kind in {
                    ObservationKind.DISCARD,
                    ObservationKind.HAND_DELTA,
                }
                and abs(old.observation.timestamp_seconds - anchor.timestamp_seconds)
                <= self.config.claim_window_seconds
            ]
            unknown = self._ambiguous_action(
                anchor,
                reason="capture_scope_discontinuity",
                evidence=[anchor, *related],
            )
            actions.append(
                replace(
                    unknown,
                    details={
                        **unknown.details,
                        "previous_source_session": self._scope[0],
                        "previous_stream_epoch": self._scope[1],
                        "next_source_session": next_scope[0],
                        "next_stream_epoch": next_scope[1],
                    },
                )
            )
        self._pending.clear()
        return actions

    def _resolve_ready_melds(self) -> list[ReconstructedAction]:
        output: list[ReconstructedAction] = []
        for meld_item in list(self._pending):
            if meld_item.consumed:
                continue
            meld = meld_item.observation
            if meld.kind != ObservationKind.MELD_DELTA:
                continue
            if self._watermark < (
                meld.timestamp_seconds + self.config.assembly_delay_seconds
            ):
                continue

            resolved = self._resolve_meld(meld_item)
            if resolved is not None:
                action, consumed_sequences = resolved
                self._consume(consumed_sequences)
                output.append(action)
        return output

    def _resolve_meld(
        self,
        meld_item: _Pending,
    ) -> tuple[ReconstructedAction, set[int]] | None:
        meld = meld_item.observation

        add_kong_matches = self._candidate_add_kong_matches(meld_item)
        if len(add_kong_matches) == 1:
            action, hand_item = add_kong_matches[0]
            return action, {meld_item.sequence, hand_item.sequence}
        if len(add_kong_matches) > 1:
            return (
                self._ambiguous_action(
                    meld,
                    reason="multiple_add_kong_hand_delta_matches",
                    evidence=(
                        [meld]
                        + [hand.observation for _, hand in add_kong_matches]
                    ),
                ),
                {
                    meld_item.sequence,
                    *[hand.sequence for _, hand in add_kong_matches],
                },
            )

        claimed_matches = self._candidate_claimed_meld_matches(meld_item)
        if len(claimed_matches) == 1:
            action, discard_item, hand_item = claimed_matches[0]
            return action, {
                meld_item.sequence,
                discard_item.sequence,
                hand_item.sequence,
            }
        if len(claimed_matches) > 1:
            evidence = [meld]
            sequences = {meld_item.sequence}
            for _, discard_item, hand_item in claimed_matches:
                evidence.extend([discard_item.observation, hand_item.observation])
                sequences.update({discard_item.sequence, hand_item.sequence})
            return (
                self._ambiguous_action(
                    meld,
                    reason="multiple_claim_evidence_combinations",
                    evidence=evidence,
                ),
                sequences,
            )
        return None

    def _candidate_add_kong_matches(
        self,
        meld_item: _Pending,
    ) -> list[tuple[ReconstructedAction, _Pending]]:
        meld = meld_item.observation
        if not meld.details.get("previous_meld"):
            return []

        matches: list[tuple[ReconstructedAction, _Pending]] = []
        for hand_item in self._candidate_hand_deltas(meld):
            action = reconstruct_add_kong(hand_item.observation, meld)
            if action.kind == PublicActionKind.ADD_KONG:
                matches.append((action, hand_item))
        return matches

    def _candidate_claimed_meld_matches(
        self,
        meld_item: _Pending,
    ) -> list[tuple[ReconstructedAction, _Pending, _Pending]]:
        meld = meld_item.observation
        if meld.actor not in {"player", "opponent"}:
            return []

        other_actor = "opponent" if meld.actor == "player" else "player"
        discards = [
            item
            for item in self._pending
            if not item.consumed
            and item.observation.kind == ObservationKind.DISCARD
            and item.observation.actor == other_actor
            and item.observation.timestamp_seconds <= meld.timestamp_seconds
            and (
                meld.timestamp_seconds - item.observation.timestamp_seconds
                <= self.config.claim_window_seconds
            )
        ]
        hands = self._candidate_hand_deltas(meld)

        matches: list[tuple[ReconstructedAction, _Pending, _Pending]] = []
        for discard_item in discards:
            for hand_item in hands:
                action = reconstruct_claimed_meld(
                    discard_item.observation,
                    hand_item.observation,
                    meld,
                )
                if action.kind in {
                    PublicActionKind.CHI,
                    PublicActionKind.PENG,
                    PublicActionKind.MING_GANG,
                }:
                    matches.append((action, discard_item, hand_item))
        return matches

    def _candidate_hand_deltas(self, meld: RawObservation) -> list[_Pending]:
        return [
            item
            for item in self._pending
            if not item.consumed
            and item.observation.kind == ObservationKind.HAND_DELTA
            and item.observation.actor == meld.actor
            and abs(
                item.observation.timestamp_seconds - meld.timestamp_seconds
            ) <= self.config.claim_window_seconds
        ]

    def _expire_unresolved_melds(self) -> list[ReconstructedAction]:
        output: list[ReconstructedAction] = []
        expiry = self.config.claim_window_seconds
        for item in self._pending:
            if item.consumed:
                continue
            observation = item.observation
            if observation.kind != ObservationKind.MELD_DELTA:
                continue
            if self._watermark <= observation.timestamp_seconds + expiry:
                continue

            evidence = [observation]
            evidence.extend(
                candidate.observation
                for candidate in self._pending
                if not candidate.consumed
                and candidate.sequence != item.sequence
                and abs(
                    candidate.observation.timestamp_seconds
                    - observation.timestamp_seconds
                ) <= expiry
                and candidate.observation.kind
                in {ObservationKind.DISCARD, ObservationKind.HAND_DELTA}
            )
            output.append(
                self._ambiguous_action(
                    observation,
                    reason="meld_window_expired_without_unique_reconstruction",
                    evidence=evidence,
                )
            )
            item.consumed = True
        return output

    @staticmethod
    def _ambiguous_action(
        anchor: RawObservation,
        *,
        reason: str,
        evidence: Iterable[RawObservation],
    ) -> ReconstructedAction:
        evidence = tuple(evidence)
        refs: list[str] = []
        confidences: list[float] = []
        for observation in evidence:
            confidences.append(observation.confidence)
            for ref in observation.evidence_refs:
                if ref not in refs:
                    refs.append(ref)
        return ReconstructedAction(
            timestamp_seconds=anchor.timestamp_seconds,
            actor=anchor.actor,
            kind=PublicActionKind.UNKNOWN_ACTION,
            evidence_grade=EvidenceGrade.UNKNOWN,
            confidence=min(confidences, default=0.0),
            evidence_refs=tuple(refs),
            unknown_reasons=(reason,),
            details={
                "assembler": "temporal_action_assembler_v0_1",
                "evidence_kinds": [
                    observation.kind.value for observation in evidence
                ],
            },
        )

    def _consume(self, sequences: set[int]) -> None:
        for item in self._pending:
            if item.sequence in sequences:
                item.consumed = True

    def _prune(self) -> None:
        # Keep a little extra history so a recent direct DISCARD can still be
        # claimed after another observer channel settles.
        cutoff = self._watermark - self.config.claim_window_seconds * 2
        self._pending = [
            item
            for item in self._pending
            if not item.consumed
            and item.observation.timestamp_seconds >= cutoff
        ]
