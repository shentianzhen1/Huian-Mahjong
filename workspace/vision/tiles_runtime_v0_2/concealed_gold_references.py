"""Opt-in reference scoring for concealed yellow-Gold faces only.

NCC is a development score, not calibrated confidence. This wrapper never
changes source coverage, ordinary features, or opened-indicator methods.
"""


class ConcealedGoldReferenceClassifier:
    def __init__(self, ordinary, references):
        self.ordinary = ordinary
        self.references = tuple(references)

    def __getattr__(self, name):
        return getattr(self.ordinary, name)

    def classify_gold_skin(self, image):
        import cv2
        import math
        from workspace.vision.tiles_v0_1.template_classifier import Classification, _feature
        original = self.ordinary.classify_gold_skin(image)
        if original.confidence >= .82 or not self.references:
            return original
        query = _feature(image, region='gold_region')
        passing = [(tile, score) for tile, reference in self.references
                   if math.isfinite(score := float(cv2.matchTemplate(
                       query, reference, cv2.TM_CCOEFF_NORMED)[0, 0]))
                   and .82 <= score <= 1.]
        # A missing-class nearest reference cannot replace full-bank identity.
        if {tile for tile, _ in passing} != {original.tile_id}:
            return original
        return Classification(original.tile_id, max(score for _, score in passing))
