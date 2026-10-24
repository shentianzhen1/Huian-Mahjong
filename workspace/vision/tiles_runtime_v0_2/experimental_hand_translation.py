"""Opt-in private replay adapter for recovered hand references and translation.

NCC scores remain development diagnostics, not calibrated probabilities.
The adapter never changes source qualification, geometry or yellow-Gold roles.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


class TranslatedHandClassifier:
    def __init__(self, ordinary, extra_features):
        self.ordinary = ordinary
        self.extra_features = extra_features

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
        return best


def with_private_hand_packet(resources, manifest_path):
    from PIL import Image
    from workspace.vision.tiles_v0_1.template_classifier import _feature
    path = Path(manifest_path)
    manifest = json.loads(path.read_text())
    features = []
    for row in manifest['rows']:
        with Image.open(path.parent / row['crop']) as source:
            image = source.convert('RGB')
        if hashlib.sha256(image.tobytes()).hexdigest() != row['rgb_sha256']:
            raise ValueError('Private hand reference RGB mismatch')
        features.append((row['truth'], _feature(image, region='concealed_identity')))
    result = dict(resources)
    result['classifier'] = TranslatedHandClassifier(resources['classifier'], features)
    return result
