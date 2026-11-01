"""Opt-in OFFLINE recovery candidate. Never installed as the Runtime default.

Inner-neutral scores are developmental NCC diagnostics, not calibrated
confidence. The .82 branch mirrors the existing trial for paired experiments;
it does not establish source qualification or promotion.
"""

class InnerRecoveryProbe:
    def __init__(self, ordinary):
        self.ordinary = ordinary

    def __getattr__(self, name):
        return getattr(self.ordinary, name)

    def classify(self, image, region=None):
        prediction = self.ordinary.classify(image, region=region)
        features = getattr(self.ordinary, 'inner_features', ())
        if (region not in {'concealed_identity', 'hand_region', 'draw_region', 'draw_visual'}
                or prediction.confidence >= .82 or not features):
            return prediction
        import cv2
        import math
        from .neutral_face_feature_probe import neutral
        from workspace.vision.tiles_v0_1.template_classifier import Classification
        query = neutral(image, trim_edges=True)
        padded = cv2.copyMakeBorder(query, 3, 3, 3, 3, cv2.BORDER_REPLICATE)
        scores = [(float(cv2.matchTemplate(padded, ref, cv2.TM_CCOEFF_NORMED).max()), tile)
                  for tile, ref in features]
        valid = [(score, tile) for score, tile in scores if math.isfinite(score)]
        if not valid:
            return prediction
        score, tile = max(valid)
        return Classification(tile, score) if score >= .82 else prediction
