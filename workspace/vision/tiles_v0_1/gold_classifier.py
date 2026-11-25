"""Experimental classifier for face-up gold-skinned Huian tiles.

Gold tiles keep the underlying tile artwork but add a gold/yellow skin and a
top-right 金 badge. V0.1 therefore avoids treating gold as a separate taxonomy:
it returns the normal tile_id plus is_gold=True.

This is an experimental bridge, not an Executor gate. It uses local-feature
matching against reviewed tile templates. Wan numerals are compared separately
from their shared lower glyph. Pip counts are diagnostic, not identity overrides.
"""
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from .labels import approved_labels
from .taxonomy import category_for
from .template_classifier import _normalize_gold_face


def _crop_label(root, label):
    image_path = Path(root) / label["image"]
    with Image.open(image_path) as source:
        image = source.convert("RGB")
        # Runtime assets are already tile-only crops; bbox records their
        # location in the original private frame, not coordinates in this PNG.
        if Path(label["image"]).parts[:1] == ("templates",):
            return image
        x, y, width, height = label["bbox"]
        return image.crop((x, y, x + width, y + height))


def _sift_features(image):
    rgb = np.asarray(image.convert("RGB"))
    enlarged = cv2.resize(
        rgb, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC
    )
    gray = cv2.cvtColor(enlarged, cv2.COLOR_RGB2GRAY)
    height, width = gray.shape
    mask = np.full_like(gray, 255)
    # The top-right 金 badge is an overlay rather than part of the base tile face.
    mask[: int(height * 0.35), int(width * 0.65):] = 0
    detector = cv2.SIFT_create(nfeatures=100)
    keypoints, descriptor = detector.detectAndCompute(gray, mask)
    points = np.asarray([point.pt for point in keypoints], dtype=np.float32).reshape(-1, 2)
    return points, descriptor, (height, width)


def _sift_descriptor(image):
    return _sift_features(image)[1]


def _good_sift_matches(sample, template):
    if (
        sample is None
        or template is None
        or len(sample) < 2
        or len(template) < 2
    ):
        return 0
    matcher = cv2.BFMatcher(cv2.NORM_L2)
    matches = matcher.knnMatch(sample, template, k=2)
    return sum(
        1 for first, second in matches
        if first.distance < 0.75 * second.distance
    )


def _wan_numeral_descriptor(image):
    return _wan_numeral_features(image)[1]


def _wan_numeral_features(image):
    face = _normalize_gold_face(image)
    return _sift_features(face.crop((0, 0, face.width, max(12, face.height // 2))))


def count_tong_pips(image):
    """Count visible tong pips after suppressing gold badge and frame.

    Returns 0 when no plausible circles are found. This is intentionally a
    narrow helper for P1..P9 and should not be used for other suits.

    The distance/accumulator thresholds are deliberately conservative. They were
    tightened after replay-temporal diagnostics showed compressed P4 frames could
    otherwise invent a fifth circle from badge/edge texture.
    """
    rgb = np.asarray(image.convert("RGB"))
    enlarged = cv2.resize(
        rgb, None, fx=5, fy=5, interpolation=cv2.INTER_CUBIC
    )
    gray = cv2.cvtColor(enlarged, cv2.COLOR_RGB2GRAY)
    height, width = gray.shape
    fill = int(np.median(gray))

    gray[: int(height * 0.42), int(width * 0.55):] = fill
    gray[: int(height * 0.08), :] = fill
    gray[-int(height * 0.08):, :] = fill
    gray[:, : int(width * 0.08)] = fill
    gray[:, -int(width * 0.08):] = fill
    gray = cv2.GaussianBlur(gray, (5, 5), 1.2)

    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=1.1,
        minDist=height * 0.16,
        param1=100,
        param2=26,
        minRadius=int(height * 0.05),
        maxRadius=int(height * 0.15),
    )
    return 0 if circles is None else len(circles[0])


@dataclass(frozen=True)
class GoldClassification:
    tile_id: str
    category: str
    is_gold: bool
    method: str
    evidence_count: int
    second_best_evidence_count: int
    pip_count: int | None = None
    safe_for_executor: bool = False


class GoldTileClassifier:
    """Classify the underlying tile identity of a gold-skinned tile."""

    def __init__(self, descriptors, numeral_descriptors=None, *, full_details=None, numeral_details=None):
        self.descriptors = {
            tile_id: tuple(values)
            for tile_id, values in descriptors.items()
            if values
        }
        if not self.descriptors:
            raise ValueError("No reviewed non-gold templates are available")
        self.numeral_descriptors = {
            tile: tuple(values) for tile, values in (numeral_descriptors or {}).items()
            if values
        }
        self.full_details = full_details or {}
        self.numeral_details = numeral_details or {}

    @classmethod
    def from_dataset(cls, dataset_root):
        return cls.from_labels(dataset_root, approved_labels(dataset_root))

    @classmethod
    def from_labels(cls, dataset_root, labels):
        root = Path(dataset_root)
        descriptors = defaultdict(list)
        numerals = defaultdict(list)
        full_details, numeral_details = defaultdict(list), defaultdict(list)
        for label in labels:
            if label["region"] == "gold_region":
                continue
            crop = _crop_label(root, label)
            details = _sift_features(crop)
            descriptor = details[1]
            if descriptor is not None:
                descriptors[label["tile_id"]].append(descriptor)
                full_details[label["tile_id"]].append(details)
            if label["tile_id"].startswith("M") and not label.get("gold_skin_only"):
                details = _wan_numeral_features(crop)
                numeral = details[1]
                if numeral is not None:
                    numerals[label["tile_id"]].append(numeral)
                    numeral_details[label["tile_id"]].append(details)
        return cls(descriptors, numerals, full_details=full_details, numeral_details=numeral_details)

    def _rank(self, image):
        sample = _sift_descriptor(image)
        scores = {}
        for tile_id, templates in self.descriptors.items():
            scores[tile_id] = max(
                (_good_sift_matches(sample, template) for template in templates),
                default=0,
            )
        return sorted(
            scores.items(), key=lambda item: (item[1], item[0]), reverse=True
        )

    def _rank_numerals(self, image):
        sample = _wan_numeral_descriptor(image)
        scores = [(tile, max((_good_sift_matches(sample, value) for value in values), default=0))
                  for tile, values in self.numeral_descriptors.items()]
        return sorted(scores, key=lambda item: (-item[1], item[0]))

    def classify(self, image):
        ranking = self._rank(image)
        if not ranking:
            raise ValueError("No candidate gold tile classes are available")

        tile_id, best = ranking[0]
        second = ranking[1][1] if len(ranking) > 1 else 0
        method = "sift"
        pip_count = None

        if tile_id.startswith("M") and self.numeral_descriptors:
            numerals = self._rank_numerals(image)
            # Empty/tied numeral evidence does not manufacture an override.
            if numerals and numerals[0][1] > (numerals[1][1] if len(numerals) > 1 else 0):
                tile_id, best = numerals[0]
                second = numerals[1][1] if len(numerals) > 1 else 0
                method = "sift_wan_numeral"

        # No winning match is not an identity. In an opening animation a
        # blank yellow card produced equal two-match scores for several tiles.
        if best <= 0 or best == second:
            return GoldClassification(
                tile_id="UNKNOWN", category="unknown", is_gold=True,
                method="sift_no_unique_match", evidence_count=best,
                second_best_evidence_count=second,
            )

        # Badge suppression can hide real pips (e.g. P7 counted as five).
        # Preserve the descriptor identity; expose this count only as evidence.
        if tile_id.startswith("P"):
            pip_count = count_tong_pips(image)

        return GoldClassification(
            tile_id=tile_id,
            category=category_for(tile_id),
            is_gold=True,
            method=method,
            evidence_count=best,
            second_best_evidence_count=second,
            pip_count=pip_count,
            safe_for_executor=False,
        )


def probe_manifest(manifest_path, dataset_root, *, exclude_matches=(), lineage_path=None):
    """Run actual crop predictions; expected labels are scoring inputs only."""
    import hashlib
    import json
    from workspace.vision.concealed_template_match_lineage import (
        canonicalize_match_group, load_concealed_template_lineage,
    )
    from .template_classifier import TemplateTileClassifier
    manifest_path = Path(manifest_path)
    query_manifest = json.loads(manifest_path.read_text())
    labels = approved_labels(dataset_root)
    excluded = {canonicalize_match_group(g) for g in exclude_matches}
    lineage = load_concealed_template_lineage(lineage_path) if lineage_path else {}
    training = [r for r in labels if r.get('sha256') not in lineage
                or lineage[r['sha256']].match_group not in excluded]
    sift = GoldTileClassifier.from_labels(dataset_root, training)
    template = TemplateTileClassifier.from_labels(dataset_root, training)
    rows = []
    for entry in query_manifest['queries']:
        with Image.open(manifest_path.parent / entry['crop']) as original:
            crop = original.convert('RGB')
        if hashlib.sha256(crop.tobytes()).hexdigest() != entry['crop_rgb_sha256']:
            raise ValueError('Query crop RGB mismatch')
        raw = sift._rank(crop)
        prediction = sift.classify(crop)
        baseline = template.classify_gold_skin(crop)
        rows.append(dict(query=entry['query'], truth=entry['truth'],
            source_sha256=entry.get('source_sha256'), crop_rgb_sha256=entry['crop_rgb_sha256'],
            ncc_candidate=baseline.tile_id, ncc_score=baseline.confidence,
            full_face_sift_candidate=raw[0][0], candidate=prediction.tile_id,
            method=prediction.method, evidence_count=prediction.evidence_count,
            second_best_evidence_count=prediction.second_best_evidence_count,
            pip_count=prediction.pip_count))
    return dict(schema_version='gold_sift_development_probe_v0_1',
        development_only=True, formal_promotion_evidence=False, runtime_changed=False,
        safe_for_executor=False, safe_for_runtime=False, safe_for_hint=False,
        scores_are_runtime_confidence=False,
        excluded_known_matches=sorted(excluded), training_labels=len(training),
        unresolved_lineage_training_labels=sum(r.get('sha256') not in lineage for r in training),
        class_count=len(sift.descriptors), queries=len(rows),
        raw_ncc_correct=sum(r['ncc_candidate']==r['truth'] for r in rows),
        raw_full_face_sift_correct=sum(r['full_face_sift_candidate']==r['truth'] for r in rows),
        candidate_correct=sum(r['candidate']==r['truth'] for r in rows), rows=rows)


def main():
    import argparse
    import json
    parser = argparse.ArgumentParser(description='Offline Gold SIFT crop comparison; no Runtime changes')
    parser.add_argument('--queries', type=Path, required=True)
    parser.add_argument('--dataset', type=Path, default=Path('dataset/tiles_runtime_v0_2'))
    parser.add_argument('--lineage', type=Path)
    parser.add_argument('--exclude-match', action='append', default=[])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.exclude_match and not args.lineage:
        parser.error('--exclude-match requires --lineage')
    result = probe_manifest(args.queries, args.dataset, exclude_matches=args.exclude_match,
                            lineage_path=args.lineage)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k != 'rows'}))


if __name__ == '__main__':
    main()
