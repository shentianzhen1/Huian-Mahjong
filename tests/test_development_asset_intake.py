from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from workspace.vision.development_asset_intake import (
    CLIENT_TILES,
    build_intake,
    client_tile_to_project,
    source_group_coverage,
)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def source(number, *, group="one_match", distinct="UNKNOWN", kind="video"):
    return {"source_sha256": digest(str(number).encode()), "kind": kind,
            "original_match_group": group,
            "independent_from_other_registered_matches": distinct}


def label(item, *, tile="M2", region="hand_region", session="session"):
    return {"source_sha256": item["source_sha256"], "tile_id": tile,
            "region": region, "source_session": session}


class SourceCoverageTests(unittest.TestCase):
    def test_five_same_match_sessions_count_as_one_provisional_group(self):
        sources = [source(i) for i in range(5)]
        rows = [label(item, session=f"session_{i}") for i, item in enumerate(sources)]
        report = source_group_coverage(rows, sources)
        stats = report["regions"]["hand_region"]["M2"]
        self.assertEqual(stats["stored_session_count"], 5)
        self.assertEqual(stats["named_match_groups"], ["one_match"])
        self.assertEqual(stats["qualified_distinct_match_group_count"], 0)
        self.assertFalse(stats["two_match_support_demonstrated"])

    def test_same_confirmed_group_cannot_be_counted_twice(self):
        sources = [source(i, distinct="CONFIRMED_DISTINCT") for i in range(2)]
        stats = source_group_coverage([label(x) for x in sources], sources)["regions"]["hand_region"]["M2"]
        self.assertEqual(stats["qualified_distinct_match_group_count"], 1)
        self.assertFalse(stats["two_match_support_demonstrated"])

    def test_two_explicitly_distinct_groups_are_still_diagnostic_only(self):
        sources = [source(1, group="a", distinct="CONFIRMED_DISTINCT"),
                   source(2, group="b", distinct="CONFIRMED_DISTINCT")]
        result = source_group_coverage([label(x) for x in sources], sources)
        self.assertTrue(result["regions"]["hand_region"]["M2"]["two_match_support_demonstrated"])
        self.assertFalse(result["runtime_admission"])

    def test_regions_are_not_pooled(self):
        sources = [source(1, group="a", distinct="CONFIRMED_DISTINCT"),
                   source(2, group="b", distinct="CONFIRMED_DISTINCT")]
        result = source_group_coverage([label(sources[0]), label(sources[1], region="draw_region")], sources)
        for region in ("hand_region", "draw_visual"):
            self.assertFalse(result["regions"][region]["M2"]["two_match_support_demonstrated"])

    def test_package_artwork_is_excluded_even_when_it_claims_many_sessions(self):
        item = source(1, kind="package", distinct="CONFIRMED_DISTINCT")
        result = source_group_coverage([label(item, session=str(i)) for i in range(10)], [item])
        self.assertEqual(result["regions"], {})
        self.assertEqual(result["package_labels_excluded_from_real_support"], 10)

    def test_unknown_source_group_and_missing_source_fail_safely(self):
        item = source(1, group="UNKNOWN")
        result = source_group_coverage([label(item)], [item])
        stats = result["regions"]["hand_region"]["M2"]
        self.assertEqual(stats["unknown_source_sha256s"], [item["source_sha256"]])
        with self.assertRaises(ValueError):
            source_group_coverage([label(source(2))], [item])

    def test_conflicting_duplicate_source_is_rejected(self):
        item = source(1)
        with self.assertRaises(ValueError):
            source_group_coverage([], [item, {**item, "original_match_group": "other"}])


class IntakeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.file = self.root / "asset.bin"
        self.file.write_bytes(b"fixed reviewed artifact")
        h = digest(self.file.read_bytes())
        self.package = [{
            "client_id": i, "project_tile": tile, "runtime_admission": False,
            "derived_image": str(self.file), "derived_sha256": h,
            "atlas": str(self.file), "atlas_sha256": h,
            "metadata": str(self.file), "metadata_sha256": h,
        } for i, tile in enumerate(CLIENT_TILES)]
        self.sources = [{"local_path": str(self.file), "source_sha256": h,
                         "kind": "video", "original_match_group": "one_match"}]
        self.crop = [{
            "id": "private/path/to/crop", "tile_id": "M2", "region": "hand_region",
            "source_sha256": h, "source_session": "a", "source_frame": 5,
            "status": "PIXEL_EXACT_FROM_SHA_VERIFIED_SOURCE", "pixel_exact": True,
            "runtime_admitted": False, "formal_promotion_evidence": False,
            "restored_image": str(self.file), "restored_asset_sha256": h,
            "current_asset_sha256": h, "declared_asset_sha256": h,
            "source_label_manifest": str(self.file), "source_label_manifest_sha256": h,
        }]

    def test_client_suit_order_and_flower_boundary(self):
        self.assertEqual([client_tile_to_project(i) for i in (0, 9, 18, 27, 33, 34, 41)],
                         ["P1", "S1", "M1", "E", "B", "F1", "F8"])
        for invalid in (-1, 42, True, None, 1.0, "1"):
            with self.assertRaises(ValueError):
                client_tile_to_project(invalid)

    def test_valid_packet_is_path_free_and_not_admitted(self):
        result = build_intake(self.package, self.crop, self.sources)
        self.assertEqual(result["counts"]["real_crops"], 1)
        self.assertEqual(result["counts"]["package_standard_classes"], 34)
        self.assertNotIn(str(self.root), json.dumps(result))
        self.assertNotIn("private/path/to/crop", json.dumps(result))
        for flag in ("runtime_admission", "formal_promotion_evidence", "safe_for_hint", "safe_for_executor"):
            self.assertIs(result[flag], False)
        self.assertTrue(all(x["approved"] is False for x in result["package_assets"] + result["real_assets"]))

    def test_changed_asset_or_source_is_rejected(self):
        self.file.write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            build_intake(self.package, self.crop, self.sources)

    def test_mislabeled_or_missing_package_class_is_rejected(self):
        altered = deepcopy(self.package)
        altered[0]["project_tile"] = "M1"
        with self.assertRaisesRegex(ValueError, "encoding mismatch"):
            build_intake(altered, self.crop, self.sources)
        with self.assertRaisesRegex(ValueError, "all 34"):
            build_intake(self.package[:-1], self.crop, self.sources)

    def test_duplicate_package_or_crop_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate package"):
            build_intake(self.package + self.package[:1], self.crop, self.sources)
        with self.assertRaisesRegex(ValueError, "duplicate crop"):
            build_intake(self.package, self.crop + self.crop, self.sources)

    def test_failed_pixel_audit_is_not_imported(self):
        altered = deepcopy(self.crop)
        altered[0]["pixel_exact"] = False
        with self.assertRaisesRegex(ValueError, "pixel audit"):
            build_intake(self.package, altered, self.sources)

    def test_runtime_or_formal_promotion_claim_is_rejected(self):
        for field in ("runtime_admitted", "formal_promotion_evidence"):
            altered = deepcopy(self.crop)
            altered[0][field] = True
            with self.assertRaisesRegex(ValueError, "development-only"):
                build_intake(self.package, altered, self.sources)

    def test_missing_file_relative_path_and_stale_label_hash_are_rejected(self):
        for path in ("relative.png", str(self.root / "absent.png")):
            altered = deepcopy(self.package)
            altered[0]["derived_image"] = path
            with self.assertRaises((ValueError, FileNotFoundError)):
                build_intake(altered, self.crop, self.sources)
        altered = deepcopy(self.crop)
        altered[0]["source_label_manifest_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            build_intake(self.package, altered, self.sources)


if __name__ == "__main__":
    unittest.main()
