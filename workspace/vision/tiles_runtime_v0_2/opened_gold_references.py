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
        scores = self._scores(image)
        tile, score = max(scores, key=lambda item: item[1])
        # A lone same-skin nearest reference can confuse absent classes.
        # Prefer agreement with the original full-bank ranking.
        if tile == original.tile_id and .82 <= score <= 1.:
            return Classification(tile, score)
        # Resolve an old-template disagreement only when its competing class
        # has an actual opened-Gold reference and is rejected by that bank.
        # Missing-class nearest matches and multiple passing classes abstain.
        represented = {name for name, _ in scores}
        passing = {name for name, value in scores if .82 <= value <= 1.}
        if (original.tile_id in represented and passing == {tile}
                and all(value < .82 for name, value in scores if name == original.tile_id)):
            return Classification(tile, score)
        return original

    def opened_gold_reference_supported(self, image, prediction):
        return prediction.confidence >= .82 and any(
            tile == prediction.tile_id and .82 <= score <= 1.
            for tile, score in self._scores(image))
