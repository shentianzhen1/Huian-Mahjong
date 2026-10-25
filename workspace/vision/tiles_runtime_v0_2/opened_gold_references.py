"""Verified-reference candidate matching for the explicit opened-Gold role."""


class OpenedGoldReferenceClassifier:
    def __init__(self, ordinary, references):
        self.ordinary = ordinary
        self.references = references
        self.opened_gold_reference_count = len(references)

    def __getattr__(self, name):
        return getattr(self.ordinary, name)

    def _scores(self, image):
        import cv2
        from workspace.vision.tiles_v0_1.template_classifier import _feature
        query = _feature(image, region='gold_region')
        return [(tile, float(cv2.matchTemplate(query, ref, cv2.TM_CCOEFF_NORMED)[0, 0]))
                for tile, ref in self.references]

    def classify_opened_gold(self, image):
        from workspace.vision.tiles_v0_1.template_classifier import Classification
        original = self.ordinary.classify_gold_skin(image)
        if original.confidence >= .82:
            return original
        tile, score = max(self._scores(image), key=lambda item: item[1])
        # A lone same-skin nearest reference can confuse absent classes.
        # Require agreement with the independent original full-bank ranking.
        if tile == original.tile_id and .82 <= score <= 1.:
            return Classification(tile, score)
        return original

    def opened_gold_reference_supported(self, image, prediction):
        return prediction.confidence >= .82 and any(
            tile == prediction.tile_id and .82 <= score <= 1.
            for tile, score in self._scores(image))
