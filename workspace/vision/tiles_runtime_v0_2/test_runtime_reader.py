from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from PIL import Image, ImageDraw

from workspace.vision.tiles_v0_1.template_classifier import TemplateTileClassifier

from .runtime_reader import (
    _coverage,
    _gold_skin_covered_classes,
    _training_labels,
    identity_gate,
)


class RuntimeReaderGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.covered = {
            *(f"M{rank}" for rank in range(1, 10)),
            *(f"P{rank}" for rank in range(1, 10)),
            *(f"S{rank}" for rank in range(1, 10)),
            "E", "SOUTH", "W", "N", "R", "G", "B",
        }
        self.cross_session = {"hand_region": {"M3", "P9"}}

    def gate(self, tile_id: str, confidence: float, covered=None):
        return identity_gate(
            tile_id,
            confidence,
            region="hand_region",
            covered_classes=self.covered if covered is None else covered,
            cross_session_classes=self.cross_session,
            confidence_threshold=0.82,
        )

    def test_known_runtime_session_is_excluded_from_templates(self) -> None:
        labels = [
            {"tile_id": "P9", "approved": True, "source_session": "session_a"},
            {"tile_id": "P9", "approved": True, "source_session": "session_b"},
            {"tile_id": "P9", "approved": True, "source_session": "session_c"},
        ]
        filtered = _training_labels(labels, "session_b")
        self.assertEqual([row["source_session"] for row in filtered], ["session_a", "session_c"])

    def test_unknown_runtime_session_keeps_all_templates(self) -> None:
        labels = [{"tile_id": "P9", "approved": True, "source_session": "session_a"}]
        self.assertEqual(_training_labels(labels, None), labels)

    def test_high_confidence_cross_session_class_is_accepted(self) -> None:
        self.assertEqual(self.gate("P9", 0.93), ("P9", "accepted"))

    def test_low_confidence_is_unknown(self) -> None:
        self.assertEqual(
            self.gate("P9", 0.81),
            ("UNKNOWN", "below_confidence_threshold"),
        )

    def test_missing_m2_blocks_wan_identity_instead_of_silent_mislabel(self) -> None:
        covered = set(self.covered)
        covered.remove("M2")
        self.assertEqual(
            self.gate("M3", 0.99, covered),
            ("UNKNOWN", "category_has_missing_standard_class"),
        )

    def test_single_session_class_is_unknown(self) -> None:
        self.assertEqual(
            self.gate("P8", 0.99),
            ("UNKNOWN", "class_not_cross_session_validated_in_region"),
        )

    def test_concealed_identity_cross_session_spans_hand_and_draw(self) -> None:
        labels = [
            {
                "tile_id": "S3",
                "approved": True,
                "region": "hand_region",
                "source_session": "session_a",
            },
            {
                "tile_id": "S3",
                "approved": True,
                "region": "draw_visual",
                "source_session": "session_b",
            },
        ]
        _, covered_by_region, cross_session = _coverage(labels)
        self.assertIn("S3", covered_by_region["concealed_identity"])
        self.assertIn("S3", cross_session["concealed_identity"])

    def test_gold_identity_cross_session_can_span_concealed_regions(self) -> None:
        labels = [
            {
                "tile_id": "M6",
                "approved": True,
                "region": "draw_visual",
                "source_session": "session_a",
            },
            {
                "tile_id": "M6",
                "approved": True,
                "region": "hand_region",
                "source_session": "session_b",
            },
        ]
        _, _, cross_session = _coverage(labels)
        self.assertIn("M6", cross_session["gold_identity"])

    def test_gold_identity_same_session_does_not_self_validate(self) -> None:
        labels = [
            {
                "tile_id": "M6",
                "approved": True,
                "region": "draw_visual",
                "source_session": "session_a",
            },
            {
                "tile_id": "M6",
                "approved": True,
                "region": "hand_region",
                "source_session": "session_a",
            },
        ]
        _, _, cross_session = _coverage(labels)
        self.assertNotIn("M6", cross_session["gold_identity"])

    def test_current_session_gold_skin_qualifies_appearance_only(self) -> None:
        labels = [
            {
                "tile_id": f"M{rank}",
                "approved": True,
                "region": "hand_region",
                "source_session": "session_base_a",
            }
            for rank in range(1, 10)
        ]
        labels.extend([
            {
                "tile_id": "M6",
                "approved": True,
                "region": "draw_visual",
                "source_session": "session_base_b",
            },
            {
                "tile_id": "M6",
                "approved": True,
                "region": "hand_region",
                "source_session": "session_target",
                "gold_skin_only": True,
            },
        ])
        training = _training_labels(labels, "session_target")
        _, covered_by_region, cross_session = _coverage(training)

        # The reviewed yellow crop is excluded from the target-session
        # classifier/template bank and therefore cannot self-match.
        self.assertEqual(_gold_skin_covered_classes(training), set())
        # It may still qualify the class as having a reviewed real Gold skin.
        self.assertEqual(_gold_skin_covered_classes(labels), {"M6"})
        # Exact identity must independently survive two non-target sessions.
        self.assertIn("M6", cross_session["gold_identity"])
        self.assertEqual(
            identity_gate(
                "M6",
                0.90,
                region="gold_identity",
                covered_classes=covered_by_region["gold_identity"],
                cross_session_classes=cross_session,
                confidence_threshold=0.82,
            ),
            ("M6", "accepted"),
        )

    def test_gold_skin_review_cannot_replace_independent_identity_support(self) -> None:
        labels = [
            {
                "tile_id": f"M{rank}",
                "approved": True,
                "region": "hand_region",
                "source_session": "session_base_a",
            }
            for rank in range(1, 10)
        ]
        labels.append({
            "tile_id": "M6",
            "approved": True,
            "region": "hand_region",
            "source_session": "session_target",
            "gold_skin_only": True,
        })
        training = _training_labels(labels, "session_target")
        _, covered_by_region, cross_session = _coverage(training)
        self.assertEqual(_gold_skin_covered_classes(labels), {"M6"})
        self.assertEqual(
            identity_gate(
                "M6",
                0.99,
                region="gold_identity",
                covered_classes=covered_by_region["gold_identity"],
                cross_session_classes=cross_session,
                confidence_threshold=0.82,
            ),
            ("UNKNOWN", "class_not_cross_session_validated_in_region"),
        )

    def test_real_gold_skin_coverage_requires_explicit_reviewed_sample(self) -> None:
        labels = [
            {
                "tile_id": "M6",
                "approved": True,
                "region": "hand_region",
                "source_session": "session_plain",
            },
            {
                "tile_id": "M6",
                "approved": True,
                "region": "hand_region",
                "source_session": "session_gold",
                "gold_skin_only": True,
            },
            {
                "tile_id": "M1",
                "approved": True,
                "region": "hand_region",
                "source_session": "session_plain_2",
            },
        ]
        self.assertEqual(_gold_skin_covered_classes(labels), {"M6"})

    def test_gold_skin_only_supports_gold_identity_not_ordinary_concealed(self) -> None:
        labels = [
            {
                "tile_id": "M6",
                "approved": True,
                "region": "hand_region",
                "source_session": "session_plain",
            },
            {
                "tile_id": "M6",
                "approved": True,
                "region": "hand_region",
                "source_session": "session_gold",
                "gold_skin_only": True,
            },
        ]
        _, covered_by_region, cross_session = _coverage(labels)
        self.assertIn("M6", covered_by_region["hand_region"])
        self.assertNotIn("M6", cross_session["concealed_identity"])
        self.assertIn("M6", covered_by_region["gold_identity"])
        self.assertIn("M6", cross_session["gold_identity"])

    def test_public_m2_does_not_unblock_concealed_wan_domain(self) -> None:
        labels = []
        for rank in range(1, 10):
            if rank == 2:
                continue
            labels.append({
                "tile_id": f"M{rank}",
                "approved": True,
                "region": "hand_region",
                "source_session": "session_a",
            })
        # M3 has genuine hand-region cross-session support.
        labels.append({
            "tile_id": "M3",
            "approved": True,
            "region": "hand_region",
            "source_session": "session_b",
        })
        # M2 exists only in a public/meld domain and must not make hand Wan
        # coverage appear complete.
        labels.append({
            "tile_id": "M2",
            "approved": True,
            "region": "meld_region",
            "source_session": "session_public",
        })

        covered, covered_by_region, cross_session = _coverage(labels)
        self.assertIn("M2", covered)
        self.assertNotIn("M2", covered_by_region["hand_region"])
        self.assertNotIn("M2", covered_by_region["concealed_identity"])
        self.assertEqual(
            identity_gate(
                "M3",
                0.99,
                region="concealed_identity",
                covered_classes=covered_by_region["concealed_identity"],
                cross_session_classes=cross_session,
                confidence_threshold=0.82,
            ),
            ("UNKNOWN", "category_has_missing_standard_class"),
        )

    def test_public_m2_does_not_complete_gold_identity_domain(self) -> None:
        labels = [
            {
                "tile_id": f"M{rank}",
                "approved": True,
                "region": "hand_region",
                "source_session": "session_a",
            }
            for rank in range(1, 10)
            if rank != 2
        ]
        labels.append({
            "tile_id": "M2",
            "approved": True,
            "region": "meld_region",
            "source_session": "session_public",
        })
        _, covered_by_region, _ = _coverage(labels)
        self.assertNotIn("M2", covered_by_region["gold_identity"])

    def test_from_labels_builds_concealed_bank_from_hand_and_draw_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = []
            for index, (tile_id, region) in enumerate((
                ("M3", "hand_region"),
                ("P4", "draw_visual"),
                ("S3", "gold_region"),
            )):
                image = Image.new("RGB", (60, 92), "white")
                draw = ImageDraw.Draw(image)
                draw.rectangle((12 + index * 2, 20, 42, 70), fill="black")
                path = root / f"{tile_id}.png"
                image.save(path)
                rows.append({
                    "image": path.name,
                    "bbox": [0, 0, 60, 92],
                    "tile_id": tile_id,
                    "region": region,
                    "approved": True,
                })

            classifier = TemplateTileClassifier.from_labels(root, rows)
            concealed = classifier.regional_templates["concealed_identity"]
            self.assertEqual(set(concealed), {"M3", "P4"})
            self.assertNotIn("S3", concealed)

    def test_gold_skin_only_label_skips_ordinary_template_banks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ordinary = Image.new("RGB", (60, 92), "white")
            ImageDraw.Draw(ordinary).rectangle((15, 20, 44, 70), fill="black")
            ordinary_path = root / "m3.png"
            ordinary.save(ordinary_path)

            gold = Image.new("RGB", (60, 92), (235, 205, 70))
            ImageDraw.Draw(gold).rectangle((18, 22, 42, 70), fill="black")
            gold_path = root / "m6_gold.png"
            gold.save(gold_path)

            rows = [
                {
                    "image": ordinary_path.name,
                    "bbox": [0, 0, 60, 92],
                    "tile_id": "M3",
                    "region": "hand_region",
                    "approved": True,
                },
                {
                    "image": gold_path.name,
                    "bbox": [0, 0, 60, 92],
                    "tile_id": "M6",
                    "region": "hand_region",
                    "approved": True,
                    "gold_skin_only": True,
                },
            ]
            classifier = TemplateTileClassifier.from_labels(root, rows)
            self.assertIn("M6", classifier.gold_identity_templates)
            self.assertNotIn("M6", classifier.templates)
            self.assertNotIn(
                "M6", classifier.regional_templates["concealed_identity"]
            )

    def test_gold_skin_ranking_ignores_ting_overlay_and_uses_full_bank(self) -> None:
        def tile(background, glyph):
            image = Image.new("RGB", (60, 92), background)
            draw = ImageDraw.Draw(image)
            draw.rectangle((18, 22, 42, 70), fill=glyph)
            return image

        m6 = tile("white", "black")
        other = Image.new("RGB", (60, 92), "white")
        ImageDraw.Draw(other).ellipse((18, 28, 42, 58), fill="black")
        # Build directly from normalized features to keep the regression
        # independent of repository image assets.
        from workspace.vision.tiles_v0_1.template_classifier import _feature
        instance = TemplateTileClassifier(
            {"M6": [_feature(m6, region="draw_visual")],
             "P1": [_feature(other, region="hand_region")]},
            {"gold_region": {"P1": [_feature(other, region="gold_region")]}},
        )
        sample = Image.new("RGB", (72, 122), (0, 55, 55))
        draw = ImageDraw.Draw(sample)
        draw.rectangle((15, 0, 57, 20), fill=(245, 190, 30))
        draw.rectangle((6, 24, 66, 116), fill=(235, 205, 70))
        draw.rectangle((24, 46, 48, 94), fill="black")
        result = instance.classify_gold_skin(sample)
        self.assertEqual(result.tile_id, "M6")

    def test_real_public_gold_m1_keeps_correct_top1_identity(self) -> None:
        """Real yellow Gold skin regression from committed public evidence."""
        root = Path(__file__).resolve().parents[3]
        dataset = root / "dataset" / "tiles_runtime_v0_2"
        evidence = (
            root
            / "references"
            / "gameplay"
            / "2026-09-15"
            / "66fe863f_youjin100"
            / "opening_excerpt_000000ms.jpg"
        )
        self.assertTrue(evidence.is_file())
        classifier = TemplateTileClassifier.from_dataset(dataset)
        with Image.open(evidence) as source:
            # Bottom-left yellow concealed M1. Keep the crop tile-only and
            # deliberately avoid the replay controls above it.
            crop = source.convert("RGB").crop((112, 413, 159, 478))
        result = classifier.classify_gold_skin(crop)
        self.assertEqual(
            result.tile_id,
            "M1",
            msg=f"real Gold M1 misranked as {result.tile_id} at {result.confidence:.6f}",
        )

    def test_from_labels_builds_gold_normalized_identity_bank(self) -> None:
        from workspace.vision.tiles_v0_1.template_classifier import _feature

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            m6 = Image.new("RGB", (60, 92), "white")
            draw = ImageDraw.Draw(m6)
            draw.rectangle((18, 22, 42, 70), fill="black")
            path = root / "m6.png"
            m6.save(path)
            rows = [{
                "image": path.name,
                "bbox": [0, 0, 60, 92],
                "tile_id": "M6",
                "region": "hand_region",
                "approved": True,
            }]
            classifier = TemplateTileClassifier.from_labels(root, rows)
            self.assertIn("M6", classifier.gold_identity_templates)
            expected = _feature(m6, region="gold_region")
            ordinary = classifier.templates["M6"][0]
            gold = classifier.gold_identity_templates["M6"][0]
            self.assertEqual(gold.tobytes(), expected.tobytes())
            self.assertNotEqual(gold.tobytes(), ordinary.tobytes())


if __name__ == "__main__":
    unittest.main()
