"""Development-only A/B for center-zoomed public meld query faces.

This experiment never changes the template bank, Runtime gates, thresholds,
formal promotion evidence, Hint, or Executor. It only reports whether a
center crop of the locked P6/S4 query images reduces the public-face domain gap.
"""
from __future__ import annotations

from collections import defaultdict
import importlib.util
import json
import math
from pathlib import Path
import unittest


VISION = all(importlib.util.find_spec(m) is not None for m in ("numpy", "PIL"))
REPO = Path(__file__).resolve().parents[1]
REAL_LABELS = REPO / "references/vision/2026-09-22/public_identity_labels_v0_1.json"
REAL_GROUPS = REPO / "references/vision/2026-09-24/public_identity_source_groups.development.json"
REAL_QUERIES = REPO / "references/vision/2026-09-30/first_hand_public_query_features_v0_1.json"


@unittest.skipUnless(VISION, "Pillow/numpy are optional in core-only installs")
class PublicFaceReferenceExperimentTests(unittest.TestCase):
    @staticmethod
    def _center_zoom(image, inset_ratio):
        from PIL import Image

        if inset_ratio == 0:
            return image.copy()
        width, height = image.size
        dx = max(1, int(round(width * inset_ratio)))
        dy = max(1, int(round(height * inset_ratio)))
        if dx * 2 >= width or dy * 2 >= height:
            raise ValueError("center zoom inset removes the full image")
        return image.crop((dx, dy, width - dx, height - dy)).resize(
            (width, height), Image.Resampling.LANCZOS
        )

    @staticmethod
    def _eligible_class_scores(bank, image, *, source_session, source_sha256, region):
        import numpy as np
        from workspace.vision.public_identity_shadow_v0_2 import _feature

        source = bank.sources[source_session]
        if source.source_sha256 != source_sha256:
            raise ValueError("query source SHA mismatch")
        query = _feature(image)
        if query is None:
            raise ValueError("query became blank after center zoom")

        best_by_class_and_group = defaultdict(dict)
        for template in bank.templates:
            if (
                template.region != region
                or template.match_group == source.match_group
                or template.source_sha256 == source_sha256
            ):
                continue
            score = float(np.dot(query, template.feature))
            old = best_by_class_and_group[template.tile_id].get(
                template.match_group, -2.0
            )
            best_by_class_and_group[template.tile_id][template.match_group] = max(
                old, score
            )

        eligible = {}
        for tile_id, by_group in best_by_class_and_group.items():
            scores = sorted(by_group.values(), reverse=True)
            if len(scores) >= 2:
                eligible[tile_id] = scores[1]
        return eligible

    def test_first_hand_center_zoom_ab_is_diagnostic_only(self):
        from PIL import Image
        from workspace.vision.public_identity_labels import load_public_identity_manifest
        from workspace.vision.public_identity_shadow_v0_2 import build_shadow_bank

        fixture = json.loads(REAL_QUERIES.read_text(encoding="utf-8"))
        self.assertTrue(fixture["development_only"])
        self.assertTrue(fixture["query_only"])
        self.assertTrue(fixture["excluded_from_formal_promotion"])
        self.assertFalse(fixture["training_template_eligible"])

        bank = build_shadow_bank(
            load_public_identity_manifest(REAL_LABELS), REPO, REAL_GROUPS
        )
        ratios = (0.00, 0.04, 0.08, 0.12, 0.16, 0.20)
        report = {
            "schema_version": "public_face_reference_ab_v0_1",
            "development_only": True,
            "query_only": True,
            "training_template_eligible": False,
            "safe_for_runtime": False,
            "safe_for_executor": False,
            "formal_promotion_evidence": False,
            "ratios": list(ratios),
            "queries": {},
        }

        for query_meta in fixture["queries"]:
            with Image.open(REPO / query_meta["image_path"]) as original:
                image = original.convert("RGB")

            rows = []
            expected = query_meta["expected_tile"]
            for ratio in ratios:
                transformed = self._center_zoom(image, ratio)
                scores = self._eligible_class_scores(
                    bank,
                    transformed,
                    source_session=fixture["source_session"],
                    source_sha256=fixture["source_sha256"],
                    region=query_meta["region"],
                )
                self.assertGreaterEqual(len(scores), 2)
                self.assertIn(expected, scores)
                expected_score = float(scores[expected])
                competitors = {
                    tile_id: float(score)
                    for tile_id, score in scores.items()
                    if tile_id != expected
                }
                competitor_tile, competitor_score = max(
                    competitors.items(), key=lambda item: (item[1], item[0])
                )
                margin = expected_score - competitor_score
                self.assertTrue(math.isfinite(expected_score))
                self.assertTrue(math.isfinite(competitor_score))
                self.assertTrue(math.isfinite(margin))
                rows.append(
                    {
                        "inset_ratio": ratio,
                        "expected_score": round(expected_score, 6),
                        "best_competitor": competitor_tile,
                        "competitor_score": round(competitor_score, 6),
                        "expected_margin": round(margin, 6),
                    }
                )

            best = max(
                rows,
                key=lambda row: (row["expected_score"], row["expected_margin"]),
            )
            report["queries"][query_meta["query_id"]] = {
                "expected_tile": expected,
                "baseline": rows[0],
                "best_by_expected_score": best,
                "variants": rows,
            }

        print("PUBLIC_FACE_REFERENCE_AB=" + json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
