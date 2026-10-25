"""Opt-in private replay adapter for recovered hand references and translation.

NCC scores remain development diagnostics, not calibrated probabilities.
The adapter never changes source qualification, geometry or yellow-Gold roles.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


class TranslatedHandClassifier:
    def __init__(self, ordinary, extra_features, neutral_features=(), inner_features=()):
        self.ordinary = ordinary
        self.extra_features = extra_features
        self.neutral_features = neutral_features
        self.inner_features = inner_features

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
        for trim_edges, features in ((False, self.neutral_features), (True, self.inner_features)):
            if best.confidence >= 0.82 or not features:
                continue
            from .neutral_face_feature_probe import neutral
            candidate_query = neutral(image, trim_edges=trim_edges)
            padded_neutral = cv2.copyMakeBorder(candidate_query, 3, 3, 3, 3, cv2.BORDER_REPLICATE)
            tile, score = max(
                ((tile, float(cv2.matchTemplate(padded_neutral, ref, cv2.TM_CCOEFF_NORMED).max()))
                 for tile, ref in features), key=lambda item: item[1])
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
    inner_features = []
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
        inner_features.append((label['tile_id'], neutral(crop, trim_edges=True)))
    features = []
    opened_gold_features = []
    for row in manifest['rows']:
        with Image.open(path.parent / row['crop']) as source:
            image = source.convert('RGB')
        if hashlib.sha256(image.tobytes()).hexdigest() != row['rgb_sha256']:
            raise ValueError('Private hand reference RGB mismatch')
        role = row.get('role', 'hand')
        if role == 'opened_gold':
            opened_gold_features.append((row['truth'], _feature(image, region='gold_region')))
            continue
        if role != 'hand':
            raise ValueError('Unknown reference role')
        features.append((row['truth'], _feature(image, region='concealed_identity')))
        neutral_features.append((row['truth'], neutral(image)))
        inner_features.append((row['truth'], neutral(image, trim_edges=True)))
    result = dict(resources)
    ordinary = resources['classifier']
    from workspace.vision.tiles_v0_1.template_classifier import TemplateTileClassifier
    if isinstance(ordinary, TemplateTileClassifier):
        from .batched_ordinary_classifier import BatchedOrdinaryClassifier
        ordinary = BatchedOrdinaryClassifier(ordinary)
    if opened_gold_features:
        from .opened_gold_references import OpenedGoldReferenceClassifier
        ordinary = OpenedGoldReferenceClassifier(ordinary, opened_gold_features)
    result['classifier'] = TranslatedHandClassifier(ordinary, features, neutral_features, inner_features)
    return result


# Small process-local cache: retain classifier objects so identity keys cannot
# be recycled. The worker is single-flight; raw asset bytes are checked on hits.
_PACKET_CLASSIFIERS = {}


def cached_private_hand_packet(resources, manifest_path):
    path = Path(manifest_path).resolve()
    manifest_bytes = path.read_bytes()
    manifest = json.loads(manifest_bytes)
    digest = hashlib.sha256(manifest_bytes)
    for row in manifest['rows']:
        digest.update(hashlib.sha256((path.parent / row['crop']).read_bytes()).digest())
    labels_digest = hashlib.sha256(json.dumps(
        resources.get('training_labels', ()), sort_keys=True).encode()).hexdigest()
    key = (id(resources['classifier']), str(path), str(resources.get('root')),
           labels_digest, digest.hexdigest())
    classifier = _PACKET_CLASSIFIERS.get(key)
    if classifier is None:
        classifier = with_private_hand_packet(resources, path)['classifier']
        _PACKET_CLASSIFIERS[key] = classifier
        while len(_PACKET_CLASSIFIERS) > 2:
            del _PACKET_CLASSIFIERS[next(iter(_PACKET_CLASSIFIERS))]
    return {**resources, 'classifier': classifier}
