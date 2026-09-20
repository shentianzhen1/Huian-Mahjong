"""Environment-owned state. No dealing/open-gold procedure is inferred here."""
from dataclasses import dataclass, field
from huian._legacy import env


@dataclass
class HuianGameState(env.GameState):
    # Reference to a tile STILL in the river; never an extra physical copy.
    pending_discard: dict | None = None
    # Auditable Hu declaration facts. This is a logical reference only; a
    # discarded winning tile remains in its source river for tile accounting.
    pending_hu: dict | None = None
    # Logical reference only: the fourth tile stays in the declarer's hand
    # until PASS commits the kong. A robbed tile remains there for accounting.
    pending_kong: dict | None = None
    special_states: list[str] = field(default_factory=lambda: ["UNKNOWN", "UNKNOWN"])
    # Physical tiles explicitly excluded from play by an imported scenario.
    # This represents accounting only, not a guessed indicator-opening rule.
    reserved_tiles: list[str] = field(default_factory=list)
    terminal_reason: str | None = None

    def canonical_dict(self):
        data = super().canonical_dict()
        data.update(pending_discard=self.pending_discard,
                    pending_hu=self.pending_hu,
                    pending_kong=self.pending_kong,
                    special_states=list(self.special_states),
                    reserved_tiles=list(self.reserved_tiles),
                    terminal_reason=self.terminal_reason)
        return data

    def physical_tiles(self):
        tiles = list(self.wall) + list(self.reserved_tiles)
        for p in range(2):
            tiles.extend(self.hands[p] + self.discards[p] + self.flowers[p])
            for meld in self.melds[p]:
                tiles.extend(meld.tiles)
        return tiles
