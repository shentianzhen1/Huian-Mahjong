from __future__ import annotations

import unittest

from workspace.vision.public_meld_identity_sift import (
    SIFT_CLAHE_CLIP_LIMIT,
    SIFT_CLAHE_TILE_GRID,
    SIFT_FALLBACK_RAW_MATCHES,
    SIFT_KNN_K,
    SIFT_MINIMUM_OTHER_MATCH_GROUPS,
    SIFT_NFEATURES,
    SIFT_RATIO_TEST,
    SIFT_SCALE_FACTOR,
)
from workspace.vision.public_meld_sift_candidate import (
    load_public_meld_sift_candidate,
)


PATH = "references/vision/2026-10-01/public_meld_sift_candidate_v0_1.json"


class PublicMeldSiftContractAlignmentTests(unittest.TestCase):
    def test_frozen_candidate_matches_implementation_constants(self):
        candidate = load_public_meld_sift_candidate(PATH)

        self.assertEqual(candidate.scale_factor, SIFT_SCALE_FACTOR)
        self.assertEqual(candidate.clahe_clip_limit, SIFT_CLAHE_CLIP_LIMIT)
        self.assertEqual(candidate.clahe_tile_grid, SIFT_CLAHE_TILE_GRID)
        self.assertEqual(candidate.nfeatures, SIFT_NFEATURES)
        self.assertEqual(candidate.knn_k, SIFT_KNN_K)
        self.assertEqual(candidate.ratio_test, SIFT_RATIO_TEST)
        self.assertEqual(
            candidate.fallback_best_raw_matches,
            SIFT_FALLBACK_RAW_MATCHES,
        )
        self.assertEqual(
            candidate.minimum_other_match_groups,
            SIFT_MINIMUM_OTHER_MATCH_GROUPS,
        )

        self.assertFalse(candidate.wire_into_runtime)
        self.assertFalse(candidate.safe_for_hint)
        self.assertFalse(candidate.safe_for_executor)
        self.assertFalse(candidate.formal_promotion_evidence)


if __name__ == "__main__":
    unittest.main()
