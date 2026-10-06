from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from workspace.vision.public_meld_identity_sift import PublicMeldSiftBank
from workspace.vision.public_meld_private_sift_loader import (
    augment_public_meld_sift_bank_from_private_zip,
)


try:
    from PIL import Image
except ImportError:
    Image = None


@unittest.skipIf(Image is None, "Pillow is part of Vision dependencies")
class PublicMeldPrivateSiftLoaderTests(unittest.TestCase):
    def _make_fixture(self, base: Path) -> tuple[Path, Path, Path]:
        repository = base / "repo"
        private = base / "private"
        repository.mkdir()
        private.mkdir()

        face_rows = []
        crop_bytes = []
        for index, tile in enumerate(("P7", "P8", "P9"), 1):
            image = Image.new("RGB", (4, 6), (index * 30, 10, 20))
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            raw = buffer.getvalue()
            crop_bytes.append(raw)
            face_rows.append({
                "face_index": index,
                "crop_file": f"g09_face_{index}.png",
                "crop_sha256": hashlib.sha256(raw).hexdigest(),
                "bbox": [index * 4, 10, 4, 6],
                "approved_tile_id": tile,
            })

        private_manifest = {
            "schema_version": "private_existing_user_confirmed_public_faces_v0_1",
            "image_source_verification": (
                "nine_original_videos_rehashed_and_all_36_png_exact_pixel_matched"
            ),
            "development_only": True,
            "previously_inspected": True,
            "independent_blind_review": False,
            "source_disjoint_holdout": False,
            "formal_promotion_evidence": False,
            "safe_for_runtime": False,
            "safe_for_executor": False,
            "groups": [{
                "group_id": "G09",
                "video_sha256": "a" * 64,
                "timestamp_seconds": 60.0,
                "frame_index": 1740,
                "faces": face_rows,
            }],
        }
        manifest_bytes = json.dumps(
            private_manifest, separators=(",", ":"), sort_keys=True
        ).encode("utf-8")
        manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()

        zip_path = private / "approved.zip"
        with ZipFile(zip_path, "w") as archive:
            archive.writestr("private_approved_labels.json", manifest_bytes)
            for row, raw in zip(face_rows, crop_bytes):
                archive.writestr("approved_faces/" + row["crop_file"], raw)

        recovery = {
            "schema_version": "public_meld_private_recovery_result_v0_1",
            "items": [{
                "recovery_id": "G09_hand6_p789",
                "status": "PRIVATE_TEMPLATE_EVIDENCE_RECOVERED",
                "source_sha256": "a" * 64,
                "timestamp_seconds": 60.0,
                "frame_index": 1740,
                "frame_lineage_mode": "direct_source_frame_no_derivative",
                "group_bbox": [0, 0, 12, 6],
                "private_label_manifest_name": "private_approved_labels.json",
                "private_label_manifest_sha256": manifest_sha,
                "faces": [{
                    "tile_id": row["approved_tile_id"],
                    "bbox": row["bbox"],
                    "crop_sha256": row["crop_sha256"],
                    "pixel_exact_from_source_frame": True,
                } for row in face_rows],
                "private_template_eligible": True,
                "public_repo_pixels_committed": False,
                "match_group": "match_a",
                "holdout_eligible": False,
                "formal_promotion_evidence": False,
                "safe_for_hint": False,
                "safe_for_executor": False,
            }],
            "runtime_policy": {
                "changes_runtime_behavior": False,
                "formal_promotion_evidence": False,
                "safe_for_hint": False,
                "safe_for_executor": False,
            },
        }
        recovery_path = repository / "recovery.json"
        recovery_path.write_text(json.dumps(recovery), encoding="utf-8")
        return repository, zip_path, recovery_path

    def test_loads_only_pinned_recovered_private_templates(self):
        with tempfile.TemporaryDirectory() as tmp:
            repository, zip_path, recovery_path = self._make_fixture(Path(tmp))
            bank = PublicMeldSiftBank(sources={}, templates=())
            with patch(
                "workspace.vision.public_meld_private_sift_loader._sift_descriptors",
                return_value=[[1.0], [2.0]],
            ):
                augmented, report = augment_public_meld_sift_bank_from_private_zip(
                    bank,
                    private_zip_path=zip_path,
                    recovery_result_path=recovery_path,
                    repository_root=repository,
                )
            self.assertEqual(report["private_template_count"], 3)
            self.assertEqual(report["tile_ids"], ["P7", "P8", "P9"])
            self.assertEqual(len(augmented.templates), 3)
            self.assertEqual(
                {template.match_group for template in augmented.templates},
                {"match_a"},
            )
            self.assertIn(
                "private_recovered_G09_hand6_p789",
                augmented.sources,
            )
            self.assertFalse(report["safe_for_executor"])

    def test_private_zip_inside_repository_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            repository, zip_path, recovery_path = self._make_fixture(Path(tmp))
            inside = repository / "approved.zip"
            inside.write_bytes(zip_path.read_bytes())
            with self.assertRaisesRegex(ValueError, "outside repository"):
                augment_public_meld_sift_bank_from_private_zip(
                    PublicMeldSiftBank(sources={}, templates=()),
                    private_zip_path=inside,
                    recovery_result_path=recovery_path,
                    repository_root=repository,
                )


if __name__ == "__main__":
    unittest.main()
