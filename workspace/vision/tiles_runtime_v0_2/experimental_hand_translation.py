"""Opt-in private replay adapter for recovered hand references and translation.

NCC scores remain development diagnostics, not calibrated probabilities.
The adapter never changes source qualification, geometry or yellow-Gold roles.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


class TranslatedHandClassifier:
    def __init__(self, ordinary, extra_features, neutral_features=()):
        self.ordinary = ordinary
        self.extra_features = extra_features
        self.neutral_features = neutral_features

    def __getattr__(self, name):
        return getattr(self.ordinary, name)

    def classify(self, image, region=None):
        original = self.ordinary.classify(image, region=region)
        if region not in {'concealed_identity', 'hand_region', 'draw_visual', 'draw_region'}:
            return original
        if original.confidence >= 0.82:
            return original
        import cv2
        import numpy as np
        from workspace.vision.tiles_v0_1.template_classifier import _feature, Classification
        query = _feature(image, region='concealed_identity')
        padded = cv2.copyMakeBorder(query, 3, 3, 3, 3, cv2.BORDER_REPLICATE)
        bank = self.ordinary.regional_templates.get('concealed_identity', {})
        examples = [(tile, feature) for tile, refs in bank.items() for feature in refs]
        examples.extend(self.extra_features)
        best = original
        for tile, reference in examples:
            score = float(cv2.matchTemplate(padded, reference, cv2.TM_CCOEFF_NORMED).max())
            if np.isfinite(score) and score > best.confidence:
                best = Classification(tile, score)
        if best.confidence < 0.82 and self.neutral_features:
            from .neutral_face_feature_probe import neutral
            candidate_query = neutral(image)
            padded_neutral = cv2.copyMakeBorder(candidate_query, 3, 3, 3, 3, cv2.BORDER_REPLICATE)
            tile, score = max(
                ((tile, float(cv2.matchTemplate(padded_neutral, ref, cv2.TM_CCOEFF_NORMED).max()))
                 for tile, ref in self.neutral_features), key=lambda item: item[1])
            if tile == best.tile_id and np.isfinite(score) and score > best.confidence:
                best = Classification(tile, score)
        return best


def with_private_hand_packet(resources, manifest_path):
    from PIL import Image
    from workspace.vision.tiles_v0_1.template_classifier import _feature
    path = Path(manifest_path)
    manifest = json.loads(path.read_text())
    from .neutral_face_feature_probe import neutral
    neutral_features = []
    # Use exactly the already session-filtered training labels, never all labels.
    for label in resources.get('training_labels', ()):
        if label.get('gold_skin_only') or label['region'] not in {'hand_region', 'draw_region', 'draw_visual'}:
            continue
        with Image.open(Path(resources['root']) / label['image']) as source:
            crop = source.convert('RGB')
            if Path(label['image']).parts[:1] != ('templates',):
                x, y, width, height = label['bbox']
                crop = crop.crop((x, y, x + width, y + height))
        neutral_features.append((label['tile_id'], neutral(crop)))
    features = []
    for row in manifest['rows']:
        with Image.open(path.parent / row['crop']) as source:
            image = source.convert('RGB')
        if hashlib.sha256(image.tobytes()).hexdigest() != row['rgb_sha256']:
            raise ValueError('Private hand reference RGB mismatch')
        features.append((row['truth'], _feature(image, region='concealed_identity')))
        neutral_features.append((row['truth'], neutral(image)))
    result = dict(resources)
    result['classifier'] = TranslatedHandClassifier(resources['classifier'], features, neutral_features)
    return result
