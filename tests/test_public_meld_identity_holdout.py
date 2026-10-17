from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from workspace.vision.public_meld_identity_holdout import (
    _load_holdout_packet,
    evaluate_frozen_public_meld_holdout,
)


REPO = Path(__file__).resolve().parents[1]
SELECTION_QUERIES = (
    "references/vision/2026-09-30/"
    "first_hand_public_query_features_v0_1.json"
)


class PublicMeldIdentityHoldoutTests(unittest.TestCase):
    def test_selection_queries_are_rejected_as_holdout_before_scoring(self):
        with self.assertRaisesRegex(ValueError, "independent original match group"):
            evaluate_frozen_public_meld_holdout(
                REPO,
                SELECTION_QUERIES,
            )

    def test_packet_contract_rejects_runtime_or_template_leak(self):
        base = {
            "schema_version": "public_identity_query_images_v0_1",
            "development_only": True,
            "excluded_from_formal_promotion": True,
            "query_only": True,
            "training_template_eligible": False,
            "source_session": "future_session",
            "source_sha256": "a" * 64,
            "match_group": "future_match",
            "queries": [{
                "query_id": "q1",
                "expected_tile": "P1",
                "region": "public_meld",
                "image_path": "future/q1.jpg",
                "image_sha256": "b" * 64,
            }],
        }

        for field, value, message in (
            ("development_only", False, "development_only"),
            ("excluded_from_formal_promotion", False, "formal promotion"),
            ("query_only", False, "query_only"),
            ("training_template_eligible", True, "template eligible"),
        ):
            with self.subTest(field=field):
                payload = dict(base)
                payload[field] = value
                with tempfile.TemporaryDirectory() as tmp:
                    path = Path(tmp) / "packet.json"
                    path.write_text(json.dumps(payload), encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, message):
                        _load_holdout_packet(path)

    def test_non_meld_queries_are_rejected(self):
        payload = {
            "schema_version": "public_identity_query_images_v0_1",
            "development_only": True,
            "excluded_from_formal_promotion": True,
            "query_only": True,
            "training_template_eligible": False,
            "source_session": "future_session",
            "source_sha256": "a" * 64,
            "match_group": "future_match",
            "queries": [{
                "query_id": "q1",
                "expected_tile": "P1",
                "region": "public_action",
                "image_path": "future/q1.jpg",
                "image_sha256": "b" * 64,
            }],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "packet.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "public_meld"):
                _load_holdout_packet(path)


if __name__ == "__main__":
    unittest.main()
