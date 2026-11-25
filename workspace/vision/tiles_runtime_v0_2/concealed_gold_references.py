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
        from workspace.vision.tiles_v0_1.template_classifier import Classification
        original = self.ordinary.classify_gold_skin(image)
        if original.confidence >= .82 or not self.references:
            return original
        passing = self._passing_scores(image)
        # A missing-class nearest reference cannot replace full-bank identity.
        if {tile for tile, _ in passing} != {original.tile_id}:
            return original
        return Classification(original.tile_id, max(score for _, score in passing))

    def _passing_scores(self, image):
        import cv2
        import math
        from workspace.vision.tiles_v0_1.template_classifier import _feature
        query = _feature(image, region='gold_region')
        # One feature-pixel translation absorbs small crop changes between
        # waiting and drawn-hand geometry; reference identity must still agree.
        query = cv2.copyMakeBorder(query, 1, 1, 1, 1, cv2.BORDER_REPLICATE)
        passing = [(tile, score) for tile, reference in self.references
                   if math.isfinite(score := float(cv2.matchTemplate(
                       query, reference, cv2.TM_CCOEFF_NORMED).max()))
                   and .82 <= score <= 1.]
        return passing

    def concealed_gold_reference_supported(self, image, prediction):
        import math
        if not math.isfinite(prediction.confidence) or not .82 <= prediction.confidence <= 1.:
            return False
        passing = self._passing_scores(image)
        return {tile for tile, _ in passing} == {prediction.tile_id}
