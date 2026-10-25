"""Same-feature NCC acceleration for the explicit ordinary-hand trial only."""
import numpy as np
from workspace.vision.tiles_v0_1.template_classifier import Classification, _feature


class BatchedOrdinaryClassifier:
    def __init__(self, ordinary):
        self.ordinary = ordinary
        bank = ordinary.regional_templates.get('concealed_identity', {})
        self.tiles = tuple(tile for tile, refs in bank.items() for _ in refs)
        features = [ref for refs in bank.values() for ref in refs]
        self.matrix = np.stack([ref.ravel() for ref in features]).astype(np.float64)
        self.shape = features[0].shape
        self.matrix -= self.matrix.mean(axis=1, keepdims=True)
        self.norms = np.linalg.norm(self.matrix, axis=1)
        self.matrix /= np.where(self.norms > 0, self.norms, 1)[:, None]
        self.matrix.flags.writeable = False

    def __getattr__(self, name):
        return getattr(self.ordinary, name)

    def classify(self, image, region=None):
        if region != 'concealed_identity':
            return self.ordinary.classify(image, region=region)
        sample = _feature(image, region=region)
        if sample.shape != self.shape:
            return self.ordinary.classify(image, region=region)
        query = sample.ravel().astype(np.float64)
        query -= query.mean()
        norm = np.linalg.norm(query)
        query /= norm if norm > 0 else 1
        scores = np.einsum('ij,j->i', self.matrix, query, optimize=False)
        # OpenCV defines constant-template CCOEFF_NORMED as 1, including
        # constant queries; nonconstant-template/constant-query scores are 0.
        scores[self.norms == 0] = 1
        scores = np.clip(scores, -1., 1.)
        winner = int(np.argmax(scores))
        best = float(scores[winner])
        others = [score for tile, score in zip(self.tiles, scores)
                  if tile != self.tiles[winner]]
        if abs(best - .82) < 1e-5 or (others and best - max(others) < 1e-5):
            return self.ordinary.classify(image, region=region)
        return Classification(self.tiles[winner], max(0., best))
