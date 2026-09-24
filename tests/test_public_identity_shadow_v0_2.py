"""No-private-video contract for Issue #69 public-region shadow classification."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

VISION = all(importlib.util.find_spec(m) is not None for m in ("numpy", "PIL"))
REPO = Path(__file__).resolve().parents[1]
REAL_LABELS = REPO / "references/vision/2026-09-22/public_identity_labels_v0_1.json"
REAL_GROUPS = REPO / "references/vision/2026-09-24/public_identity_source_groups.development.json"


@unittest.skipUnless(VISION, "Pillow/numpy are optional in core-only installs")
class PublicIdentityShadowV02Tests(unittest.TestCase):
    def setUp(self):
        from PIL import Image, ImageDraw
        from workspace.vision.public_identity_labels import (
            PublicIdentityLabel, PublicIdentityManifest,
        )
        from workspace.vision.public_identity_shadow_v0_2 import ShadowBank
        self.Image, self.ImageDraw = Image, ImageDraw
        self.PublicIdentityLabel = PublicIdentityLabel
        self.PublicIdentityManifest = PublicIdentityManifest
        self.ShadowBank = ShadowBank
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.samples = []
        self.sources = []
        self.reg = self.root / "registry.json"

    def face(self, tile):
        image = self.Image.new("RGB", (60, 80), (235, 235, 235))
        draw = self.ImageDraw.Draw(image)
        if tile == "M1":
            for x in (9, 23, 37, 51):
                draw.rectangle((x, 8, x + 5, 71), fill=(35, 35, 35))
        elif tile == "M2":
            for y in (9, 24, 39, 54):
                draw.rectangle((8, y, 51, y + 5), fill=(35, 35, 35))
        else:
            raise AssertionError(tile)
        return image

    def source(self, session, group):
        sha = hashlib.sha256(session.encode("utf-8")).hexdigest()
        self.sources.append({
            "source_session": session, "source_sha256": sha,
            "match_group": group, "review_exposure": "previously_inspected",
        })
        return sha

    def add(self, session, group, tile, *, region="public_meld"):
        from workspace.vision.public_identity_labels import PublicIdentityLabel
        existing = next((s for s in self.sources if s["source_session"] == session), None)
        sha = existing["source_sha256"] if existing else self.source(session, group)
        file = Path("samples") / f"{session}_{tile}_{region}.png"
        target = self.root / file
        target.parent.mkdir(parents=True, exist_ok=True)
        self.face(tile).save(target)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        label = PublicIdentityLabel(
            label_id=f"{session}_{tile}_{region}",
            source_calibration_sample_id=f"synthetic_{session}_{tile}",
            source_session=session, source_sha256=sha,
            image_path=str(file), image_sha256=digest,
            frame_index=0, time_ms=0, region=region, tile_id=tile,
            bbox=(0.0, 0.0, 1.0, 1.0), status="approved",
            annotator="synthetic_ci",
        )
        self.samples.append(label)
        return label

    def bank(self):
        from workspace.vision.public_identity_shadow_v0_2 import build_shadow_bank
        self.reg.write_text(json.dumps({
            "schema_version": "public_identity_source_groups_development_v0_1",
            "development_only": True,
            "excluded_from_formal_promotion": True,
            "sources": self.sources,
        }), encoding="utf-8")
        manifest = self.PublicIdentityManifest(
            tuple(self.samples), True, "synthetic previously inspected fixture"
        )
        return build_shadow_bank(manifest, self.root, self.reg), manifest

    def test_two_other_matches_per_competing_class_can_only_propose(self):
        from workspace.vision.public_identity_shadow_v0_2 import propose_shadow_identity
        for source in ("train_A", "train_B", "holdout_C"):
            for tile in ("M1", "M2"):
                self.add(source, source, tile)
        bank, _ = self.bank()
        target = next(s for s in self.sources if s["source_session"] == "holdout_C")
        for tile in ("M1", "M2"):
            result = propose_shadow_identity(
                bank, self.face(tile), region="public_meld",
                source_session=target["source_session"],
                source_sha256=target["source_sha256"],
            )
            self.assertEqual(result["eligible_class_count"], 2)
            self.assertEqual(result["shadow_proposal"], tile)
            self.assertEqual(result["tile_id"], "UNKNOWN")
            self.assertEqual(result["evidence_grade"], "UNKNOWN")
            self.assertFalse(result["safe_for_runtime"])
            self.assertFalse(result["safe_for_executor"])
            self.assertFalse(result["formal_promotion_evidence"])

    def test_two_videos_same_match_do_not_count_as_two_training_groups(self):
        from workspace.vision.public_identity_shadow_v0_2 import propose_shadow_identity
        for source in ("train_A1", "train_A2"):
            for tile in ("M1", "M2"):
                self.add(source, "recorded_match_A", tile)
        target_sha = self.source("holdout_C", "recorded_match_C")
        bank, _ = self.bank()
        result = propose_shadow_identity(
            bank, self.face("M1"), region="public_meld",
            source_session="holdout_C", source_sha256=target_sha,
        )
        self.assertEqual(result["eligible_class_count"], 0)
        self.assertIsNone(result["shadow_proposal"])

    def test_region_isolation_unknown_and_source_identity_guard(self):
        from workspace.vision.public_identity_shadow_v0_2 import propose_shadow_identity
        for source in ("train_A", "train_B"):
            for tile in ("M1", "M2"):
                self.add(source, source, tile)
        target_sha = self.source("heldout", "new_match")
        bank, _ = self.bank()
        single = propose_shadow_identity(
            bank, self.face("M1"), region="public_single",
            source_session="heldout", source_sha256=target_sha,
        )
        self.assertEqual(single["eligible_class_count"], 0)
        self.assertIsNone(single["shadow_proposal"])
        blank = propose_shadow_identity(
            bank, self.Image.new("RGB", (60, 80), "white"),
            region="public_meld", source_session="heldout",
            source_sha256=target_sha,
        )
        self.assertEqual(blank["reason"], "blank_or_low_texture_public_face")
        with self.assertRaisesRegex(ValueError, "query source session/SHA"):
            propose_shadow_identity(
                bank, self.face("M1"), region="public_meld",
                source_session="heldout", source_sha256="0" * 64,
            )

    def test_sha_tamper_and_cross_match_duplicate_bytes_fail(self):
        from workspace.vision.public_identity_shadow_v0_2 import (
            build_shadow_bank, load_development_sources,
        )
        label = self.add("train_A", "match_A", "M1")
        bank, manifest = self.bank()
        self.assertEqual(len(bank.templates), 1)
        image = self.root / label.image_path
        image.write_bytes(b"not a matching reviewed source image")
        with self.assertRaisesRegex(ValueError, "integrity"):
            build_shadow_bank(manifest, self.root, self.reg)
        broken = json.loads(self.reg.read_text())
        broken["sources"].append({
            "source_session": "train_B", "source_sha256": broken["sources"][0]["source_sha256"],
            "match_group": "other_match", "review_exposure": "previously_inspected",
        })
        self.reg.write_text(json.dumps(broken))
        with self.assertRaisesRegex(ValueError, "identical video bytes"):
            load_development_sources(self.reg)

    def test_real_17_labels_have_no_cross_match_eligible_class(self):
        from workspace.vision.public_identity_labels import load_public_identity_manifest
        from workspace.vision.public_identity_shadow_v0_2 import evaluate_reviewed_development
        report = evaluate_reviewed_development(
            load_public_identity_manifest(REAL_LABELS), REPO, REAL_GROUPS,
        )
        self.assertEqual(report["approved_label_count"], 17)
        self.assertEqual(report["source_match_groups"], 2)
        self.assertEqual(report["eligible_queries"], 0)
        self.assertEqual(report["shadow_proposals"], 0)
        self.assertEqual(report["shadow_abstentions"], 17)
        self.assertIsNone(report["shadow_accuracy_on_proposals"])
        self.assertFalse(report["formal_promotion_evidence"])
        self.assertFalse(report["safe_for_runtime"])
        self.assertEqual(report["by_region"]["public_meld"]["reviewed"], 12)


if __name__ == "__main__":
    unittest.main()
