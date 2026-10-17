"""Cosine-gate impossibility is a geometry fact, not a classifier accuracy claim."""
import importlib.util
import math
import unittest


@unittest.skipUnless(importlib.util.find_spec("numpy"), "numpy optional")
class PublicIdentityScoreFeasibilityTests(unittest.TestCase):
    def setUp(self):
        import numpy as np
        from workspace.vision.public_identity_shadow_v0_2 import (
            PublicTemplate, ShadowBank, SourceGroup,
        )
        self.np = np
        self.template = PublicTemplate
        self.sources = {
            name: SourceGroup(name, name * 64, name)
            for name in ("a", "b", "c")
        }
        self.bank_type = ShadowBank

    def pair(self, cls, similarity):
        first = self.np.asarray([1., 0.])
        second = self.np.asarray([similarity, math.sqrt(1 - similarity ** 2)])
        return [self.template("public_single", cls, group, group * 64,
                              group, feature)
                for group, feature in (("a", first), ("b", second))]

    def summarize(self, templates, **kwargs):
        from workspace.vision.public_identity_shadow_v0_2 import summarize_shadow_score_feasibility
        return summarize_shadow_score_feasibility(
            self.bank_type(self.sources, tuple(templates)), region="public_single",
            source_session="c", source_sha256="c" * 64, **kwargs)

    def test_two_sources_but_infeasible_at_fixed_gate(self):
        result = self.summarize(self.pair("R", .8543) + self.pair("N", .0307)
                                + self.pair("G", .4304))
        self.assertEqual(result["eligible_class_count"], 3)
        self.assertEqual(result["mathematically_possible_class_count"], 1)
        self.assertEqual(result["impossible_class_count"], 2)
        self.assertAlmostEqual(result["highest_impossible_score_ceiling"],
                               math.sqrt((1 + .4304) / 2), places=5)
        self.assertFalse(result["safe_for_runtime"])
        self.assertFalse(result["formal_promotion_evidence"])

    def test_duplicate_same_match_and_query_source_do_not_count(self):
        a = self.pair("G", .1)[0]
        same_group = self.template("public_single", "G", "another_clip", "z" * 64,
                                   "a", self.np.asarray([1., 0.]))
        query = self.template("public_single", "G", "c", "c" * 64, "c",
                              self.np.asarray([1., 0.]))
        result = self.summarize([a, same_group, query])
        self.assertEqual(result["eligible_class_count"], 0)

    def test_best_cross_group_pair_is_generous_upper_bound(self):
        templates = self.pair("G", .1)
        templates.append(self.template("public_single", "G", "a", "a" * 64,
                                       "a", self.np.asarray([.99, .1])))
        # A third same-match crop may improve the upper bound but cannot be
        # counted as a third independent original match.
        result = self.summarize(templates, minimum_score=.8)
        self.assertEqual(result["eligible_class_count"], 1)
        self.assertEqual(result["mathematically_possible_class_count"], 0)

    def test_bad_feature_fails_closed(self):
        invalid = self.template("public_single", "G", "a", "a" * 64,
                                "a", self.np.asarray([float("nan"), 0.]))
        with self.assertRaisesRegex(ValueError, "invalid public template feature"):
            self.summarize([invalid])


if __name__ == "__main__":
    unittest.main()
