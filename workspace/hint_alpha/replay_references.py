"""Explicit reference configuration for development video replay."""
import hashlib
import json
from functools import partial
from pathlib import Path


def apply_replay_references(resources, manifest_path):
    from workspace.vision.tiles_runtime_v0_2.experimental_hand_translation import with_private_hand_packet
    from workspace.vision.tiles_runtime_v0_2.dynamic_geometry import detect_dynamic_geometry
    path = Path(manifest_path).resolve()
    raw = path.read_bytes()
    manifest = json.loads(raw)
    adapted = with_private_hand_packet(resources, path)
    adapted = {**adapted, 'geometry_detector': partial(detect_dynamic_geometry, edge_seams=True)}
    return adapted, {
        'version': manifest.get('version'), 'count': len(manifest['rows']),
        'manifest_sha256': hashlib.sha256(raw).hexdigest(),
        'training_review': adapted.get('experimental_training_review'),
        'development_only': True, 'formal_promotion_evidence': False,
    }
