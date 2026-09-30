from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from workspace.vision.public_identity_labels import (
    PublicIdentityLabel,
    PublicIdentityManifest,
)
from workspace.vision.public_meld_sift_holdout import (
    _assert_no_template_leakage,
    _load_sift_holdout_packet,
    evaluate_frozen_public_meld_sift_holdout,
)


REPO = Path(__file__).resolve().parents[1]
KNOWN_SELECTION_PACKET = (
    "references/vision/2026-09-30/"
    "first_hand_public_query_features_v0_1.json"
)


def _packet() -> dict:
    return {
        "schema_version": "public_identity_query_images_v0_1",
        "development_only": True,
        "excluded_from_formal_promotion": True,
        "query_only": True,
        "training_template_eligible": False,
        "source_session": "future_source",
        "source_sha256": "a" * 64,
        "match_group": "future_match",
        "queries": [{
            "query_id": "future_p1",
            "expected_tile": "P1",
            "region": "public_meld",
            "image_path": "future/p1.jpg",
            "image_sha256": "b" * 64,
        }],
    }


class PublicMeldSiftHoldoutTests(unittest.TestCase):
    def test_known_selection_match_is_rejected_as_future_holdout(self):
        with self.assertRaisesRegex(ValueError, "new independent match group"):
            evaluate_frozen_public_meld_sift_holdout(
                REPO,
                KNOWN_SELECTION_PACKET,
            )

    def test_packet_contract_blocks_template_eligibility_and_wrong_region(self):
        for field, value, message in (
            ("development_only", False, "development_only"),
            ("excluded_from_formal_promotion", False, "formal promotion"),
            ("query_only", False, "query_only"),
            ("training_template_eligible", True, "template eligible"),
        ):
            with self.subTest(field=field):
                payload = _packet()
                payload[field] = value
                with tempfile.TemporaryDirectory() as tmp:
                    path = Path(tmp) / "packet.json"
                    path.write_text(json.dumps(payload), encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, message):
                        _load_sift_holdout_packet(path)

        payload = _packet()
        payload["queries"][0]["region"] = "public_action"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "packet.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "public_meld"):
                _load_sift_holdout_packet(path)

    def test_duplicate_query_ids_fail_closed(self):
        payload = _packet()
        payload["queries"].append(dict(payload["queries"][0]))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "packet.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate"):
                _load_sift_holdout_packet(path)

    def test_template_pixel_or_source_leakage_is_rejected(self):
        label = PublicIdentityLabel(
            label_id="template_p1",
            source_calibration_sample_id="sample_p1",
            source_session="template_source",
            source_sha256="c" * 64,
            image_path="templates/p1.jpg",
            image_sha256="d" * 64,
            frame_index=0,
            time_ms=0,
            region="public_meld",
            tile_id="P1",
            bbox=(0.0, 0.0, 0.5, 0.5),
            status="approved",
            annotator="test",
        )
        manifest = PublicIdentityManifest(
            labels=(label,),
            excluded_from_formal_promotion=True,
            development_only_reason="test",
        )

        payload = _packet()
        payload["source_session"] = "template_source"
        with self.assertRaisesRegex(ValueError, "source session"):
            _assert_no_template_leakage(payload, manifest=manifest)

        payload = _packet()
        payload["queries"][0]["image_sha256"] = "d" * 64
        with self.assertRaisesRegex(ValueError, "pixels"):
            _assert_no_template_leakage(payload, manifest=manifest)


if __name__ == "__main__":
    unittest.main()
