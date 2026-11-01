"""Prevent related clips or unsupported lineage from becoming references."""
from types import SimpleNamespace
import unittest
from workspace.vision.public_meld_opponent_reference_probe import source_disjoint_templates


class ReferenceSourceTests(unittest.TestCase):
    def test_same_match_different_file_and_exact_source_are_excluded(self):
        related = SimpleNamespace(match_group='first_hand', source_sha256='clip_a')
        exact = SimpleNamespace(match_group='different_alias', source_sha256='query_sha')
        unrelated = SimpleNamespace(match_group='other_match', source_sha256='other_sha')
        self.assertEqual(source_disjoint_templates([related, exact, unrelated],
            {'first_hand', 'eight_hand'}, 'query_sha'), [unrelated])

    def test_missing_lineage_abstains(self):
        missing_group = SimpleNamespace(match_group=None, source_sha256='other_sha')
        missing_source = SimpleNamespace(match_group='other_match', source_sha256=None)
        self.assertEqual(source_disjoint_templates([missing_group, missing_source], set(), 'query_sha'), [])

    def test_five_related_frames_still_have_one_original_match(self):
        templates = [SimpleNamespace(match_group='other_match', source_sha256='other_sha') for _ in range(5)]
        accepted = source_disjoint_templates(templates, {'query_match'}, 'query_sha')
        self.assertEqual(len({t.match_group for t in accepted}), 1)
