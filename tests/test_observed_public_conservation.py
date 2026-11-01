"""Public-zone accounting never fabricates hidden hands or wall tiles."""
import unittest

from workspace.simulator.observed_public_conservation import (
    PublicTileEvent as E, audit_public_conservation,
)


class ObservedPublicConservationTests(unittest.TestCase):
    def test_offer_claim_river_and_unknown_physical_remainder(self):
        events = [
            E("OFFER", "opponent", "P6"),
            E("CLAIM", "tz", "P6", ("P6",) * 4),
            E("OFFER", "tz", "S2"),
            E("CLAIM", "opponent", "S2", ("S1", "S2", "S3")),
            E("OFFER", "opponent", "M8"),
            E("RESOLVE_RIVER", "opponent", "M8"),
        ]
        result = audit_public_conservation(
            events, terminal_concealed=("M6", "M6", "P3"),
            opened_gold="M6", flower_count=3)
        self.assertEqual(result["known_type_counts"]["P6"], 4)
        self.assertEqual(result["known_type_counts"]["M6"], 3)
        self.assertEqual(result["river_tile_count"], 1)
        self.assertEqual(result["river_tile_counts_by_actor"], {"tz": 0, "opponent": 1})
        self.assertFalse(result["terminal_river_counts_verified"])
        self.assertEqual(result["meld_count"], 2)
        self.assertEqual(result["known_physical_tile_count"], 15)
        self.assertEqual(result["unknown_physical_tile_count"], 129)
        self.assertIsNone(result["conditional_unlocated_nonwall_count"])
        self.assertFalse(result["full_144_tile_conservation_verified"])

        with_wall = audit_public_conservation(
            events, terminal_concealed=("M6", "M6", "P3"),
            opened_gold="M6", flower_count=3, observed_wall_remaining=120)
        self.assertEqual(with_wall["conditional_unlocated_nonwall_count"], 9)
        self.assertFalse(with_wall["full_144_tile_conservation_verified"])

        closed_count_only = audit_public_conservation(
            events, terminal_concealed=("M6", "M6", "P3"),
            opened_gold="M6", flower_count=3, observed_wall_remaining=129,
            observed_terminal_river_counts={"tz": 0, "opponent": 1})
        self.assertEqual(closed_count_only["conditional_unlocated_nonwall_count"], 0)
        self.assertTrue(closed_count_only["terminal_river_counts_verified"])
        self.assertFalse(closed_count_only["full_144_tile_conservation_verified"])

        with self.assertRaisesRegex(ValueError, "opponent river count mismatch: ledger=1, observed=3"):
            audit_public_conservation(
                events, observed_terminal_river_counts={"tz": 0, "opponent": 3})

    def test_wrong_claim_duplicate_or_fifth_copy_abstains(self):
        with self.assertRaisesRegex(ValueError, "pending offer"):
            audit_public_conservation([E("CLAIM", "tz", "P6", ("P6",) * 4)])
        with self.assertRaisesRegex(ValueError, "unresolved action-area"):
            audit_public_conservation([E("OFFER", "opponent", "P6")])
        with self.assertRaisesRegex(ValueError, "fifth known"):
            audit_public_conservation([
                E("OFFER", "opponent", "P6"),
                E("CLAIM", "tz", "P6", ("P6",) * 4),
                E("RIVER", "opponent", "P6"),
            ])
        with self.assertRaisesRegex(ValueError, "consecutive"):
            audit_public_conservation([
                E("OFFER", "opponent", "S3"),
                E("CLAIM", "tz", "S3", ("S3", "S4", "S9")),
            ])
        with self.assertRaisesRegex(ValueError, "exceed 144"):
            audit_public_conservation([], observed_wall_remaining=144,
                                      opened_gold="M6")
        with self.assertRaisesRegex(ValueError, "both actors"):
            audit_public_conservation([], observed_terminal_river_counts={"tz": 0})

    def test_actor_specific_terminal_zones_and_observation_mismatch(self):
        events = [
            E("OFFER", "opponent", "P6"),
            E("CLAIM", "tz", "P6", ("P6",) * 4),
            E("OFFER", "tz", "S2"),
            E("CLAIM", "opponent", "S2", ("S1", "S2", "S3")),
        ]
        options = dict(
            terminal_concealed_by_actor={"tz": ("M6", "M6"), "opponent": ("P3",)},
            observed_terminal_meld_tile_counts={"tz": 4, "opponent": 3},
            observed_terminal_flower_counts={"tz": 3, "opponent": 1},
            flower_count=4,
        )
        result = audit_public_conservation(events, **options)
        self.assertEqual(result["meld_tile_counts_by_actor"], {"tz": 4, "opponent": 3})
        self.assertEqual(result["terminal_hand_meld_tile_counts_by_actor"],
                         {"tz": 6, "opponent": 4})
        self.assertTrue(result["terminal_meld_tile_counts_verified"])
        self.assertTrue(result["terminal_flower_counts_verified"])
        self.assertFalse(result["full_144_tile_conservation_verified"])

        with self.assertRaisesRegex(ValueError, "opponent meld tile count mismatch"):
            audit_public_conservation(events, **{**options,
                "observed_terminal_meld_tile_counts": {"tz": 4, "opponent": 6}})
        with self.assertRaisesRegex(ValueError, "disagree with flower_count"):
            audit_public_conservation(events, **{**options,
                "observed_terminal_flower_counts": {"tz": 3, "opponent": 2}})
        with self.assertRaisesRegex(ValueError, "one format only"):
            audit_public_conservation(events, terminal_concealed=("M6",), **options)


if __name__ == "__main__":
    unittest.main()
